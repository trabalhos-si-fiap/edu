# Endereço real na rota de entrega — Design

**Data:** 2026-06-14
**Módulos:** `orders`, `addresses` (leitura), `tracking` (backend); `marketplace/checkout` (Flutter)

## Problema

A rota de entrega (`GET /orders/{id}/route`) e a "Última Localização" da tela de
rastreio estão **chumbadas com um destino de São Paulo**, não o endereço do
usuário. A causa não é só uma constante: o endereço é descartado em toda a
cadeia.

- **App** (`checkout_screen.dart`): o usuário seleciona um endereço
  (`_selectedAddressId`, default = favorito), mas `checkout_service.dart` envia
  apenas `{'payment_method': ...}` no `POST /orders` — o endereço é jogado fora.
- **Backend** (`orders/models.py`, `create_order_from_cart`): o `Order` não
  guarda endereço algum.
- **`addresses/models.py`**: `Address` não tem `latitude`/`longitude`.
- **`tracking/services.py`**: como não há de onde tirar o destino, ficou chumbado
  `_MOCK_DESTINATION = (-23.561414, -46.655881)` (SP), usado em `get_order_route`
  e `predict_eta`.
- **`tracking/builders.py`**: a "Última Localização" mostra `city="Cajamar",
  state="SP"` fixos, inclusive quando o pedido é "Entregue no endereço".

Além disso, `get_order_route` hoje **não carrega o pedido nem verifica
ownership** — uma lacuna de autorização (security rule #2) que esta mudança
fecha naturalmente.

## Princípio

O pedido vira o **registro histórico do _para onde_** foi entregue — um
**snapshot** do endereço no momento do checkout, igual ao padrão já usado em
`OrderItem` (snapshot de produto). A rota e a localização derivam desse snapshot.
O **Google Directions geocodifica o endereço em texto** internamente, então não
precisamos de coluna de coordenadas nem de uma chamada de geocoding separada.

## Mudanças

### 1. Modelo `Order` (+ migration Alembic)

Adicionar colunas de snapshot em `orders_orders`, **todas nullable** (pedidos
pré-existentes e contrato leniente do checkout):

```
ship_label        String(60)   nullable
ship_zip_code     String(9)    nullable
ship_street       String(160)  nullable
ship_number       String(20)   nullable
ship_complement   String(120)  nullable
ship_neighborhood String(120)  nullable
ship_city         String(120)  nullable
ship_state        String(2)    nullable
```

Espelham os campos de `Address`. `max_length` no model (security rule #4).

### 2. Checkout (app → backend)

- **`checkout_service.dart`**: incluir `address_id` no corpo do `POST /orders`
  (envia `_selectedAddressId`). A finalização já depende de um endereço
  selecionado.
- **`OrderCreateIn`** (`orders/schemas.py`): novo campo `address_id: uuid.UUID |
  None = None` (opcional, preserva o contrato de corpo vazio).
- **`create_order_from_cart`** (`orders/services.py`): assinatura ganha
  `address_id: uuid.UUID | None`. Quando presente:
  - carrega o `Address` filtrando por `id == address_id AND user_id == user_id`
    (ownership — security rule #2); endereço de outro usuário ou inexistente →
    erro (nova exceção `AddressNotFound` no módulo orders, mapeada a **400** na
    rota — `address_id` inválido/alheio é erro do cliente);
  - copia os campos para as colunas `ship_*` do `Order`, **na mesma transação
    travada** do checkout (atomicidade — security rule #3).
  - Ausente → nenhum snapshot gravado (rota depois responde 503).

### 3. Rota — `get_order_route` (`tracking/services.py` + `routes.py`)

- A rota `GET /orders/{id}/route` passa a injetar `session` (`get_session`) e
  repassá-la ao serviço.
- `get_order_route(session, redis, user_id, order_id)`:
  - carrega o pedido via `orders_services.get_order(session, user_id, parsed_id)`
    (ownership → `OrderNotFound`); a rota mapeia `OrderNotFound` → **404**.
  - id malformado → tratado como não encontrado (404), não 500.
  - pedido **sem** `ship_street` → `RouteUnavailable` → **503** (estado de erro
    já tratado no app).
  - monta o destino em **texto** a partir do snapshot, ex.:
    `"{street}, {number}, {neighborhood}, {city} - {state}, {zip_code}, Brazil"`.
  - **origem segue o Centro de Distribuição real** (Cajamar — `_ORIGIN` coords).
  - chama o Directions com origem-coords + destino-texto.
  - o `RouteOut.destination` usa as **coords geocodificadas** devolvidas pelo
    Directions (`legs[-1].end_location`), e `label` = `ship_label` ou `ship_street`.
- **Cache:** mantém a chave `tracking:route:{order_id}`; o snapshot é imutável,
  então a rota cacheada continua válida.

### 4. Cliente Directions (`tracking/directions.py`)

- `destination` passa a aceitar `str` (endereço em texto); origem continua
  `tuple[float, float]`. O Directions aceita os dois formatos misturados.
- `DirectionsResult` ganha `destination_latitude` e `destination_longitude`,
  extraídos de `routes[0].legs[-1].end_location` (lat/lng resolvido pelo
  geocoding do Google) — usados para posicionar o pino do destino no mapa.
- A chave da API continua vindo de settings, nunca logada (security rule #5).

### 5. Última Localização (`tracking/builders.py`)

`build_order_tracking` (função pura, recebe o `Order`) passa a derivar
`TrackingLocationOut.city/state`:
- `out_for_delivery` / `delivered` → `order.ship_city` / `order.ship_state`
  (fallback para Cajamar/SP se o snapshot for nulo);
- demais status → Centro de Distribuição (Cajamar/SP), como hoje.

## Fora de escopo (deliberado)

- **`predict-eta`** (`POST /orders/{id}/predict-eta`): mantém o
  `_MOCK_DESTINATION`. **Nenhum cliente Dart o consome** (endpoint para um futuro
  app de entregador) e ele exige coordenadas para o cálculo Haversine, que esta
  proposta escolheu **não** armazenar. Fica como follow-up documentado; o
  comentário do `_MOCK_DESTINATION` será atualizado para deixar claro que serve
  só a esse endpoint placeholder.
- **Geocoding persistido / coords em `Address`**: descartado por YAGNI.

## Seeds

Os seeds que criam pedidos de demonstração precisam gravar o snapshot `ship_*`
(senão a rota responde 503 na demo). Verificar `back-end/tests/seeds` /
`back-end/app/.../seeds` no plano e popular a partir do endereço semeado do
usuário.

## TDD — testes primeiro, por camada

- **`test_tracking_directions.py`**: destino em texto vira `destination` no
  request; `DirectionsResult` extrai `destination_latitude/longitude` de
  `end_location`.
- **`orders` services**: `create_order_from_cart` grava o snapshot quando
  `address_id` é válido e do usuário; rejeita endereço de outro usuário; funciona
  sem `address_id` (sem snapshot).
- **`test_tracking_services.py`**: `get_order_route` → 404 (pedido inexistente /
  de outro usuário), 503 (sem endereço), sucesso (destino do snapshot, coords do
  Directions). Ownership enforçado.
- **`test_tracking_builders.py`**: cidade/estado da localização refletem o
  destino em `out_for_delivery`/`delivered`; CD nos demais status.
- **`orders/schemas`**: `address_id` opcional aceito e parseado.
- **Flutter**: `checkout_service` envia `address_id` no corpo (teste com
  `MockClient`).

## Riscos / Notas

- Pedidos antigos (pré-migration) e pedidos sem `address_id` não têm snapshot →
  rota 503. Aceitável: estado de erro já existe; seeds atualizados cobrem a demo.
- Custo Directions inalterado (cache por pedido mantido).
</content>
</invoke>
