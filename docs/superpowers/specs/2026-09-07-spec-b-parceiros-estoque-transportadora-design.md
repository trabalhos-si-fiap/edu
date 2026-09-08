# Spec B — Comércio: parceiros, estoque e transportadora — Design

**Data:** 2026-09-07
**Status:** Aprovado para planejamento
**Módulos:** `back-end/commerce-service/`, `web-admin/`, `front-end-flutter/lib/features/marketplace/`
**Depende de:** spec A (o corte). Paralela à spec D.

## Objetivo

Absorver o domínio da API Java que a spec A eliminou, e abrir o marketplace
para catálogos de parceiros — nesta entrega, a Leroy Merlin.

O resultado é o `commerce-service` sendo dono de estoque, transportadora,
parceiro e origem de expedição, com o painel Angular lendo tudo isso pelo
gateway. É o pré-requisito da spec C: sem origem por parceiro não há rota para
simular, e sem estoque não há falta de estoque para tratar.

## Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Entidade de parceiro | Estender `Fornecedor`, que já existe. Não criar entidade nova. |
| Pedido misto (Edu + Leroy) | Proibido. Bloqueio no carrinho, com mensagem. |
| Origem de expedição | Campo no parceiro. Edu sai de Aclimação/SP; Leroy, de Cajamar/SP. |
| Catálogo Leroy | Seed. Não há API pública da Leroy e não é o ponto da entrega. |
| Filtro de parceiro ativo | Regra de verdade, sem `if parceiro == "leroy"` em lugar nenhum. |
| Código PIX | Passa a ser emitido pelo backend. |
| Ocorrência de transportadora | Reconciliada dentro do `Ocorrencia` que já existe. |
| `web-admin` (Angular) | Passa a falar com o gateway no fim desta spec. |

## Contexto do código existente

### Já existe e deve ser estendido, não recriado

`commerce-service/app/models/produto.py` já traz três dos modelos que o prompt
de origem pedia para criar:

```python
class Fornecedor(Base):          # linha 22
    __tablename__ = "fornecedores"
    id, nome, contato, ativo

class Product(Base):             # linha 46
    __tablename__ = "products"
    id, name, type, subtype, description, price,
    image_url, rating_avg, rating_count, created_at, updated_at

class Estoque(Base):             # linha 83
    __tablename__ = "estoque"
    id, produto_id, fornecedor_id, quantidade, atualizado_em
    UniqueConstraint("produto_id", "fornecedor_id")
```

Consequências diretas:

- **`Fornecedor` é o parceiro.** Já tem `nome`, `contato` e `ativo` — o filtro
  por ativo que o item 3 pede é uma coluna que existe. Falta a origem.
- **`Estoque` é o `Inventory` do Java.** Produto mais quantidade, com unicidade
  por produto e fornecedor. A porta do Java aqui é vazia.
- **Produto pertence ao parceiro através do estoque**, não por chave direta.
  A seção de parceiros filtra por `Estoque.fornecedor_id`, sem coluna nova em
  `products`.

Também já existem, e a spec C depende deles:

- `app/services/substituicao_ia.py` — sugere substitutos por similaridade de
  embeddings, com queda para busca por categoria quando o modelo não carrega.
- `app/models/ocorrencia.py:15` — `tipo` já aceita `FALTA_ESTOQUE` e
  `ATRASO_ENTREGA`; o router expõe `/occurrences/stock-shortage`,
  `/occurrences/delivery-delay`, `/occurrences/order/{pedido_id}` e
  `/occurrences/{id}/resolve`.
- `app/services/previsao_entrega.py`.

### O que realmente falta portar do Java

Do domínio de `mobile_hybrid_app/api/`, sobra pouco:

| Entidade Java | Destino |
|---|---|
| `Product` | Já existe como `Product`. Nada a fazer. |
| `Inventory` | Já existe como `Estoque`. Nada a fazer. |
| `InventoryAdjustment` | **Portar.** Não há equivalente: é a trilha de auditoria de mudança de estoque. |
| `Carrier`, `CarrierStatus` | **Portar.** Não há equivalente. |
| `CarrierOccurrence`, `OccurrenceType`, `OccurrenceStatus` | **Reconciliar** dentro do `Ocorrencia` existente. |
| `AdminUser` | Já coberto por `auth_users.role = 'admin'`. Nada a fazer. |

Campos do `Carrier` no Java: `name`, `location`, `email`, `averageDeliveryDays`,
`rating`, `slaPercentage`, `status`, `createdAt`, `updatedAt`.

### Mock a eliminar

`front-end-flutter/lib/features/marketplace/presentation/checkout_screen.dart:444`
gera o código PIX copia-e-cola dentro do app, portado do legacy.

## Arquitetura

Nenhum serviço novo. Toda a mudança é dentro do `commerce-service`, mais o
cliente Angular.

```
commerce-service/app/
  models/
    produto.py        # Fornecedor ganha origem; Estoque ganha ajustes
    transportadora.py # NOVO — Carrier + CarrierStatus
    ocorrencia.py     # ganha os tipos de ocorrência de transportadora
  services/
    parceiros.py      # NOVO — regra de ativo e de origem
    estoque.py        # NOVO — ajuste com auditoria, atômico
    transportadoras.py# NOVO
    pix.py            # NOVO — emissão do payload copia-e-cola
  routers/
    parceiros.py      # NOVO — CRUD admin
    transportadoras.py# NOVO
    produtos.py       # ganha filtro por parceiro
    carrinho.py       # ganha a regra de origem única
```

O gateway precisa de duas entradas novas em
`api-gateway/app/routing.py::SERVICE_MAP`: `partners` e `carriers`, ambas para
`commerce`. Sem isso o painel recebe 404 e o erro parece do Angular.

### Origem de expedição

`Fornecedor` ganha três colunas: `origem_rotulo` (texto exibível, por exemplo
"Cajamar, SP"), `origem_lat` e `origem_lng`.

Os produtos próprios do Edu não têm parceiro externo — eles pertencem a um
fornecedor "Edu" que é criado pelo seed como qualquer outro, com origem
Aclimação/SP. Isso evita um caminho especial para "sem parceiro": todo produto
tem estoque, todo estoque tem fornecedor, todo fornecedor tem origem. Um único
caminho de código responde "de onde este pedido sai".

### Regra de origem única no carrinho

A regra vive no serviço de carrinho, não na tela. Ao adicionar um item, o
serviço compara o fornecedor do produto com o fornecedor dos itens já no
carrinho; se diferirem, recusa com `409 Conflict` e uma mensagem que o app
exibe sem reescrever.

A verificação é feita sob o mesmo lock de linha que a adição já usa, para que
duas adições simultâneas não montem um carrinho misto — a regra 3 do
`CLAUDE.md` se aplica: leitura seguida de escrita em recurso compartilhado é
atômica ou não é regra.

### Ocorrências: um modelo, não dois

O Java tem `CarrierOccurrence`, ancorada na transportadora. O commerce tem
`Ocorrencia`, ancorada no pedido. Manter os dois criaria duas telas de
ocorrência e dois relatórios que nunca fecham.

Decisão: `Ocorrencia` ganha uma referência opcional a transportadora e os
tipos vindos do Java. Uma ocorrência continua sendo sempre de um pedido; a
transportadora é uma dimensão dela, não um segundo dono. O painel de
transportadoras lê ocorrências agrupando por essa coluna.

## Componentes

### 1. `Fornecedor` como parceiro

Migração acrescentando `origem_rotulo`, `origem_lat`, `origem_lng`. CRUD em
`/partners`, restrito a `require_role("admin")`. Listagem paginada — a regra 4
do `CLAUDE.md` não abre exceção para telas de administração.

### 2. Estoque com auditoria

Porta do `InventoryAdjustment`: tabela `estoque_ajustes` com estoque de origem,
delta, motivo, autor e instante. O ajuste e o registro acontecem na mesma
transação, com `with_for_update()` sobre a linha de estoque. Um ajuste que não
deixa rastro é indistinguível de uma perda de dado.

Endpoint `POST /products/{id}/stock-adjustments`, admin apenas.

### 3. Transportadora

`app/models/transportadora.py` com os campos do `Carrier` do Java. CRUD em
`/carriers`, admin apenas. `status` é enum de texto, seguindo `StatusPedido` e
`CarrierStatus` — não booleano, porque o Java já distinguia mais de dois
estados.

### 4. Catálogo de parceiro no app

`GET /products` ganha o parâmetro `partner_id`. A tela de marketplace ganha uma
seção "Parceiros", separada do catálogo próprio, que lista os parceiros ativos
e seus produtos.

A seção pergunta ao backend quais parceiros estão ativos. Nesta entrega a
resposta é uma lista de um elemento, a Leroy Merlin — mas o app não sabe disso,
e desativar a Leroy no painel esvazia a seção sem tocar em código.

### 5. Seed da Leroy Merlin

Produtos de ambiente de estudo — mesa, luminária, cadeira, organizadores — com
imagem, preço e estoque. Mesmo caminho de seed dos produtos próprios, sem rota
especial.

### 6. Código PIX no backend

`app/services/pix.py` monta o payload copia-e-cola e o devolve na confirmação
de pagamento. O app passa a exibir o que recebeu.

Não é integração com provedor: é o mesmo algoritmo que hoje roda no cliente,
movido para onde o dado nasce. Isso fica dito no código e no relatório final da
entrega, para ninguém ler como pagamento real.

### 7. `web-admin` no gateway

Trocar a base de `localhost:8080/api/v1` pelo gateway e reescrever os serviços
Angular para os endpoints acima. As páginas `products-stock`, `carriers` e
`occurrences` têm equivalente direto. A página `dashboard` depende do
`analytics-service` e fica por último; se os campos não baterem, ela entra na
entrega com os que existirem, e o que falta é registrado — não inventado no
cliente.

## Fluxo de dados

```
Admin (web-admin ou app)
  └─ POST /partners ........... cria parceiro com origem
  └─ POST /products ........... cria produto
  └─ POST /products/{id}/stock-adjustments ... ajusta estoque com auditoria

Estudante (front-end-flutter)
  └─ GET /partners?active=true ...... quais seções mostrar
  └─ GET /products?partner_id=... ... catálogo daquele parceiro
  └─ POST /cart/items ............... 409 se a origem divergir
  └─ POST /orders/{id}/confirm-payment ... recebe o payload PIX pronto
```

A origem do pedido é resolvida no momento da criação, a partir do fornecedor
dos itens, e gravada no pedido. A spec C lê esse campo para simular a rota; ela
não recalcula a origem, porque o estoque pode mudar depois.

## Tratamento de erros

- Item de origem divergente no carrinho: `409` com mensagem pronta para exibir.
- Ajuste que deixaria estoque negativo: `422`, dentro da transação, sem gravar.
- Parceiro inativo em `GET /products?partner_id=`: lista vazia, não `404`. Um
  parceiro desativado durante a navegação não deve produzir tela de erro.
- Falha ao montar o PIX: `502` com mensagem genérica. O payload nunca é
  montado no cliente como recurso alternativo — seria reintroduzir o mock que
  esta spec remove.

## Testes

Toda unidade abaixo começa por um teste que falha:

- Origem única: adicionar item de outro fornecedor devolve `409`; duas adições
  concorrentes não produzem carrinho misto.
- Ajuste de estoque: grava auditoria, é atômico, recusa saldo negativo.
- Filtro de parceiro: desativar o parceiro esvazia a seção; nenhuma string
  `leroy` aparece em caminho de decisão.
- Transportadora: CRUD e transições de `status`.
- Ocorrência de transportadora: agrupamento por transportadora não quebra as
  ocorrências existentes de pedido.
- PIX: o payload emitido pelo backend é idêntico ao que o cliente gerava, para
  o mesmo pedido. O teste ancora a paridade antes de o código do cliente sair.
- Seed da Leroy: idempotente em duas passadas.
- Flutter: teste de widget da seção de parceiros com lista vazia, um parceiro,
  e erro de rede.

## Critério de pronto

1. Nenhum processo Java necessário para o painel ou para o app.
2. `web-admin` opera produtos, estoque, transportadoras e ocorrências pelo
   gateway.
3. A seção de parceiros aparece no app e responde ao flag de ativo.
4. Um pedido carrega a origem correta conforme o parceiro dos seus itens.
5. `checkout_screen.dart` não gera mais código PIX.
6. `make services-test`, `make front-analyze` e `make front-test` verdes.

## Fora de escopo

- Integração real com API da Leroy Merlin. Não existe pública, e o seed atende.
- Gateway de pagamento real.
- Pedido com múltiplas origens. Proibido por decisão, não adiado.
- Dashboard novo no `analytics-service`. O que existe é reaproveitado; o que
  faltar vira pendência registrada.
