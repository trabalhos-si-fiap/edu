# Fotos nos produtos do marketplace — Design

**Data:** 2026-06-13
**Status:** Aprovado para planejamento

## Objetivo

Permitir que produtos do marketplace tenham fotos reais: um **admin faz upload** de uma
imagem pelo backend, o arquivo é armazenado em **object storage (Cloudflare R2)** e lido via
**presigned URL**, e o **app Flutter exibe** a imagem real no card e na tela de detalhe (com
fallback para o ícone atual).

Como parte da exibição, o marketplace do Flutter — hoje 100% mock — passa a **consumir a API
de produtos** (`/api/products`), incluindo reviews.

## Decisões tomadas (brainstorming)

| Decisão | Escolha |
|---|---|
| Escopo | Upload (backend) **+** exibição (app) |
| Armazenamento | **Cloudflare R2** (object storage, API S3-compatível via `aioboto3`) |
| Leitura das imagens | **Presigned GET URLs** geradas no backend, memoizadas no Redis |
| Dev/Test | **MinIO** (S3-compat) no Docker Compose; R2 em prod (só troca `endpoint_url`) |
| Controle de acesso ao upload | Novo campo **`is_admin`** no `User` + dependency `require_admin` |
| UI de upload | **Só backend** (admin via API/ferramenta interna; sem tela no app) |
| Consumo da API no app | **Sim** — aposentar mock, consumir `/api/products` (Option B) |
| Reviews | **Wirar à API** (`GET /products/{id}/reviews`), aposentar `mockReviews` |
| Carrinho | **Migrar `cart_store` para id `String`** (UUID) |

## Estado atual (resumo da investigação)

- Backend: `Product.image_url` (`String(512)`, default `""`) já existe no model, no schema
  `ProductOut` e no model Dart `Product.imageUrl`. **Nenhum upload ou object storage existe.**
  Seed não popula `image_url`. `OrderItem.image_url` faz snapshot da URL do produto na compra.
- Auth: existe JWT (`get_current_user` em `app/modules/auth/dependencies.py`); todas as rotas
  de produto são autenticadas; **não há roles** (User só tem `is_active`/`is_verified`). Há um
  wrapper `get_current_active_user` previsto para gating futuro.
- Frontend: marketplace renderiza **placeholders com ícone** (`AppColors.imagePlaceholder` +
  `iconForProduct`), nunca imagem. Usa `mockProducts`/`mockReviews`, **não chama a API**.
  `Product.id` é `int`; backend usa **UUID**.

---

## Arquitetura

### Fluxo

```
Admin ──(multipart, Bearer JWT)──▶ POST /api/products/{id}/image  [require_admin]
                                        │ valida tipo/tamanho/magic bytes
                                        │ put_object no R2: products/{uuid}.{ext}
                                        │ atualiza Product.image_key
                                        ▼
                                   ProductOut (image_url = presigned URL)

App ──(Bearer JWT)──▶ GET /api/products            ──▶ lista + image_url (presigned)
                      GET /api/products/{id}/reviews ──▶ reviews
       (serialização gera/memoiza a presigned URL p/ cada image_key → Redis)
App ──▶ GET <presigned URL do R2>  ──▶ bytes da imagem (direto do R2, sem passar pelo backend)
```

A `image_url` exposta na API é uma **presigned GET URL** gerada a partir da `image_key`
armazenada no banco. O backend fica no caminho de **geração da URL** (não no de download dos
bytes — o app baixa direto do R2).

---

## Backend

### 1. Role admin (`app/modules/auth/`)

- **Model** (`models.py`): novo campo
  `is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())`.
- **Migration Alembic**: adiciona a coluna com `server_default` false (não quebra usuários existentes).
- **Dependency** (`dependencies.py`): `require_admin` que recebe `Depends(get_current_user)` e
  levanta `HTTPException(403)` se `not user.is_admin`. Pode reusar/estender o ponto previsto em
  `get_current_active_user`.

### 2. Infra de object storage (R2)

- **Dependências**: adicionar `python-multipart` e `aioboto3` ao `pyproject.toml`.
- **Config** (`app/core/config.py`, pydantic-settings):
  `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`,
  `R2_PUBLIC_ENDPOINT` (opcional — endpoint usado para montar a presigned URL acessível pelo
  app, ex. via emulador), `MEDIA_PRESIGN_TTL` (ex. `86400` s) e `MEDIA_PRESIGN_CACHE_TTL`
  (ex. `82800` s — menor que o TTL para haver margem). **Todas via env/secrets — nunca no código.**
- **Cliente de storage** (`app/core/storage.py` ou `app/modules/products/storage.py`):
  wrapper fino sobre `aioboto3` (`endpoint_url`, credenciais, bucket) expondo `put_object`,
  `delete_object` e `generate_presigned_url`. O `endpoint_url` aponta para **MinIO** em
  dev/test e para **R2** em prod — só a env muda.
- **Docker Compose**: serviço `minio` (+ `minio-init`/console opcional) com bucket de dev criado
  no boot; backend aponta `R2_ENDPOINT_URL` para o MinIO em dev.

### 3. Endpoint de upload

`POST /api/products/{product_id}/image`, `Depends(require_admin)`, aceita `UploadFile`.

Validações (regra de segurança #4 — inputs com limites):
- **Content-type** numa whitelist: `image/jpeg`, `image/png`, `image/webp`.
- **Tamanho server-side**: limite **5 MB**; ler em chunks com cap e rejeitar (`413`/`400`) se exceder
  — não confiar em `Content-Length` do cliente.
- **Magic bytes**: validar a assinatura real do arquivo (não confiar em extensão/content-type).
- **Object key gerada pelo servidor**: `products/{uuid4}.{ext}` derivada do tipo validado —
  **nunca** usar o filename do cliente.

Comportamento:
- `put_object` no bucket (com `ContentType` correto) na key gerada.
- Atualiza `product.image_key` via service layer.
- Remove o objeto antigo do produto, se houver (best-effort, dentro de `try/finally`).
- Retorna `ProductOut` atualizado (com `image_url` presigned).
- `404` se o produto não existir.

### 4. Modelo, service e serialização (presigned)

- **Model** (`app/modules/products/models.py`): renomear a coluna `image_url` → **`image_key`**
  (`String(512)`, default `""`), que passa a guardar a object key. Migration Alembic renomeando
  a coluna (dados atuais são `""`, sem backfill necessário).
- **`OrderItem`** (`app/modules/orders/models.py`): o snapshot passa a guardar a **key**
  (`image_key`); a serialização de pedidos também gera presigned na leitura. ⚠️ área afetada —
  o caminho de criação de pedido (orders service) que copia a imagem do produto precisa copiar
  a `image_key`.
- **Service** (`services.py`): função para setar a `image_key` do produto (busca, atualiza, commit).
  Lógica de upload/validação/storage isolada em helper testável, separada da rota.
- **Serialização** (`schemas.py` / camada de montagem do `ProductOut`): `image_url` **não** é
  campo de banco — é derivado. Para cada `image_key` não-vazia, gerar a presigned URL e expô-la
  como `image_url`. Key vazia → `image_url = ""`.

### 4b. Presigned URL + cache no Redis

- Geração via `generate_presigned_url('get_object', ...)` com expiração `MEDIA_PRESIGN_TTL`.
- **Memoização no Redis**: chave `presign:{image_key}` → URL, TTL `MEDIA_PRESIGN_CACHE_TTL`.
  Antes de gerar, consultar o cache; assim a mesma `image_key` devolve a **mesma URL** dentro da
  janela, mantendo estável a chave de cache do `CachedNetworkImage` no app (evita re-download a
  cada request). Em listagens, evita N assinaturas por página.
- Trade-off aceito: a URL expira após o TTL; o app re-busca a lista e recebe uma nova URL — a
  imagem é re-baixada apenas quando a URL efetivamente rotaciona.

### 5. Seed (`app/seeds/products.py`)

- Popular `image_url` dos produtos seed (URLs estáticas válidas ou rodando o upload), para o app
  exibir imagens de cara. Mantém o seed idempotente.

### 6. Testes (TDD — Red/Green/Refactor)

Testes antes da implementação, com `httpx.AsyncClient`, banco real e **MinIO** como storage:
- `require_admin`: usuário comum → `403`; admin → passa.
- Upload: sucesso (200 + `image_key` populada + objeto presente no bucket MinIO); content-type
  inválido → rejeitado; tamanho acima do limite → rejeitado; arquivo não-imagem (magic bytes) →
  rejeitado; produto inexistente → `404`; substituição remove o objeto antigo.
- Serialização: `ProductOut.image_url` é uma presigned URL quando há `image_key`; `""` quando não há.
- Cache de presign: segunda chamada usa a URL memoizada no Redis (não re-assina).

---

## Frontend (Flutter)

### 1. Renderização — widget `ProductImage`

- Adicionar pacote `cached_network_image`.
- `features/marketplace/presentation/widgets/product_image.dart`: se `imageUrl` não-vazio →
  `CachedNetworkImage` com `placeholder` (loading) e `errorWidget` = ícone atual
  (`iconForProduct`); se vazio → ícone atual. Respeitar o `AspectRatio`/dimensões existentes do
  card e do hero.
- **Cache vs presigned:** `CachedNetworkImage` cacheia pela URL. Como o backend memoiza a
  presigned URL (Redis), a URL é estável dentro da janela de TTL → o cache do app funciona.
  Quando a URL rotaciona, a imagem é re-baixada (aceito). O app não precisa de lógica especial.
- Usar no card (`marketplace_screen.dart`) e no hero (`product_detail_screen.dart`),
  substituindo os blocos de placeholder.

### 2. Camada de dados (padrão `AddressesApi`/`NotificationsApi`)

- `features/marketplace/data/products_api.dart`: classe `ProductsApi` com `http.Client` +
  `TokenStore`, header `Authorization: Bearer <access>`, exceção `ProductsException`.
  - `list({String? q, int limit, int offset})` → `GET /products` → `List<Product>`.
  - `reviews(String productId)` → `GET /products/{id}/reviews` → `List<Review>`.
- `Product.fromJson` mapeando snake_case (`image_url`, `rating_avg`, `rating_count`).
- `Review.fromJson` mapeando os campos de `ReviewOut`.

### 3. Migração de `id` `int → String` (ripple do UUID)

Backend usa UUID; o app passa a usar `String`. Pontos afetados (confirmados por grep):
- `marketplace/domain/product.dart`: `Product.id` e `Review.id` → `String`.
- `cart/data/cart_store.dart`: `_indexOf`, `decrement`, `removeAll` (`int productId` → `String`).
- `marketplace_screen.dart`: `Navigator.pushNamed('/product', arguments: product.id)` (arg String).
- Rota `/product`: handler que recebe o argumento passa a tratar `String`.
- `checkout_screen.dart`: `removeAll(product.id)` / `decrement(product.id)`.
- `product_detail_screen.dart` e `widgets/review_item.dart`: deixam de usar `reviewsForProduct`
  (mock) e passam a receber reviews carregadas da API.

### 4. Telas — consumir API

- `MarketplaceScreen`: substituir `mockProducts` por carga via `ProductsApi.list()` usando o
  padrão `setState` + estados de **loading / erro (com retry) / empty**, com `RefreshIndicator`
  (espelhando `AddressesScreen`). O filtro de tipo/busca passa a operar sobre dados da API.
- `ProductDetailScreen`: carregar produto (ou recebê-lo via navegação) e reviews via
  `ProductsApi.reviews(id)`, com loading/erro.
- **Aposentar** `features/marketplace/data/mock_marketplace.dart` (`mockProducts`, `mockReviews`,
  `productById`, `reviewsForProduct`).

### 5. Testes (Flutter)

- `Product.fromJson` / `Review.fromJson` (mapeamento snake_case, defaults).
- `ProductsApi` com `http.Client` fake (sucesso, erro de status, token ausente).
- `cart_store` com ids `String` (add/decrement/removeAll/total).

---

## Considerações de segurança

- Upload gateado por `require_admin` (regra #2 — controle de acesso explícito).
- Limite de tamanho server-side, whitelist de content-type e validação de magic bytes (regra #4).
- Object key gerada pelo servidor — sem usar input do cliente no path (anti path traversal).
- **Credenciais R2** (`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/endpoint) via env/secrets, nunca
  no código nem em log (regra #5).
- Bucket **privado**: leitura só via presigned URL com expiração (`MEDIA_PRESIGN_TTL`) — nada de
  objeto público. Presigned somente GET.

## Fora de escopo

- UI de upload no app Flutter.
- Múltiplas imagens por produto / galeria (mantém-se a única `image_key` existente).
- Redimensionamento/otimização de imagens server-side (thumbnails).
- **Copy-on-purchase** da imagem para uma key própria do pedido: o `OrderItem` referencia a mesma
  `image_key` do produto; se a foto do produto for substituída/deletada, thumbnails de pedidos
  antigos podem quebrar. Snapshot imutável do binário fica para depois.
- Custom domain público no R2 (optou-se por presigned URLs).

## Ordem de implementação sugerida

1. Backend: `is_admin` + migration → `require_admin` (+ testes).
2. Backend: config R2 + `python-multipart`/`aioboto3` + cliente de storage + MinIO no Compose.
3. Backend: model `image_url`→`image_key` (+ migration) e ajuste no `OrderItem`/orders service.
4. Backend: presigned + cache Redis na serialização de `ProductOut` (+ testes).
5. Backend: endpoint de upload + service + validações (TDD, contra MinIO).
6. Backend: seed populando imagens (via upload/objeto no bucket de dev).
7. Frontend: `Product/Review.fromJson` + `ProductsApi` (+ testes).
8. Frontend: migração `id` int→String (`cart_store`, rotas, checkout).
9. Frontend: widget `ProductImage` + telas consumindo a API; aposentar mock.
