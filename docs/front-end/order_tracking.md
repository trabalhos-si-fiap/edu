# Módulo Order Tracking (Flutter)

Documentação do módulo de **rastreio de pedido** do app **Edu IA** — tela de
acompanhamento, linha do tempo de etapas, última localização e o **mapa com a
rota real** entre o Centro de Distribuição e o endereço do pedido.

> O módulo consome a API real do back-end FastAPI (`GET /orders/{id}/tracking` e
> `GET /orders/{id}/route`). Cada serviço aceita `useMock: true` para desenvolver
> a tela sem backend/chave. Os dados do pedido ainda são **mockados no servidor**
> (sem persistência); o contrato já é o definitivo.

---

## 1. Visão geral

```
OrdersScreen ──"Rastrear pedido"──► OrderTrackingScreen ──"Ver mapa"──► OrderMapScreen
 (marketplace)   (arguments: id)      (timeline, kit,         (GoogleMap: 2 marcadores
                                       última localização)      + rota desenhada)
```

A tela de rastreio mostra cabeçalho, estimativa de chegada, linha do tempo de
etapas (`processed` / `in_transit` / `delivered`), kit do pedido e o card de
**Última Localização**. O botão **Ver mapa** abre uma tela separada com um
`GoogleMap` embutido que desenha a rota real por ruas (polyline vinda do
back-end, calculada via Google Directions API).

---

## 2. Estrutura de arquivos

Feature-first, em `lib/features/order_tracking/`:

```
lib/features/order_tracking/
├── domain/
│   ├── order_model.dart        # OrderModel, TrackingStep, TrackingLocation, KitItem
│   └── order_route.dart        # OrderRoute, RoutePoint (+ polylinePoints)
├── data/
│   ├── order_service.dart      # GET /orders/{id}/tracking  (OrderException)
│   ├── route_service.dart      # GET /orders/{id}/route      (RouteException)
│   └── polyline_codec.dart     # decodePolyline(String) -> List<LatLng>
└── presentation/
    ├── order_tracking_screen.dart   # tela de rastreio
    ├── order_map_screen.dart        # tela do mapa (GoogleMap)
    ├── order_provider.dart          # estado da tela de rastreio
    ├── route_provider.dart          # estado da tela do mapa
    └── widgets/
        ├── arrival_estimate_card.dart
        ├── tracking_timeline.dart
        ├── location_card.dart       # card "Última Localização" + botão "Ver mapa"
        ├── kit_content_card.dart
        ├── support_card.dart
        ├── order_error_view.dart     # estado de erro reutilizável (message + onRetry)
        └── order_format.dart
```

---

## 3. Modelo de dados

Parsing **manual** via `fromJson` (sem codegen), espelhando os schemas Pydantic
do back-end campo a campo.

| Tipo | Arquivo | Campos principais |
|------|---------|-------------------|
| `OrderModel` | `domain/order_model.dart` | `id`, `headline`, `description`, `estimatedArrival`, `steps`, `location`, `kit`, `carrier`, `mapUrl?`; getter `currentStep` |
| `TrackingStep` | `domain/order_model.dart` | `code`, `title`, `status` (`done`/`current`/`pending`), `timestamp?` |
| `TrackingLocation` | `domain/order_model.dart` | `name`, `city`, `state`, `updatedAt?`; getter `cityState` |
| `KitItem` | `domain/order_model.dart` | `name`, `subtitle?` |
| `OrderRoute` | `domain/order_route.dart` | `origin`, `destination` (`RoutePoint`), `polyline`, `distanceText`, `distanceKm`, `durationText`, `durationMinutes`; getter `polylinePoints` |
| `RoutePoint` | `domain/order_route.dart` | `label`, `latitude`, `longitude`; getter `latLng` (`LatLng`) |

`OrderRoute.polylinePoints` decodifica preguiçosamente a `polyline` codificada do
Google em `List<LatLng>` usando `decodePolyline` (algoritmo de polyline
implementado inline em `polyline_codec.dart`, sem pacote extra).

> O campo `map_url` do `OrderModel` existe no contrato mas **não é usado** neste
> fluxo (o mapa é embutido, não um link externo). Mantido para não alterar o
> contrato sem necessidade.

---

## 4. Gerência de estado

Usa o pacote **`provider`**. Cada tela tem um `ChangeNotifier` próprio,
instanciado localmente com `ChangeNotifierProvider(create: ...)` e consumido com
`Consumer`. Ambos seguem a mesma máquina de estados `loading → success | error`.

| Provider | Arquivo | Estado exposto | Ações |
|----------|---------|----------------|-------|
| `OrderProvider` | `presentation/order_provider.dart` | `state` (`OrderViewState`), `order`, `errorMessage` | `load(orderId)`, `retry()` |
| `RouteProvider` | `presentation/route_provider.dart` | `state` (`RouteViewState`), `route`, `errorMessage` | `load(orderId)`, `retry()` |

Cada provider injeta seu serviço (`OrderProvider({OrderService?})`,
`RouteProvider({RouteService?})`) — facilita testes com fakes. Erros do tipo
`OrderException`/`RouteException` viram `errorMessage` amigável; qualquer outra
exceção cai num genérico "Algo deu errado. Tente novamente.".

---

## 5. Telas e rotas

| Rota | Tela | Argumentos | Descrição |
|------|------|------------|-----------|
| `/order-tracking` | `OrderTrackingScreen` | `String orderId` | Rastreio: timeline, kit, última localização |
| `/order-map` | `OrderMapScreen` | `String orderId` | Mapa embutido com a rota origem→destino |

Argumentos chegam via `ModalRoute.of(context)?.settings.arguments as String?` e
são passados com `Navigator.pushNamed(context, rota, arguments: orderId)`.

### OrderTrackingScreen
Observa o `OrderProvider`; desenha loading / erro / sucesso. No sucesso compõe
os cards. O `LocationCard` recebe `onOpenMap`, ligado a
`Navigator.pushNamed(context, '/order-map', arguments: order.id)`.

### OrderMapScreen
Observa o `RouteProvider`. No sucesso renderiza um `GoogleMap` com:
- dois `Marker` (Centro de Distribuição e endereço de entrega);
- uma `Polyline` roxa com os `polylinePoints` decodificados;
- a câmera enquadrando os dois pontos via `CameraUpdate.newLatLngBounds`,
  disparada num `addPostFrameCallback` (o mapa pode ter tamanho zero em
  `onMapCreated` no Android).

---

## 6. Serviços HTTP

Ambos seguem o mesmo padrão: injeção de `http.Client` e `TokenStore`, header
`Authorization: Bearer <access>`, URL a partir de `ApiConfig.baseUrl`, e flag
`useMock` para devolver dados simulados.

| Serviço | Arquivo | Endpoint | Erros |
|---------|---------|----------|-------|
| `OrderService.fetchTracking(id)` | `data/order_service.dart` | `GET /orders/{id}/tracking` | `OrderException` (404 → "Pedido não encontrado") |
| `RouteService.fetchRoute(id)` | `data/route_service.dart` | `GET /orders/{id}/route` | `RouteException` (404, 503, conexão) |

> O `GET /orders/{id}/route` é **lazy**: só é chamado ao abrir o mapa. Se o
> back-end não conseguir a rota (provedor fora do ar, cota, chave ausente) ele
> responde **503** e a tela mostra o estado de erro com "Tentar novamente".

---

## 7. Configuração da chave do Google Maps (Android)

O `GoogleMap` precisa de uma chave do **Maps SDK for Android** no lado do app
(diferente da chave da Directions API, que vive **só no back-end**).

- A chave fica em `android/secrets.properties` (**gitignored** — nunca commitada):
  ```properties
  MAPS_API_KEY=sua_chave_do_maps_sdk
  ```
- `android/app/build.gradle.kts` lê o arquivo e injeta `manifestPlaceholders["MAPS_API_KEY"]`.
- `AndroidManifest.xml` referencia a chave:
  ```xml
  <meta-data
      android:name="com.google.android.geo.API_KEY"
      android:value="${MAPS_API_KEY}" />
  ```

Sem o arquivo o app **compila** normalmente (placeholder vazio); só o mapa não
renderiza. Para produção, recomenda-se uma chave do app **restrita por package
name** (`br.com.fiap.estuda_app`) e habilitada apenas para o Maps SDK.

> **iOS:** não configurado ainda. Para rodar no iOS, prover a chave em
> `AppDelegate.swift` via `GMSServices.provideAPIKey(...)` (a partir de um
> arquivo gitignored).

---

## 8. Dependências e design

- **`google_maps_flutter`** — mapa embutido (`GoogleMap`, `Marker`, `Polyline`).
- **`http`** — clientes REST (com `MockClient` de `package:http/testing.dart` nos testes).
- **`provider`** — estado das telas.

Cores via `AppColors` (`core/theme/app_colors.dart`): a rota e os destaques usam
`AppColors.purple`; cards com `borderRadius` 16–20 e sombra sutil, padrão do
projeto. Estados de loading/erro reutilizam `order_error_view.dart`.

---

## 9. Testes

`test/features/order_tracking/`:

| Arquivo | Cobre |
|---------|-------|
| `polyline_codec_test.dart` | decodifica o vetor canônico do Google; entrada vazia |
| `order_route_test.dart` | `OrderRoute.fromJson` (contrato) + `polylinePoints` |
| `route_service_test.dart` | parse 200 + header bearer; `RouteException` em não-200 (`MockClient`) |
| `route_provider_test.dart` | `load()` → success com rota; `RouteException` → estado de erro |

Ver também: [Arquitetura](archtecture.md) · [Guia Visual](visual_guide.md) ·
[Marketplace](marketplace.md). Back-end: [Start Here](../back-end/start-here.md) §13.
