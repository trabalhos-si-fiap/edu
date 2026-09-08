# Estado deste painel

Veio de `trabalhos-si-fiap/mobile_hybrid_app`, pasta `web-angular/`, trazido
por `git subtree` na spec A (2026-09-07) com o histórico preservado.

## Não funciona ainda

Os serviços Angular apontam para `localhost:8080/api/v1` — a API Java, que a
spec A eliminou. **O painel não sobe contra este backend.**

A troca para o api-gateway (porta 8100) é escopo da
[spec B](../docs/superpowers/specs/2026-09-07-spec-b-parceiros-estoque-transportadora-design.md),
e depende de endpoints de estoque e transportadora que ainda não existem no
`commerce-service`.

Enquanto isso, `web-admin` não está no `docker-compose.yml`.

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
