# Order Tracking — "Ver mapa" com rota real embutida

**Data:** 2026-06-13
**Status:** Design aprovado, pronto para plano de implementação

## Objetivo

Fazer o botão "Ver mapa" da tela de Acompanhamento de Pedido
(`order_tracking`) abrir um mapa interativo **embutido no app**, mostrando a
**rota real por ruas** entre o Centro de Distribuição (origem) e o endereço de
destino do pedido.

Hoje o botão está ligado a um callback vazio (`onOpenMap: () {}`) e o "mapa"
exibido na tela é apenas um desenho estilizado (`CustomPaint`).

## Decisões fechadas (brainstorming)

| Decisão | Escolha |
|---|---|
| Onde o mapa aparece | Embutido no app (`google_maps_flutter`) |
| Traçado da rota | Rota real por ruas (Google **Directions API**) |
| Onde a Directions é chamada | **No backend** (chave server-side) |
| Quando rotear | **Lazy** — só ao tocar "Ver mapa" |
| Coords origem/destino | **Mockadas** por enquanto (pedidos ainda não têm persistência) |
| Cache | Resultado da rota cacheado em Redis por `order_id` |

## Chaves de API

O usuário ativou a Maps Platform no GCP e tem **uma** chave
(`GOOGLE_MAPS_API_PLATAFORM`), que será colocada em `back-end/.env`.

- **Dev/agora:** a mesma chave é usada nos dois lados (backend chama Directions;
  app renderiza com Maps SDK) para destravar o desenvolvimento.
- **Produção (recomendação):** separar em **duas** chaves restritas:
  - **Cliente (app):** embarcada e extraível → restringir por *package name /
    bundle id* e habilitar **apenas** Maps SDK for Android / iOS.
  - **Servidor (backend):** restringir por IP e habilitar **apenas** Directions
    API.

Nenhuma chave hardcoded no código (regra de segurança nº 5): backend lê de
`settings`; app lê do `AndroidManifest.xml` / `AppDelegate` / `Info.plist`.
Sem as chaves, o mapa não renderiza, mas o restante do app segue normal.

## Backend

### Novo endpoint

```
GET /orders/{order_id}/route
```

- Protegido por `Depends(get_current_user)` (regra nº 2).
- `order_id` limitado (`min_length=1, max_length=64`), igual aos endpoints
  existentes do módulo `tracking`.
- Chamado apenas quando o usuário abre o mapa.

### Contrato de resposta (`RouteOut`)

```
origin:        { label: str, latitude: float, longitude: float }
destination:   { label: str, latitude: float, longitude: float }
polyline:      str          # overview_polyline codificada do Google
distance_text: str          # ex.: "32 km"
distance_km:   float
duration_text: str          # ex.: "48 min"
duration_minutes: int
```

Campos explícitos no schema Pydantic (regra nº 6). `latitude`/`longitude`
reaproveitam os bounds `GeoPoint` já existentes em `schemas.py`.

### Peças novas / alteradas

- **`tracking/directions.py`** (novo) — cliente da Directions API via `httpx`
  (já é dependência). Recebe origem e destino, retorna polyline + distância +
  duração. Requisitos:
  - `timeout` explícito na chamada HTTP.
  - Tratamento de erro: timeout, status != OK da API, resposta sem rota →
    levanta exceção de domínio (nova em `exceptions.py`, ex.: `RouteUnavailable`).
  - Chave lida de `settings.GOOGLE_MAPS_API_PLATAFORM`.
  - Sem logar a chave nem dados sensíveis (regra nº 5); usar `loguru`.
- **`tracking/services.py`** — `get_order_route(user_id, order_id)`:
  - Origem = Centro de Distribuição (coords mockadas, Cajamar/SP).
  - Destino = reuso de `_MOCK_DESTINATION` (a "casa do cliente"; passa a
    representar o endereço cadastrado no pedido).
  - Consulta o cache Redis; em cache miss, chama `directions.py`, mapeia para
    `RouteOut` e grava no cache.
- **Cache Redis** — origem e destino são fixos por pedido, logo a rota não muda.
  Chave por `order_id`. **Paga a Directions só na primeira abertura** de cada
  pedido. (Redis já está no stack.)
- **`tracking/routes.py`** — registra a nova rota.
- **`core/config.py`** — adiciona `GOOGLE_MAPS_API_PLATAFORM: str | None = None`.

### Testes (TDD, escritos primeiro)

- `directions.py`: `httpx` mockado — sucesso, timeout, status != OK, resposta
  sem rota.
- `services.py`: monta origem/destino corretos; usa cache (miss chama a API,
  hit não chama).
- endpoint: auth obrigatória (401 sem token), 200 com formato esperado, 404
  quando o pedido não existe (quando a persistência existir).

## Frontend (Flutter)

### Dependências

- `pubspec.yaml`: adicionar `google_maps_flutter`.
- Decodificação da polyline: helper próprio (~20 linhas, algoritmo de polyline
  do Google) para manter as dependências enxutas — sem pacote extra.

### Peças novas / alteradas

- **`order_tracking/data/route_service.dart`** (novo) — `RouteService.fetchRoute(orderId)`
  chama `GET /orders/{id}/route`, mesmo padrão de auth/erro do `OrderService`
  (inclui `useMock` para desenvolver sem chave/backend).
- **`order_tracking/domain/order_route.dart`** (novo) — modelo `OrderRoute`
  (origin, destination, polyline, distância, duração), parsing manual com
  `fromJson`/`toJson`, no mesmo estilo de `order_model.dart`.
- **`order_tracking/presentation/order_map_screen.dart`** (novo) — tela com
  `GoogleMap`:
  - dois marcadores (Centro de Distribuição e destino);
  - `Polyline` decodificada;
  - câmera enquadrando os dois pontos;
  - estados de loading/erro reaproveitando os widgets existentes do módulo.
- **`main.dart`** — registra a rota nomeada `/order-map`, recebendo `orderId`
  via `arguments` (mesmo padrão de `/order-tracking`).
- **`order_tracking_screen.dart`** — troca `onOpenMap: () {}` por
  `Navigator.pushNamed(context, '/order-map', arguments: order.id)`.

### Configuração de plataforma

- Android: chave do Maps SDK no `AndroidManifest.xml` (+ permissões já
  presentes para apps de mapa, se necessário).
- iOS: chave no `AppDelegate`/`Info.plist`.

### Testes

- `RouteService`: parsing, headers de auth, caminhos de erro.
- Parsing do `OrderRoute`.
- Decoder de polyline (vetores conhecidos do algoritmo do Google).

## Fora de escopo (YAGNI)

- O card estilizado (`_MapLinesPainter`) continua como preview na tela de
  tracking — **não** vira mapa real (evita custo de render do Maps SDK).
- O campo `map_url` fica órfão para este fluxo; **não** será removido agora
  para não alterar contrato sem necessidade.
- O endpoint `predict-eta` segue intacto — responsabilidade distinta (ETA, não
  desenho de rota).
- Persistência real de pedidos / endereços: quando existir, apenas os builders
  privados em `services.py` mudam para buscar coords reais filtradas por
  `user_id`; o contrato do endpoint e o app permanecem.

## Sequência de implementação (alto nível)

1. Backend: setting + schema `RouteOut` + exceção.
2. Backend: cliente `directions.py` (TDD).
3. Backend: service `get_order_route` com cache (TDD).
4. Backend: rota + testes de endpoint.
5. Flutter: modelo `OrderRoute` + decoder de polyline (TDD).
6. Flutter: `RouteService` (TDD).
7. Flutter: tela `order_map_screen` + rota nomeada + wiring do botão.
8. Config de plataforma (Android/iOS) + verificação manual end-to-end.
