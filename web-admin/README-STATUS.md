# Estado deste painel

Veio de `trabalhos-si-fiap/mobile_hybrid_app`, pasta `web-angular/`, trazido
por `git subtree` na spec A (2026-09-07) com o histórico preservado.

**Para ver a autoria original:** `git log -- web-admin/src/...` mostra pouca
coisa — os arquivos viviam em `web-angular/src/...` no repositório 2, e o
commit do subtree os moveu um nível acima, então o `git log` filtrado pelo
caminho novo não enxerga o histórico anterior à mudança de caminho. `git
blame` atravessa a mudança normalmente, e `git shortlog -sn
14af3a34dcc1e983d720d78fc5ed82c2a9ac65d7` lista os autores originais do
painel.

## Como roda

`cd web-admin && npm start` (`ng serve`, em `http://localhost:4200`) e entre
com a conta de admin de demonstração (`admin@demo.edu`, ver
[demo-accounts.md](../docs/back-end/demo-accounts.md)).

Os serviços Angular chamam caminhos relativos, `/api/...`. Em
desenvolvimento, o `proxy.conf.json` repassa `/api` para o **api-gateway** em
`http://localhost:8100`, que roteia cada prefixo para o microserviço dono. Não
existe mais `localhost:8080` nem `/api/v1`: essa era a API Java, eliminada na
spec A; o painel passou a falar com o gateway na
[spec B](../docs/superpowers/specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md).

O proxy só vale para o `ng serve`. Quem servir o `dist/` do `npm run build`
precisa de um proxy reverso que mande `/api` para o gateway.

`web-admin` não está no `docker-compose.yml`.

## Telas

| Rota | Tela | Rotas do backend (via gateway) |
|---|---|---|
| `/login` | Login | `POST /api/auth/login` |
| `/dashboard` | Dashboard | `GET /api/analytics/executive-summary`, `GET /api/partners`, `GET /api/carriers` |
| `/pedidos` | Pedidos: lista do mais novo para o mais antigo, filtro por status, confirmar pagamento de pedido `CRIADO`/`CONFIRMADO` | `GET /api/admin/orders`, `PATCH /api/admin/orders/{id}/confirm-payment` |
| `/parceiros` | Parceiros: contato, origem de expedição, quantidade de produtos, ativo/inativo (somente leitura) | `GET /api/partners`, `GET /api/admin/inventory` |
| `/produtos-estoque` | Produtos e estoque: catálogo, criação/edição de produto, ajuste de estoque com motivo | `/api/products`, `/api/admin/inventory` |
| `/transportadoras` | Transportadoras: diretório, criação/edição, ativar/inativar | `/api/carriers`, `GET /api/occurrences` |
| `/carregamentos` | Carregamentos: criação com credencial, atribuição de pedido | `/api/shipments` |
| `/ocorrencias` | Ocorrências de transportadora: filtros e encerramento | `/api/occurrences` |

## O que veio junto e foi podado

- `api/` (Spring Boot) — não veio. A spec B usa o histórico do repositório
  arquivado como referência das regras de negócio.
- `mobile-flutter/` — não veio. Cada tela tem equivalente em
  `front-end-flutter/lib/features/`.

### Equivalência tela a tela

`mobile-flutter/lib` tinha 25 arquivos `.dart`. Vinte e quatro têm o mesmo
caminho sob `front-end-flutter/lib`:

| `mobile-flutter/lib/` | `front-end-flutter/lib/` |
|---|---|
| `core/network/app_http.dart` | idêntico, byte a byte |
| `core/network/{api_config,auth_http_client,session_store,token_refresher,token_store}.dart` | mesmo caminho |
| `core/theme/{app_colors,app_theme}.dart` | mesmo caminho |
| `core/utils/{currency,jwt_utils}.dart` | mesmo caminho |
| `features/admin/data/admin_api.dart` | mesmo caminho |
| `features/admin/presentation/{admin_analytics_screen,admin_dashboard_screen}.dart` | mesmo caminho |
| `features/admin/presentation/widgets/{admin_scaffold,admin_widgets}.dart` | mesmo caminho |
| `features/auth/` (5 telas: `data/auth_api.dart` + `presentation/{forgot_password,login,register,reset_password}_screen.dart`) | mesmo caminho |
| `features/logistics/presentation/{delivery_queue_screen,picking_queue_screen}.dart` | mesmo caminho, com divergência que só existe porque acompanhava o contrato Java |
| `features/notifications/data/messaging_service.dart` | mesmo caminho |
| `main.dart` | mesmo caminho |

A única exceção é `features/admin/domain/dashboard.dart`. O `edu` tem, no
lugar, `features/admin/domain/analytics.dart`. O próprio docstring do
`dashboard.dart` explica a troca: ele espelha os DTOs da Edu Admin API
(Spring Boot, `api/`) e **substituiu** `analytics.dart`, que espelhava o
`analytics-service` em Python — não usado pelo backend do fork. Neste
repositório o backend é justamente o `analytics-service` em Python, então
`analytics.dart` é o arquivo correto aqui, e `dashboard.dart` modela um
backend que a spec A elimina. Nada se perde — é uma ausência deliberada.

O `edu` tem, além dessas 25: `picking_screen`, `delivery_detail_screen`,
`tracking_screen` e `widgets/logistics_scaffold` em `features/logistics/`,
além de mais de uma dezena de outras features que o fork nunca teve.
