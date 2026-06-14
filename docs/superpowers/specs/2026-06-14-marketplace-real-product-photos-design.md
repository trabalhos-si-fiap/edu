# Marketplace — fotos reais para os produtos (design)

**Data:** 2026-06-14
**Escopo:** backend (`back-end/app/seeds/products.py` + testes)
**Relacionado:** [2026-06-13-marketplace-product-photos-design.md](2026-06-13-marketplace-product-photos-design.md) (pipeline de imagem original)

## Problema

Os 6 produtos do catálogo do marketplace usam placeholders de **cor sólida**
(PNGs gerados por `_solid_png`) como imagem. Funciona como placeholder, mas é
ruim para apresentar o app. Queremos **fotos reais, relevantes e de licença
livre**, armazenadas no nosso object storage (MinIO em dev, R2 em prod) e
servidas pelo pipeline existente.

## Contexto da arquitetura (já existente, não muda)

- `Product.image_url` (`String(512)`) guarda a **chave do objeto** (ex.:
  `products/seed-0.png`), **não** uma URL.
- `app/core/storage.py::ObjectStorage` fala S3 via `aioboto3` (`put_object`,
  `delete_object`, `generate_presigned_get`). Bucket privado.
- `app/core/media.py::presigned_image_url` converte a chave em presigned GET URL
  (cache no Redis ~23h) na serialização de `ProductOut`.
- O app Flutter recebe a presigned URL e renderiza com `CachedNetworkImage`.
- `seed_products()` é chamado **apenas manualmente** (`uv run python -m
  app.seeds.products`) — não há hook de startup. Logo, "sempre sobrescrever" só
  dispara quando alguém roda o seed de propósito.

## Decisões (tomadas no brainstorming)

1. **Fonte:** curar 6 URLs do Unsplash e **baixar no momento do seed** (sem
   binários no repo, mantém o padrão atual do seed).
2. **Sobrescrita:** **sempre sobrescrever** a imagem dos 6 produtos com a foto
   curada a cada execução do seed (inclusive sobre uploads de admin). Aceito por
   ser mais simples; seguro porque o seed só roda manualmente.
3. **Aplicação:** implementar + testes apenas. Não subir docker nem rodar o seed
   neste trabalho.

## Design

### Fonte das fotos

Unsplash License: uso livre, inclusive comercial, sem atribuição obrigatória.
Uma foto relevante por produto, embutida como `photo_url` em cada dict de
`SEED_PRODUCTS`, usando os parâmetros de CDN do Unsplash para baixar um JPEG
quadrado de ~800px diretamente (sem necessidade de Pillow/redimensionamento):

```
https://images.unsplash.com/photo-<id>?w=800&h=800&fit=crop&q=80&fm=jpg
```

| Produto | Tema da foto |
|---|---|
| Guia de Redação Nota 1000 | escrita / caderno e caneta |
| Mastering Data Synthesis | dados / dashboards / laptop |
| Diagnostic AI Toolkit | tecnologia / IA |
| Simulado ENEM Completo | prova / mesa de estudo com papéis |
| Mapa Mental de Biologia | biologia / microscópio / células |
| Curso de Matemática Essencial | matemática / equações / lousa |

Cada URL será **validada com `curl -sI` (esperando HTTP 200)** durante a
implementação. Se algum ID retornar 404, é substituído por outro equivalente.

### Mudanças em `app/seeds/products.py`

- Adicionar a chave `photo_url` aos 6 dicts de `SEED_PRODUCTS`.
- Novo helper assíncrono:

  ```python
  async def _fetch_image(url: str) -> bytes:
      """Baixa a imagem da URL curada. Timeout e cap de tamanho defensivos.
      Levanta em erro de rede/HTTP — o chamador trata."""
  ```

  Usa `httpx.AsyncClient` (já é dependência do projeto). Timeout explícito
  (ex.: 15s). Rejeita corpo acima de um limite defensivo
  (`settings.MEDIA_MAX_UPLOAD_BYTES`).

- **Injeção de dependência** na assinatura para testabilidade sem rede:

  ```python
  async def seed_products(
      session: AsyncSession,
      *,
      storage: "ObjectStorage | None" = None,
      fetch_image: Callable[[str], Awaitable[bytes]] = _fetch_image,
  ) -> int:
  ```

- Chave do objeto passa a `products/seed-{index}.jpg`; content-type
  `image/jpeg`.

- Lógica por produto (vale para novo **e** existente):

  ```python
  photo_url = data.get("photo_url")
  if storage is not None and photo_url:
      key = f"products/seed-{index}.jpg"
      try:
          body = await fetch_image(photo_url)
      except Exception as exc:  # rede/HTTP/timeout
          logger.warning("seed: falha ao baixar foto de {!r}: {}", data["name"], exc)
          # mantém a image_url atual; não apaga imagem boa por falha transitória
      else:
          await storage.put_object(key, body, "image/jpeg")
          if product.image_url and product.image_url != key:
              # limpa o objeto antigo (ex.: o .png placeholder) — best-effort
              try:
                  await storage.delete_object(product.image_url)
              except Exception:
                  pass
          product.image_url = key
  ```

  Para produtos **novos**, o `product` é o recém-criado; para **existentes**, é
  a linha carregada por nome (sempre sobrescreve).

- `_solid_png` é **mantido** como fallback para eventuais entradas futuras sem
  `photo_url` (KISS — sem remover comportamento que ainda pode servir). Como os
  6 atuais terão `photo_url`, na prática não é usado no seed atual.

### `main()`

Sem mudança de assinatura — segue criando `ObjectStorage()` e usando o
`fetch_image` default (`_fetch_image` real via httpx).

### Tratamento de erro

- Falha de download → warning via `loguru.logger` + mantém `image_url` atual do
  produto. O seed continua para os demais produtos.
- `delete_object` do objeto antigo é best-effort (um órfão no bucket não pode
  derrubar o seed).

## Plano de testes (TDD — escritos antes da implementação)

Arquivo: `back-end/tests/seeds/test_products_seed.py`.

- `_RecordingStorage` ganha `delete_object` (registra chaves deletadas).
- Fake fetcher: `async def _fake_fetch(url) -> bytes` retornando bytes JPEG
  canônicos (cabeçalho `\xff\xd8\xff` + corpo), injetado via `fetch_image=`.
- **Atualizar** `test_seed_uploads_image_and_sets_key_when_storage_given`: chave
  termina em `.jpg`, content-type `image/jpeg`, `image_url` começa com
  `products/seed-` e termina `.jpg`.
- **Inverter** `test_seed_does_not_overwrite_existing_images` →
  `test_seed_always_overwrites_images`: após dois runs, o segundo **re-sobe** a
  imagem e **deleta** a chave anterior quando a chave muda.
- **Novo** `test_seed_download_failure_keeps_existing_image`: fetcher que levanta
  exceção; `image_url` permanece o valor anterior; nenhum `put_object`
  correspondente; (opcional) checa warning.
- Manter `test_seed_backfills_images_for_existing_products_without_one`
  (agora via download) e `test_solid_png_is_a_valid_image`.
- Os testes que não usam storage (`test_inserts_full_catalog`,
  `test_seeds_sample_reviews_and_headline_aggregates`, `test_is_idempotent`)
  permanecem válidos sem alteração.

## Fora de escopo

- Sem mudanças no `Product` model, na rota de presign, na validação de upload, ou
  no app Flutter.
- Sem subir docker / rodar o seed neste trabalho.
- Nenhum binário de imagem commitado no repositório.

## Riscos e mitigação

- **URLs do Unsplash podem expirar com o tempo.** Mitigação: validação na
  implementação; falha de download é tratada com warning (não quebra o seed).
- **Dependência de rede no seed.** Aceita explicitamente na decisão de
  brainstorming; o seed roda manualmente, não em boot.
