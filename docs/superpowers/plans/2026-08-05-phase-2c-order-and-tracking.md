# Fase 2 — Bloco C: pedido, checkout, rastreio e rota

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o `commerce-service` servir o ciclo de pedido que o app consome — listagem, checkout a partir do carrinho, recompra, rastreio, rota e ETA — sobre a máquina de estados real de staff que já existe, sem inventar um simulador.

**Architecture:** `pedidos`/`pedido_itens` viram `orders`/`order_items` com PK UUID, os oito `ship_*` do legacy e o snapshot de produto. A máquina interna ganha `CONFIRMADO` e passa a ter **nove** estados; o contrato expõe **seis**. O checkout lê o carrinho (não o preço que o cliente mandou) e busca o endereço no `auth-users-service` por HTTP com repasse do bearer do aluno. O rastreio é uma função pura sobre o status do contrato.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, pytest, ruff, uv, PostgreSQL, Redis, MinIO, RabbitMQ, Google Directions API, Flutter/Dart.

**Spec:** [`docs/superpowers/specs/2026-08-04-microservices-migration-phase-2-design.md`](../specs/2026-08-04-microservices-migration-phase-2-design.md) — bloco C.
**Depende de:** [bloco A](2026-08-05-phase-2a-security-and-fleet.md) **e** [bloco B](2026-08-05-phase-2b-catalog-and-cart.md), os dois concluídos. Em especial:
- A/task 19: `get_current_user_id` é o nome canônico da dependência.
- A/task 22: `google_maps_api_key` foi **deixado de pé** no `commerce-service/app/config.py` esperando este bloco. A task C9 é quem passa a lê-lo.
- A/task 25 e B/task B4: a contagem de linhas do `commerce_db` foi medida. A task C0 a refaz.
- B/task B0: a divergência 403-vs-401 já está registrada. **Não a redescubra.**
- B/task B7: `app/services/auth_client.py` já existe com `get_me`. A task C5 acrescenta `get_address` **ao mesmo arquivo**.
- B/task B8: `carts`/`cart_items` existem, com `services.montar_cart_out` e `services.adicionar_item`.

---

## Global Constraints

**Do `CLAUDE.md`:**

1. Nunca concatenar input do usuário em SQL — sempre ORM com bind params.
2. Todo endpoint com controle de acesso explícito **e** filtro de ownership. Aqui isso é literal: **toda** query de pedido filtra por `user_id`.
3. Read→write em recurso compartilhado é atômico: `with_for_update()` ou expressão SQL atômica.
4. Todo input com limite: `max_length` no model **e** no schema; listagem paginada.
5. Nenhum segredo no código. Nunca logar token. `loguru.logger`, nunca `print()`.
6. Schemas com campos explícitos — `PedidoOut` já omite `separador_id`/`entregador_id` de propósito; mantenha.
7. Comparação de segredo com `hmac.compare_digest()`.
8. TDD sem exceção: Red → Green → Refactor.
9. Conventional Commits, um commit por unidade lógica, `git diff --staged` antes de cada commit.
10. `ruff check` e `ruff format` limpos antes de commitar.

**Do backlog da fase 1:**

11. **Todo teste de regressão precisa ser provado quebrando o que ele trava.**
12. **Nunca alimentar o teste com a própria constante da implementação.**
13. **Desconfie do instrumento antes de concluir que o código está limpo.**
14. **Monkeypatch no módulo que define, não no que importa.**
15. **`default=` do SQLAlchemy é client-side** — `server_default=` junto.
16. **Comentário que era verdade e virou mentira** — este bloco reescreve a máquina de estados, e os docstrings de `separacao.py`/`entrega.py` descrevem a antiga em detalhe. Releia-os.
17. **`docker ps` reporta saudável container que não serve.**

**Deste bloco:**

18. **Réplica exata é o critério, e ele é binário.** Toda task de rota começa portando o arquivo de teste do legacy.
19. **Reproduzir as inconsistências é o trabalho.** `GET /orders` devolve **array puro**, não envelope — ao contrário de `/products` e `/cart`. Não "arrume".
20. **Nunca mude uma asserção portada sem registrar por quê.**
21. **As 69 suítes atuais do commerce são atualizadas, não removidas.** Elas travam o comportamento de staff que a tradução não pode mudar. Se uma delas quebrar e você não souber dizer qual mudança de comportamento a quebrou, pare.
22. **Dois carve-outs declarados, os dois para a fase 3:** `test_lifecycle.py` e `test_status_pipeline.py` do legacy **não** são portados — o simulador Celery é fase 3. Até lá, um pedido criado pelo app só anda se alguém trabalhar a fila de separação. Registre isso no relatório de cada task que o toque.

---

## File Structure

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `commerce-service/app/services/status_pedido.py` | 9 estados internos, `TRANSICOES_VALIDAS`, mapeamento 9→6 | C1 |
| `commerce-service/app/models/pedido.py` | `Order`/`OrderItem`/`PedidoStatusHistorico` | C2, C3, C4 |
| `commerce-service/app/schemas/pedido.py` | `OrderOut`/`OrderItemOut` (app) + `PedidoStaffOut` (staff) | C2, C4, C6 |
| `commerce-service/app/routers/pedidos.py` | `/orders` do aluno — reescrito | C6, C7, C8 |
| `commerce-service/app/routers/rastreio.py` | **novo** — tracking, route, predict-eta | C8, C9 |
| `commerce-service/app/routers/separacao.py` · `entrega.py` · `admin.py` | acompanham o rename e `CONFIRMADO` | C1, C2 |
| `commerce-service/app/services/pedidos.py` | **novo** — checkout, listagem, rebuy | C6, C7 |
| `commerce-service/app/services/rastreio_builder.py` | **novo** — `build_order_tracking` puro | C8 |
| `commerce-service/app/services/directions.py` | **novo** — cliente Google Directions | C9 |
| `commerce-service/app/services/rastreio_routing.py` | **novo** — Haversine/ETA | C9 |
| `commerce-service/app/schemas/rastreio.py` | **novo** — `OrderTrackingOut`, `RouteOut`, `ETAPredictionOut` | C8, C9 |
| `commerce-service/app/services/auth_client.py` | ganha `get_address` | C5 |
| `commerce-service/app/config.py` | `tracking_*`; `google_maps_api_key` finalmente lido | C9 |
| `auth-users-service/app/routers/addresses.py` | **rota nova** `GET /auth/addresses/{id}` | C5 |
| `commerce-service/app/routers/ocorrencias.py` | eventos com `pedido_id` UUID string | C10 |
| `analytics-service/app/events/consumer.py` · `notification-service/app/events/consumer.py` | acompanham a troca de tipo | C10 |
| `notification-service/app/models/notificacao.py` | `pedido_id` deixa de ser Integer | C10 |
| `front-end-flutter/lib/features/marketplace/domain/order_summary.dart` | caso `cancelled` | C11 |
| `front-end-flutter/lib/features/marketplace/presentation/orders_provider.dart` | pedido cancelado sai dos ativos | C11 |

---

## Helpers de teste compartilhados

Estas funções aparecem em mais de uma task deste plano. Escreva-as **uma vez**, na task que primeiro precisar delas, e reaproveite depois. `headers_for(role, sub)`, `_seed_pedido(db_session, status, **overrides)`, `_seed_produto(db_session)`, `_seed_estoque(db_session)` e as constantes `ALUNO`/`PICKER_A`/`PICKER_B`/`DELIVERER_A`/`ADMIN` **já existem** em `commerce-service/tests/` — não os reescreva.

Ponha as quatro abaixo em `commerce-service/tests/helpers_pedido.py` (arquivo novo) e importe-as de lá, para não duplicar em cinco arquivos de teste:

```python
"""Helpers de seed compartilhados pelas suítes de pedido do bloco C."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from app.models.pedido import Order, OrderItem, PedidoStatusHistorico
from app.services.status_pedido import StatusPedido

ALUNO = "00000000-0000-0000-0000-000000000001"  # sub padrão de headers_for("student")


async def _seed_pedido_com_endereco(db_session, *, user_id: str = ALUNO, **overrides) -> Order:
    """Pedido com o snapshot `ship_*` preenchido.

    Os valores são os que `test_staff_view_composes_the_address_from_the_snapshot`
    (task C4) asserta literalmente — mudar um aqui quebra aquele teste, que é
    o comportamento certo.
    """
    dados = {
        "user_id": uuid.UUID(user_id),
        "status": StatusPedido.CRIADO.value,
        "total": Decimal("100.00"),
        "payment_method": "PIX",
        "ship_label": "Casa",
        "ship_zip_code": "01310-100",
        "ship_street": "Av. Paulista",
        "ship_number": "1000",
        "ship_complement": "ap 42",
        "ship_neighborhood": "Bela Vista",
        "ship_city": "São Paulo",
        "ship_state": "SP",
    }
    dados.update(overrides)
    pedido = Order(**dados)
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _historico_do_pedido(db_session, order_id) -> list[PedidoStatusHistorico]:
    resultado = await db_session.execute(
        select(PedidoStatusHistorico)
        .where(PedidoStatusHistorico.order_id == order_id)
        .order_by(PedidoStatusHistorico.criado_em.asc(), PedidoStatusHistorico.id.asc())
    )
    return list(resultado.scalars().all())


def _order_falso(*, status: str, **overrides) -> SimpleNamespace:
    """Pedido em memória para `build_order_tracking`, que é uma função PURA.

    `SimpleNamespace` de propósito, não um `Order` do ORM: o construtor do
    rastreio não toca banco, e testá-lo contra o ORM arrastaria a fixture de
    sessão para uma suíte que não precisa dela — foi por isso que o legacy
    separou `builders.py` de `services.py`.
    """
    base = {
        "id": uuid.uuid4(),
        "status": status,
        "created_at": datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        "status_updated_at": datetime(2026, 8, 2, 9, 30, tzinfo=UTC),
        "ship_city": "São Paulo",
        "ship_state": "SP",
        "ship_label": "Casa",
        "items": [SimpleNamespace(product_name="Guia de Redação Nota 1000")],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


async def _seed_item(db_session, pedido: Order, **overrides) -> OrderItem:
    dados = {
        "order_id": pedido.id,
        "product_id": uuid.uuid4(),
        "product_name": "Guia de Redação Nota 1000",
        "unit_price": Decimal("49.90"),
        "quantity": 2,
        "image_url": "products/seed-0.jpg",
        "rating_avg": 4.5,
        "rating_count": 128,
    }
    dados.update(overrides)
    item = OrderItem(**dados)
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item
```

No `auth-users-service` (task C5), `tests/helpers.py` **já existe** — leia-o antes de escrever `_seed_endereco`. Se ele não tiver um seed de endereço, acrescente:

```python
async def _seed_endereco(db_session, user_id, **overrides) -> Address:
    dados = {
        "user_id": user_id,
        "label": "Casa",
        "zip_code": "01310-100",
        "street": "Av. Paulista",
        "number": "1000",
        "complement": "ap 42",
        "neighborhood": "Bela Vista",
        "city": "São Paulo",
        "state": "SP",
    }
    dados.update(overrides)
    endereco = Address(**dados)
    db_session.add(endereco)
    await db_session.commit()
    await db_session.refresh(endereco)
    return endereco
```

---

### Task C0: portão de entrada

- [ ] **Step 1: Confirme que os blocos A e B estão de pé**

Run:
```bash
cd /home/elias/programming/fiap/estuda_app
git log --oneline -30
make services-test
```

Expected: PASS nos oito alvos. O log tem que mostrar os commits de A e B.

- [ ] **Step 2: Refaça a contagem de linhas**

Run:
```bash
cd back-end && make stack-up
docker compose exec -T postgres psql -U edu -d commerce_db -c "
  SELECT 'pedidos' AS t, count(*) FROM pedidos
  UNION ALL SELECT 'pedido_itens', count(*) FROM pedido_itens
  UNION ALL SELECT 'pedido_status_historico', count(*) FROM pedido_status_historico
  UNION ALL SELECT 'ocorrencias', count(*) FROM ocorrencias;"
```

- **Todas 0:** siga. As migrations de C3 podem ser reconstrução declarada.
- **Qualquer > 0:** pare e leve ao autor do spec. Alguém rodou um seed ou exercitou as rotas de staff; a migration vira preservadora e o custo do bloco sobe.

> A task B10 rodou `make services-seed`, que popula **`products`**, não `pedidos`. Se `pedidos` tiver linha, foi uso manual — investigue de onde veio antes de apagar.

- [ ] **Step 3: Releia o relatório da task B0**

A divergência 403-vs-401 vale para as rotas deste bloco também. Tenha a contagem à mão: os testes de `TestAuthRequired` de `orders` e `tracking` a repetem.

- [ ] **Step 4: Relate.** Nada a commitar.

---

### Task C1: nove estados internos, seis no contrato

`CONFIRMADO` entra entre `CRIADO` e `AGUARDANDO_SEPARACAO`. `CANCELADO` já existe. E nasce a função que traduz o estado interno no valor que o app lê.

**Files:**
- Modify: `back-end/commerce-service/app/services/status_pedido.py`
- Modify: `back-end/commerce-service/app/routers/admin.py` (`confirmar_pagamento`)
- Test: `back-end/commerce-service/tests/test_status_pedido.py` (novo), `tests/test_admin_routes.py`

**Interfaces:**
- Produces:
  - `StatusPedido` ganha `CONFIRMADO = "CONFIRMADO"`; `TRANSICOES_VALIDAS` ganha `CRIADO → [CONFIRMADO, CANCELADO]` e `CONFIRMADO → [AGUARDANDO_SEPARACAO, CANCELADO]`.
  - `STATUS_CONTRATO: dict[StatusPedido, str]` — o mapeamento 9→6.
  - `status_do_contrato(status_interno: str) -> str`.
  - `StatusContrato: StrEnum` com `PENDING`, `CONFIRMED`, `SEPARATING`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED`.
  - `FLUXO_CONTRATO: tuple[StatusContrato, ...]` — a progressão dos cinco não-cancelados, na ordem, usada pelo construtor do rastreio.

> **Decisão que o spec deixou em aberto — leia antes de implementar.**
> O spec diz que `CONFIRMADO` entra entre `CRIADO` e `AGUARDANDO_SEPARACAO` e que "quem o dispara já existe: `confirmar_pagamento`". Ele **não** diz quem avança de `CONFIRMADO` para `AGUARDANDO_SEPARACAO`. Sem o simulador Celery (fase 3), deixar `CONFIRMADO` como estado de repouso deixaria todo pedido preso atrás de um segundo clique manual do admin, e a fila de separação (`GET /picking/queue`, que seleciona `AGUARDANDO_SEPARACAO`) ficaria sempre vazia.
>
> **Esta task encadeia as duas transições dentro de `confirmar_pagamento`**, seguindo o precedente que `finalizar_separacao` já estabelece (`SEPARADO` → `AGUARDANDO_COLETA` na mesma chamada). Consequência a registrar: `confirmed` aparece no `GET /orders/{id}/status-history` mas **nunca é o status corrente**. Isso não quebra a tela — `_step_status` do construtor do rastreio marca o passo `confirmed` como `done` quando o pedido já está em `separating`. É a mesma situação do `pending` no legacy, que o pipeline Celery atravessa em segundos.

- [ ] **Step 1: Escreva o teste que falha**

Crie `back-end/commerce-service/tests/test_status_pedido.py`:

```python
import pytest

from app.services.status_pedido import (
    FLUXO_CONTRATO,
    StatusContrato,
    StatusPedido,
    status_do_contrato,
    validar_transicao,
)


def test_confirmado_sits_between_criado_and_aguardando_separacao():
    assert validar_transicao(StatusPedido.CRIADO, StatusPedido.CONFIRMADO)
    assert validar_transicao(StatusPedido.CONFIRMADO, StatusPedido.AGUARDANDO_SEPARACAO)
    # O atalho antigo some: o pagamento passa a ser um estado, não um pulo.
    assert not validar_transicao(StatusPedido.CRIADO, StatusPedido.AGUARDANDO_SEPARACAO)


def test_cancelado_is_reachable_from_confirmado():
    assert validar_transicao(StatusPedido.CONFIRMADO, StatusPedido.CANCELADO)


@pytest.mark.parametrize(
    ("interno", "contrato"),
    [
        ("CRIADO", "pending"),
        ("CONFIRMADO", "confirmed"),
        ("AGUARDANDO_SEPARACAO", "separating"),
        ("EM_SEPARACAO", "separating"),
        ("SEPARADO", "separating"),
        ("AGUARDANDO_COLETA", "out_for_delivery"),
        ("EM_TRANSITO", "out_for_delivery"),
        ("ENTREGUE", "delivered"),
        ("CANCELADO", "cancelled"),
    ],
)
def test_every_internal_state_maps_to_a_contract_value(interno, contrato):
    assert status_do_contrato(interno) == contrato


def test_the_mapping_covers_every_internal_state():
    """Um estado interno novo sem entrada no mapa não pode passar em silêncio:
    ele viraria `pending` por acidente e a tela mostraria um pedido ativo."""
    for estado in StatusPedido:
        assert status_do_contrato(estado.value) is not None


def test_the_contract_has_exactly_six_values():
    assert len(StatusContrato) == 6


def test_the_visible_flow_excludes_cancelled():
    """A timeline tem quatro passos visíveis. `cancelled` não é um passo — é a
    saída do fluxo, e um `FLUXO_CONTRATO.index(cancelled)` estouraria."""
    assert StatusContrato.CANCELLED not in FLUXO_CONTRATO
    assert FLUXO_CONTRATO == (
        StatusContrato.PENDING,
        StatusContrato.CONFIRMED,
        StatusContrato.SEPARATING,
        StatusContrato.OUT_FOR_DELIVERY,
        StatusContrato.DELIVERED,
    )
```

Em `tests/test_admin_routes.py`:

```python
async def test_confirm_payment_lands_the_order_in_the_picking_queue(
    client, db_session, _stub_publish_event
):
    """Confirmar pagamento passa por CONFIRMADO e para em AGUARDANDO_SEPARACAO.

    Parar em CONFIRMADO deixaria a fila de separação sempre vazia — não há
    simulador na fase 2 para avançar sozinho."""
    pedido = await _seed_pedido(db_session, status=StatusPedido.CRIADO.value)

    response = await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value

    historico = [h.status for h in await _historico_do_pedido(db_session, pedido.id)]
    assert historico == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]

    chaves_status = [
        payload["status"] for key, payload in _stub_publish_event if key == "order.status_changed"
    ]
    assert chaves_status == [
        StatusPedido.CONFIRMADO.value,
        StatusPedido.AGUARDANDO_SEPARACAO.value,
    ]
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_status_pedido.py tests/test_admin_routes.py -k "confirmado or contract or confirm_payment or visible_flow" -v`

Expected: `ImportError` em `FLUXO_CONTRATO`/`StatusContrato`/`status_do_contrato`; e `assert 'AGUARDANDO_SEPARACAO' == 'CONFIRMADO'` no histórico.

- [ ] **Step 3: Reescreva `status_pedido.py`**

```python
from enum import StrEnum


class StatusPedido(StrEnum):
    """Estados INTERNOS do pedido — o vocabulário da operação de staff.

    São nove. O contrato público expõe seis (ver `StatusContrato` abaixo):
    a operação distingue "aguardando separação" de "em separação" de
    "separado", e o aluno não precisa dessa granularidade.
    """

    CRIADO = "CRIADO"
    CONFIRMADO = "CONFIRMADO"
    AGUARDANDO_SEPARACAO = "AGUARDANDO_SEPARACAO"
    EM_SEPARACAO = "EM_SEPARACAO"
    SEPARADO = "SEPARADO"
    AGUARDANDO_COLETA = "AGUARDANDO_COLETA"
    EM_TRANSITO = "EM_TRANSITO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class StatusContrato(StrEnum):
    """Estados PÚBLICOS — o que `GET /orders` devolve e o Flutter lê.

    São exatamente os cinco do legacy mais `cancelled`. O sexto existe
    porque o enum do Flutter tem `default: return OrderSummaryStatus.pending`:
    sem um valor próprio, um pedido cancelado apareceria como "Pendente", no
    passo 0 do stepper, para sempre. E `CANCELADO` é alcançável por decisão
    do próprio aluno (resolução `cancelar_pedido` de uma ocorrência).
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEPARATING = "separating"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Progressão VISÍVEL, na ordem. `CANCELLED` fica de fora de propósito: ele não
# é um passo da timeline, é a saída do fluxo. Um `.index(CANCELLED)` no
# construtor do rastreio estouraria `ValueError` — ver rastreio_builder.py.
FLUXO_CONTRATO: tuple[StatusContrato, ...] = (
    StatusContrato.PENDING,
    StatusContrato.CONFIRMED,
    StatusContrato.SEPARATING,
    StatusContrato.OUT_FOR_DELIVERY,
    StatusContrato.DELIVERED,
)

# Transições válidas: de onde -> pra onde.
#
# CONFIRMADO entra entre CRIADO e AGUARDANDO_SEPARACAO: o pagamento passa a
# ser um estado observável, não um pulo. `confirmar_pagamento` (admin.py)
# encadeia as duas transições, porque não há simulador na fase 2 e parar em
# CONFIRMADO deixaria a fila de separação sempre vazia.
#
# CANCELADO é alcançável de vários estágios porque ocorrências (falta de
# estoque, atraso de entrega) podem levar o aluno a cancelar o pedido em
# quase qualquer ponto do fluxo, exceto após a entrega já confirmada.
TRANSICOES_VALIDAS: dict[StatusPedido, list[StatusPedido]] = {
    StatusPedido.CRIADO: [StatusPedido.CONFIRMADO, StatusPedido.CANCELADO],
    StatusPedido.CONFIRMADO: [StatusPedido.AGUARDANDO_SEPARACAO, StatusPedido.CANCELADO],
    StatusPedido.AGUARDANDO_SEPARACAO: [StatusPedido.EM_SEPARACAO, StatusPedido.CANCELADO],
    StatusPedido.EM_SEPARACAO: [StatusPedido.SEPARADO, StatusPedido.CANCELADO],
    StatusPedido.SEPARADO: [StatusPedido.AGUARDANDO_COLETA, StatusPedido.CANCELADO],
    StatusPedido.AGUARDANDO_COLETA: [StatusPedido.EM_TRANSITO, StatusPedido.CANCELADO],
    StatusPedido.EM_TRANSITO: [StatusPedido.ENTREGUE, StatusPedido.CANCELADO],
    StatusPedido.ENTREGUE: [],
    StatusPedido.CANCELADO: [],
}

# Nove internos -> seis do contrato. Exaustivo por construção: o teste
# `test_the_mapping_covers_every_internal_state` percorre `StatusPedido`
# inteiro, então um estado novo sem entrada aqui quebra a suíte em vez de
# virar "pending" por acidente — que faria a tela mostrar um pedido ativo.
STATUS_CONTRATO: dict[StatusPedido, StatusContrato] = {
    StatusPedido.CRIADO: StatusContrato.PENDING,
    StatusPedido.CONFIRMADO: StatusContrato.CONFIRMED,
    StatusPedido.AGUARDANDO_SEPARACAO: StatusContrato.SEPARATING,
    StatusPedido.EM_SEPARACAO: StatusContrato.SEPARATING,
    StatusPedido.SEPARADO: StatusContrato.SEPARATING,
    StatusPedido.AGUARDANDO_COLETA: StatusContrato.OUT_FOR_DELIVERY,
    StatusPedido.EM_TRANSITO: StatusContrato.OUT_FOR_DELIVERY,
    StatusPedido.ENTREGUE: StatusContrato.DELIVERED,
    StatusPedido.CANCELADO: StatusContrato.CANCELLED,
}


def validar_transicao(status_atual: str, novo_status: str) -> bool:
    try:
        atual = StatusPedido(status_atual)
        novo = StatusPedido(novo_status)
    except ValueError:
        return False
    return novo in TRANSICOES_VALIDAS.get(atual, [])


def status_do_contrato(status_interno: str) -> StatusContrato:
    """Traduz o estado interno no valor que o app lê.

    Levanta `KeyError` para um estado desconhecido, de propósito: cair num
    default silencioso ("pending") faria um pedido em estado novo aparecer
    como ativo na tela do aluno, indefinidamente.
    """
    return STATUS_CONTRATO[StatusPedido(status_interno)]
```

- [ ] **Step 4: Encadeie em `confirmar_pagamento`**

Em `back-end/commerce-service/app/routers/admin.py`:

```python
@router.patch("/orders/{pedido_id}/confirm-payment", response_model=PedidoStaffOut)
async def confirmar_pagamento(
    pedido_id: uuid.UUID,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO, na mesma chamada.

    `CONFIRMADO` é o estado que o contrato expõe como `confirmed`, e existir
    é o que dá ao aluno o passo "Confirmado" na timeline. Mas ele não é um
    estado de REPOUSO: não há simulador na fase 2 (é fase 3), e a fila de
    separação seleciona `AGUARDANDO_SEPARACAO` — parar em `CONFIRMADO`
    deixaria a fila sempre vazia e todo pedido preso atrás de um segundo
    clique manual.

    Encadear duas transições numa rota é o padrão que `finalizar_separacao`
    (separacao.py) já usa para SEPARADO -> AGUARDANDO_COLETA. As duas geram
    linha de histórico e evento, nessa ordem.
    """
    await transicionar_pedido(db, pedido_id, StatusPedido.CONFIRMADO.value, user["sub"])
    return await transicionar_pedido(
        db, pedido_id, StatusPedido.AGUARDANDO_SEPARACAO.value, user["sub"]
    )
```

> `pedido_id: uuid.UUID` já antecipa a task C3. Se você estiver executando C1 antes de C3, mantenha `int` e troque depois — mas anote, porque é fácil esquecer.

- [ ] **Step 5: Rode a suíte inteira**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS. Suítes de staff que assumiam `CRIADO → AGUARDANDO_SEPARACAO` direto vão falhar — **elas travavam a máquina antiga**, então atualize-as e diga isso no corpo do commit (constraint 21).

- [ ] **Step 6: Prove o mapeamento exaustivo (constraint 11)**

Acrescente um valor fictício a `StatusPedido` sem pôr no `STATUS_CONTRATO`, rode `test_the_mapping_covers_every_internal_state`, confirme `KeyError`, remova o valor fictício.

- [ ] **Step 7: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/app/services/status_pedido.py \
        back-end/commerce-service/app/routers/admin.py \
        back-end/commerce-service/tests/
git diff --staged
git commit -m "feat(commerce): add CONFIRMADO and the nine-to-six status mapping

The internal machine speaks nine states; the public contract exposes six.
cancelled is the sixth because the Flutter enum falls back to pending, so a
cancelled order would render as active on step 0 forever.

confirm-payment chains CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO in one
call: without the phase-3 simulator, resting at CONFIRMADO would leave the
picking queue permanently empty.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C2: rename mecânico `pedidos` → `orders`

**Só o rename.** PK ainda `Integer`, nenhuma coluna nova, nenhuma rota nova. Suíte verde antes e depois. Este é o maior raio do bloco: `picking`, `delivery`, `occurrences`, `admin` e as 69 suítes.

Mapeamento de `pedidos` → `orders`:
`aluno_id`→`user_id` · `valor_total`→`total` · `separador_id`→`picker_id` · `entregador_id`→`deliverer_id` · `transportadora_nome`→`carrier_name` · `data_prevista_entrega`→`estimated_delivery_at` · `criado_em`→`created_at` · `atualizado_em`→`updated_at` · `status` fica · `endereco_entrega` fica (some em C4).

De `pedido_itens` → `order_items`:
`pedido_id`→`order_id` · `produto_id`→`product_id` · `fornecedor_id`→`supplier_id` · `quantidade`→`quantity` · `preco_unitario`→`unit_price`.

`pedido_status_historico` **não é renomeada** — não tem cliente. Só o FK acompanha o rename da tabela alvo.

**Files:**
- Modify: `back-end/commerce-service/app/models/pedido.py`, `ocorrencia.py`
- Modify: `back-end/commerce-service/app/schemas/pedido.py`, `ocorrencia.py`
- Modify: `back-end/commerce-service/app/routers/pedidos.py`, `separacao.py`, `entrega.py`, `admin.py`, `ocorrencias.py`
- Modify: `back-end/commerce-service/app/services/priorizacao_fila.py`, `previsao_entrega.py`
- Create: `back-end/commerce-service/alembic/versions/<hash>_rename_pedidos_to_orders.py`
- Modify: as suítes do commerce

**Interfaces:**
- Produces: `app.models.pedido.Order` e `app.models.pedido.OrderItem` (as classes `Pedido`/`PedidoItem` deixam de existir). `PedidoStatusHistorico` mantém o nome de classe e de tabela; só `pedido_id` vira `order_id`.
- `PedidoOut`/`PedidoStaffOut`/`PedidoFilaOut` mantêm os nomes de classe nesta task; os **campos** viram inglês porque seguem a tabela. `PedidoStatusHistoricoOut` fica em português (tabela sem cliente), exceto o campo que vem de `orders`.

> **Regra de língua de schema (do spec):** o schema segue a **tabela**, não o router. `occurrences`, `picking`, `delivery` e `admin` continuam em português nos campos vindos de `ocorrencias`/`estoque`/`fornecedores`, e passam a inglês nos campos vindos de `orders`. Um `PedidoStaffOut` com `user_id` ao lado de `score_risco` é o resultado correto dessa regra, não uma inconsistência.

- [ ] **Step 1: Meça o raio**

Run:
```bash
cd back-end/commerce-service
grep -rn "Pedido\b\|PedidoItem\|pedidos\|pedido_itens\|aluno_id\|valor_total\|separador_id\|entregador_id\|transportadora_nome\|data_prevista_entrega\|criado_em\|atualizado_em\|preco_unitario\|quantidade\b" app/ tests/ > /tmp/raio-c2.txt
wc -l /tmp/raio-c2.txt
```

Registre a contagem. Ela é a medida do risco que o spec nomeou.

> `criado_em` e `atualizado_em` aparecem também em `ocorrencias` e `pedido_status_historico`, que **não** mudam. `quantidade` aparece em `estoque`, que **não** muda. Filtre por arquivo antes de substituir cegamente.

- [ ] **Step 2: Suíte verde ANTES**

Run: `cd back-end/commerce-service && uv run pytest -q`

Anote a contagem. Não comece sobre vermelho.

- [ ] **Step 3: Renomeie os models**

```python
class Order(Base):
    """Pedido. Em inglês — tabela e colunas — porque é um agregado com
    cliente (o app Flutter, na fase 4).

    `pedido_status_historico` continua em português: sem cliente. `status`
    guarda o estado INTERNO (nove valores, `StatusPedido`); a tradução para
    os seis do contrato acontece na serialização, não aqui.
    """

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(
        String(30), nullable=False, default="CRIADO", server_default=text("'CRIADO'"), index=True
    )
    endereco_entrega = Column(Text, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    picker_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    deliverer_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    carrier_name = Column(String(100), nullable=True)
    estimated_delivery_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    # Nullable: o carrinho não tem noção de fornecedor, e quem define o
    # fornecedor de um item é a separação. Um item que nasce do checkout
    # chega aqui sem `supplier_id`, e isso é correto.
    supplier_id = Column(Integer, ForeignKey("fornecedores.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)


class PedidoStatusHistorico(Base):
    """Sem cliente — fica em português. Só o FK acompanha o rename."""

    __tablename__ = "pedido_status_historico"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    status = Column(String(30), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
```

Em `app/models/ocorrencia.py`, só o alvo do FK: `pedido_id = Column(Integer, ForeignKey("orders.id"), ...)`. **`ocorrencias.pedido_id` mantém o nome** — agregado sem cliente.

- [ ] **Step 4: Atualize schemas e routers**

`PedidoOut` passa a:

```python
class PedidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID
    status: str
    endereco_entrega: str
    total: Decimal
    carrier_name: str | None
    estimated_delivery_at: datetime | None
    created_at: datetime
```

`PedidoStaffOut` ganha `picker_id`/`deliverer_id`. `PedidoStatusHistoricoOut` fica como está (`status`, `observacao`, `criado_em` — todos de uma tabela sem cliente).

Percorra `/tmp/raio-c2.txt` e ajuste os routers. Os pontos que **não** são substituição direta:
- `separacao.py`: `Pedido.criado_em.asc()` → `Order.created_at.asc()`; `pedido.separador_id` → `pedido.picker_id`.
- `entrega.py`: `Pedido.entregador_id` → `Order.deliverer_id`; `pedido.data_prevista_entrega` → `pedido.estimated_delivery_at`.
- `ocorrencias.py`: `pedido.valor_total` → `pedido.total`; `pedido.aluno_id` → `pedido.user_id`; `item.preco_unitario` → `item.unit_price`; `item.quantidade` → `item.quantity`; `PedidoItem.produto_id` → `OrderItem.product_id`. Os **payloads de evento** ficam como estão (`"pedido_id"`, `"aluno_id"`, `"valor_total"`) — chave de evento não é campo de tabela, e renomeá-la dessincronizaria produtor e consumidor sem nenhum cliente pedindo.
- `services/priorizacao_fila.py` e `previsao_entrega.py`: leia os dois e ajuste os atributos.
- `_pode_ver_pedido` (criado no bloco A, task 10): `pedido.separador_id`/`entregador_id` → `picker_id`/`deliverer_id`.

- [ ] **Step 5: Escreva a migration à mão**

Run: `cd back-end && docker compose exec -T commerce-service uv run alembic revision -m "rename pedidos to orders"`

```python
def upgrade() -> None:
    op.rename_table("pedidos", "orders")
    op.alter_column("orders", "aluno_id", new_column_name="user_id")
    op.alter_column("orders", "valor_total", new_column_name="total")
    op.alter_column("orders", "separador_id", new_column_name="picker_id")
    op.alter_column("orders", "entregador_id", new_column_name="deliverer_id")
    op.alter_column("orders", "transportadora_nome", new_column_name="carrier_name")
    op.alter_column("orders", "data_prevista_entrega", new_column_name="estimated_delivery_at")
    op.alter_column("orders", "criado_em", new_column_name="created_at")
    op.alter_column("orders", "atualizado_em", new_column_name="updated_at")

    op.rename_table("pedido_itens", "order_items")
    op.alter_column("order_items", "pedido_id", new_column_name="order_id")
    op.alter_column("order_items", "produto_id", new_column_name="product_id")
    op.alter_column("order_items", "fornecedor_id", new_column_name="supplier_id")
    op.alter_column("order_items", "quantidade", new_column_name="quantity")
    op.alter_column("order_items", "preco_unitario", new_column_name="unit_price")
    op.alter_column("order_items", "supplier_id", nullable=True)

    op.alter_column("pedido_status_historico", "pedido_id", new_column_name="order_id")


def downgrade() -> None:
    op.alter_column("pedido_status_historico", "order_id", new_column_name="pedido_id")
    op.alter_column("order_items", "supplier_id", nullable=False)
    op.alter_column("order_items", "unit_price", new_column_name="preco_unitario")
    op.alter_column("order_items", "quantity", new_column_name="quantidade")
    op.alter_column("order_items", "supplier_id", new_column_name="fornecedor_id")
    op.alter_column("order_items", "product_id", new_column_name="produto_id")
    op.alter_column("order_items", "order_id", new_column_name="pedido_id")
    op.rename_table("order_items", "pedido_itens")

    op.alter_column("orders", "updated_at", new_column_name="atualizado_em")
    op.alter_column("orders", "created_at", new_column_name="criado_em")
    op.alter_column("orders", "estimated_delivery_at", new_column_name="data_prevista_entrega")
    op.alter_column("orders", "carrier_name", new_column_name="transportadora_nome")
    op.alter_column("orders", "deliverer_id", new_column_name="entregador_id")
    op.alter_column("orders", "picker_id", new_column_name="separador_id")
    op.alter_column("orders", "total", new_column_name="valor_total")
    op.alter_column("orders", "user_id", new_column_name="aluno_id")
    op.rename_table("orders", "pedidos")
```

> **Confira se `fornecedor_id` era `NOT NULL`** antes de escrever o `alter_column(..., nullable=True)`. No model atual ele é `Column(Integer, ForeignKey(...))` sem `nullable=`, o que é nullable por padrão — nesse caso a linha do `alter_column` de nulidade sai, e o `downgrade` correspondente também. Meça, não assuma: `docker compose exec -T postgres psql -U edu -d commerce_db -c "\d pedido_itens"`.

- [ ] **Step 6: Atualize as suítes, rode, sincronize**

```bash
cd back-end/commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic upgrade head
docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS com **a mesma contagem do Step 2**; sync-check **vazio**.

- [ ] **Step 7: Releia os docstrings (constraint 16)**

`separacao.py::transicionar_pedido`, `iniciar_separacao`, `finalizar_separacao` e `entrega.py::confirmar_coleta` têm docstrings longos que citam `separador_id`, `entregador_id`, `assign-picker` e a máquina de estados. Os nomes mudaram; a task C1 mudou a máquina. Atualize cada um. Um docstring que descreve a versão anterior é pior do que nenhum.

- [ ] **Step 8: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "refactor(commerce): rename pedidos to orders, table and columns

Mechanical rename, no behaviour change. The orders aggregate gains a client
in phase 4, so it turns English — the whole table, not just the columns the
app reads. pedido_status_historico stays Portuguese: no client. order_items
gains a nullable supplier_id, because the cart has no notion of supplier and
picking is what assigns one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C3: `orders.id` e `order_items.id` viram UUID

Mesma razão de `products`: o Flutter faz `as String` sobre `id`, e id inteiro é enumerável.

Cascata: `order_items.order_id` · `pedido_status_historico.order_id` · `ocorrencias.pedido_id`.

**Files:**
- Modify: `back-end/commerce-service/app/models/pedido.py`, `ocorrencia.py`
- Modify: todos os schemas e routers com `pedido_id: int`
- Create: `back-end/commerce-service/alembic/versions/<hash>_orders_uuid_pk.py`
- Modify: as suítes

**Interfaces:**
- Produces: `Order.id: uuid.UUID`, `OrderItem.id: uuid.UUID`, com `default=new_uuid` e `server_default=text("gen_random_uuid()")`.
  Todo path param `pedido_id`/`order_id` vira `uuid.UUID`.

- [ ] **Step 1: Refaça a contagem de linhas (portão)**

Mesmo comando da task C0/Step 2, agora contra `orders`/`order_items`. Zero em todas → siga. Qualquer > 0 → pare.

- [ ] **Step 2: Escreva o teste que falha**

```python
async def test_order_id_is_a_uuid_string_in_the_response(client, db_session):
    pedido = await _seed_pedido(db_session, user_id=ALUNO)
    response = await client.get(f"/orders/{pedido.id}", headers=headers_for("student", sub=ALUNO))
    assert response.status_code == 200
    assert isinstance(response.json()["id"], str)
    uuid.UUID(response.json()["id"])


async def test_a_malformed_order_id_is_a_422_not_a_500(client):
    response = await client.get("/orders/nao-e-uuid", headers=headers_for("student"))
    assert response.status_code == 422
```

- [ ] **Step 3: Rode e confirme que falha**

Expected: `assert isinstance(1, str)` e 404 (não 422) no id malformado.

- [ ] **Step 4: Troque o tipo**

Em `app/models/pedido.py`, `Order.id` e `OrderItem.id` viram:

```python
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
```

com `from app.ids import new_uuid` (criado no bloco B). `OrderItem.order_id`, `PedidoStatusHistorico.order_id` e `Ocorrencia.pedido_id` viram `UUID(as_uuid=True)`.

Em todo router e schema, `pedido_id: int` → `pedido_id: uuid.UUID`; `PedidoOut.id: int` → `uuid.UUID`; `OcorrenciaOut.pedido_id`, `FaltaEstoqueIn.pedido_id`, `AtrasoEntregaIn.pedido_id` idem.

- [ ] **Step 5: Escreva a migration como reconstrução declarada**

Mesmo padrão da task B4: revision manual (não autogenerate), com `_falhar_se_houver_dado` guardando as quatro tabelas afetadas (`orders`, `order_items`, `pedido_status_historico`, `ocorrencias`), drop das FKs, `ALTER ... TYPE uuid USING gen_random_uuid()` na PK, `ALTER ... TYPE uuid USING NULL` nas colunas referenciadoras, recriação das FKs, e `downgrade` que levanta `RuntimeError`.

Copie a estrutura literal da revision de B4 e troque a lista de tabelas e constraints. **Confira os nomes reais das constraints** com `\d order_items`, `\d pedido_status_historico`, `\d ocorrencias` antes de escrever os `drop_constraint`.

- [ ] **Step 6: Aplique, rode, sincronize**

```bash
cd back-end && docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio**.

- [ ] **Step 7: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "refactor(commerce): make orders.id and order_items.id UUIDs

Same reason as products: the Flutter model does \`as String\` on id, and an
integer id is enumerable. order_items.order_id,
pedido_status_historico.order_id and ocorrencias.pedido_id follow. A
malformed id now answers 422 instead of reaching the query.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C4: `ship_*`, `payment_method`, `status_updated_at` e o snapshot do item

`orders` troca `endereco_entrega Text NOT NULL` pelos oito `ship_*` nullable do legacy, e ganha `payment_method` e `status_updated_at`. `order_items` ganha o snapshot que o app lê (`product_name`, `image_url`, `rating_avg`, `rating_count`).

**Files:**
- Modify: `back-end/commerce-service/app/models/pedido.py`
- Modify: `back-end/commerce-service/app/schemas/pedido.py`
- Modify: `back-end/commerce-service/app/routers/separacao.py`, `entrega.py`, `admin.py` (schemas de staff que mostram `endereco_entrega`)
- Modify: `back-end/commerce-service/app/routers/separacao.py::transicionar_pedido` (carimba `status_updated_at`)
- Create: `back-end/commerce-service/alembic/versions/<hash>_orders_shipping_and_snapshot.py`

**Interfaces:**
- Produces:
  - `Order` ganha `payment_method String(120) NOT NULL DEFAULT ''`, `status_updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`, e `ship_label(60)`, `ship_zip_code(9)`, `ship_street(160)`, `ship_number(20)`, `ship_complement(120)`, `ship_neighborhood(120)`, `ship_city(120)`, `ship_state(2)`, todos nullable. `endereco_entrega` **sai**.
  - `OrderItem` ganha `product_name String(160) NOT NULL`, `image_url String(512) NOT NULL DEFAULT ''`, `rating_avg Numeric(3,2) NOT NULL DEFAULT 0`, `rating_count Integer NOT NULL DEFAULT 0`.
  - `def endereco_formatado(order: Order) -> str` em `app/services/pedidos.py` — compõe a string que os schemas de staff mostravam.

- [ ] **Step 1: Escreva o teste que falha**

```python
async def test_order_carries_the_shipping_snapshot(db_session):
    pedido = Order(
        user_id=uuid.uuid4(),
        status=StatusPedido.CRIADO.value,
        total=Decimal("100.00"),
        payment_method="PIX",
        ship_label="Casa",
        ship_zip_code="01310-100",
        ship_street="Av. Paulista",
        ship_number="1000",
        ship_complement="ap 42",
        ship_neighborhood="Bela Vista",
        ship_city="São Paulo",
        ship_state="SP",
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)

    assert pedido.ship_city == "São Paulo"
    assert pedido.status_updated_at is not None


async def test_staff_view_composes_the_address_from_the_snapshot(client, db_session):
    """Os schemas de staff mostravam `endereco_entrega`; a coluna morreu, mas
    a informação não — ela passa a ser composta dos oito campos."""
    pedido = await _seed_pedido_com_endereco(db_session)
    response = await client.get("/admin/orders", headers=headers_for("admin"))
    assert response.status_code == 200
    assert response.json()[0]["endereco_entrega"] == (
        "Av. Paulista, 1000, ap 42 - Bela Vista, São Paulo - SP, 01310-100"
    )


async def test_a_transition_stamps_status_updated_at(client, db_session):
    """A timeline do rastreio mostra a hora da última mudança — sem este
    carimbo ela mostraria a hora da criação para sempre."""
    pedido = await _seed_pedido(db_session, status=StatusPedido.CRIADO.value)
    antes = pedido.status_updated_at

    await client.patch(
        f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin")
    )

    await db_session.refresh(pedido)
    assert pedido.status_updated_at > antes


async def test_order_item_snapshots_the_product(db_session):
    pedido = await _seed_pedido(db_session)
    item = OrderItem(
        order_id=pedido.id,
        product_id=uuid.uuid4(),
        product_name="Guia de Redação Nota 1000",
        unit_price=Decimal("49.90"),
        quantity=2,
        image_url="products/seed-0.jpg",
        rating_avg=4.5,
        rating_count=128,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    assert item.product_name == "Guia de Redação Nota 1000"
    assert item.supplier_id is None
```

> **Constraint 12:** a string do endereço composto é escrita literal no teste. Se você a montasse chamando `endereco_formatado`, o teste passaria com qualquer formato.

- [ ] **Step 2: Rode e confirme que falha**

Expected: `TypeError: 'ship_label' is an invalid keyword argument`.

- [ ] **Step 3: Acrescente as colunas**

```python
class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid,
                server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="CRIADO",
                    server_default=text("'CRIADO'"), index=True)
    total = Column(Numeric(10, 2), nullable=False)
    # Rótulo descritivo escolhido no app ("PIX", "Visa ••••1234"). Nunca um
    # dado de cartão: o que identifica a forma de pagamento vive em
    # `payment_methods`, mascarado.
    payment_method = Column(String(120), nullable=False, default="", server_default=text("''"))

    picker_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    deliverer_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    carrier_name = Column(String(100), nullable=True)
    estimated_delivery_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Quando o pedido mudou de status pela última vez. Alimenta os horários da
    # timeline do rastreio; carimbado por `transicionar_pedido`.
    status_updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Snapshot do endereço escolhido no checkout. Um pedido é o registro
    # histórico de PARA ONDE foi entregue, então o endereço é copiado aqui e
    # não pode mudar se o aluno editar ou apagar o endereço de origem.
    #
    # Nullable: o contrato de criação aceita corpo vazio (sem `address_id`),
    # e nesse caso `GET /orders/{id}/route` responde 503 por falta de
    # destino — que é o comportamento do legacy.
    #
    # Os tamanhos batem com `auth-users-service/app/models/address.py`. Um
    # endereço que cabe lá tem que caber aqui, senão o checkout estoura no
    # INSERT depois de já ter travado o carrinho.
    ship_label = Column(String(60), nullable=True)
    ship_zip_code = Column(String(9), nullable=True)
    ship_street = Column(String(160), nullable=True)
    ship_number = Column(String(20), nullable=True)
    ship_complement = Column(String(120), nullable=True)
    ship_neighborhood = Column(String(120), nullable=True)
    ship_city = Column(String(120), nullable=True)
    ship_state = Column(String(2), nullable=True)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderItem.product_name",
    )
```

```python
class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid,
                server_default=text("gen_random_uuid()"))
    order_id = Column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Snapshot do produto no momento da compra — um pedido é registro
    # histórico e não pode mudar se o catálogo mudar preço ou nome depois.
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    product_name = Column(String(160), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    image_url = Column(String(512), nullable=False, default="", server_default=text("''"))
    rating_avg = Column(Numeric(3, 2), nullable=False, default=0, server_default=text("0"))
    rating_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    # Nullable: o carrinho não tem fornecedor; quem o define é a separação.
    supplier_id = Column(Integer, ForeignKey("fornecedores.id"), nullable=True)

    order = relationship("Order", back_populates="items")
```

- [ ] **Step 4: Componha o endereço para os schemas de staff**

Em `app/services/pedidos.py` (crie o módulo se ainda não existir):

```python
def endereco_formatado(order: Order) -> str:
    """Monta a string que `endereco_entrega` guardava, a partir dos oito
    campos do snapshot.

    A coluna morreu porque um endereço em texto livre não dá para geocodificar
    (`GET /orders/{id}/route` precisa dos campos separados) nem para renderizar
    por parte. Mas a operação de staff lia essa string — então ela continua
    existindo, agora derivada.

    Pedido sem snapshot (criação com corpo vazio) devolve string vazia, não
    "None, None - None".
    """
    complemento = f"{order.ship_number}, {order.ship_complement}" if order.ship_complement else order.ship_number
    partes = [
        f"{order.ship_street}, {complemento}" if order.ship_street else None,
        order.ship_neighborhood,
        f"{order.ship_city} - {order.ship_state}" if order.ship_city else None,
        order.ship_zip_code,
    ]
    return ", ".join(p for p in partes if p)
```

> Confira a string esperada do teste do Step 1 contra esta função e ajuste **a função** se divergir — o formato do teste é o que a operação lê hoje.

Em `PedidoStaffOut`, `endereco_entrega` deixa de ser campo de model e vira computado:

```python
class PedidoStaffOut(BaseModel):
    """Visão de staff. Campos vindos de `orders` em inglês; `score_risco`
    (de `priorizacao_fila`) em português. É a regra de língua por agregado,
    não uma inconsistência."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: str
    total: Decimal
    endereco_entrega: str
    carrier_name: str | None
    estimated_delivery_at: datetime | None
    created_at: datetime
    picker_id: UUID | None
    deliverer_id: UUID | None

    @classmethod
    def de_order(cls, order: Order) -> "PedidoStaffOut":
        return cls(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            total=order.total,
            endereco_entrega=endereco_formatado(order),
            carrier_name=order.carrier_name,
            estimated_delivery_at=order.estimated_delivery_at,
            created_at=order.created_at,
            picker_id=order.picker_id,
            deliverer_id=order.deliverer_id,
        )
```

e troque `PedidoStaffOut.model_validate(pedido)` por `PedidoStaffOut.de_order(pedido)` em `separacao.py`, `entrega.py` e `admin.py`. As rotas com `response_model=list[PedidoStaffOut]` que hoje devolvem objetos ORM crus precisam passar a construir explicitamente.

- [ ] **Step 5: Carimbe `status_updated_at`**

Em `separacao.py::transicionar_pedido`, junto de `pedido.status = novo_status`:

```python
    pedido.status = novo_status
    # A timeline do rastreio mostra a hora da última mudança. Sem este
    # carimbo ela mostraria a hora da criação para sempre.
    pedido.status_updated_at = datetime.now(UTC)
```

- [ ] **Step 6: Migration, aplicar, rodar, sincronizar**

```bash
cd back-end && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "orders shipping and item snapshot"
```

Revise: `add_column` para os onze campos novos, `drop_column` de `endereco_entrega`, e **`server_default` em todo `nullable=False` novo** (`payment_method`, `status_updated_at`, `product_name`… — `product_name` não tem default; a tabela está vazia, então declare-o com `server_default=""` na migration e remova o default depois, ou aceite `nullable=False` sem default porque não há linha para preencher; escolha e registre).

```bash
docker compose exec -T commerce-service uv run alembic upgrade head
cd commerce-service && uv run pytest -q
cd ../ && docker compose exec -T commerce-service uv run alembic revision --autogenerate -m "sync check"
```

Expected: PASS; sync-check **vazio**.

- [ ] **Step 7: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): snapshot shipping and product data on the order

endereco_entrega as free text could neither be geocoded for the route
endpoint nor rendered field by field, so it becomes the eight ship_*
columns the legacy carries; the staff view composes the old string from
them. order_items snapshots product name, image and rating, because an
order is a historical record and must not change when the catalog does.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C5: `GET /auth/addresses/{id}` e `auth_client.get_address`

O checkout precisa do endereço para copiá-lo. O `auth-users-service` só tem a listagem — a busca individual existe como função privada (`_buscar_endereco_do_usuario`) mas não como rota.

**Files:**
- Modify: `back-end/auth-users-service/app/routers/addresses.py`
- Test: `back-end/auth-users-service/tests/test_addresses_routes.py`
- Modify: `back-end/commerce-service/app/services/auth_client.py`
- Test: `back-end/commerce-service/tests/test_auth_client.py`

**Interfaces:**
- Produces:
  - `GET /auth/addresses/{address_id}` → `AddressOut`; 404 `"Endereço não encontrado"` para id inexistente **ou de outro usuário** (mesma resposta, para não virar oráculo).
  - `auth_client.get_address(raw_token: str, address_id: uuid.UUID) -> dict | None` — devolve `None` no 404, levanta `AuthServiceUnavailable` em falha de transporte ou 5xx.

> Por que `None` no 404 e exceção no resto: o router do checkout precisa distinguir "endereço inválido" (→ 400 `"Invalid delivery address"`, que é como o legacy trata id obsoleto) de "auth fora do ar" (→ 503). Um único tipo de erro obrigaria o chamador a inspecionar mensagem.

- [ ] **Step 1: Escreva o teste que falha (auth-users-service)**

```python
async def test_get_address_returns_the_owners_address(client, db_session, auth_headers, user_id):
    endereco = await _seed_endereco(db_session, user_id)
    response = await client.get(f"/auth/addresses/{endereco.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["street"] == endereco.street


async def test_get_address_hides_another_users_address_behind_404(client, db_session, auth_headers):
    endereco = await _seed_endereco(db_session, uuid.uuid4())  # outro dono
    response = await client.get(f"/auth/addresses/{endereco.id}", headers=auth_headers)
    # 404, não 403: 403 confirmaria que o id existe, virando um oráculo de
    # enumeração sobre os endereços dos outros.
    assert response.status_code == 404


async def test_get_address_requires_authentication(client):
    response = await client.get(f"/auth/addresses/{uuid.uuid4()}")
    assert response.status_code == 403
```

- [ ] **Step 2: Rode e confirme que falha**

Expected: 405 ou 404 — não há rota GET com path param.

- [ ] **Step 3: Acrescente a rota**

Em `back-end/auth-users-service/app/routers/addresses.py`, **entre** `criar_endereco` e `atualizar_endereco`:

```python
@router.get("/{address_id}", response_model=AddressOut)
async def detalhe_endereco(
    address_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Um endereço do próprio usuário.

    Existe para o checkout do commerce-service, que copia o endereço para o
    snapshot do pedido e não pode ler o banco do auth. O bearer repassado é
    o do próprio aluno, então a autorização continua sendo daqui.

    Endereço de outro usuário devolve o MESMO 404 de um id inexistente —
    `_buscar_endereco_do_usuario` já filtra por `user_id`. Um 403 confirmaria
    que o id existe.
    """
    return await _buscar_endereco_do_usuario(db, address_id, user_id)
```

> A rota vai **depois** de `POST ""` e **antes** de `PATCH /{address_id}`; a ordem entre métodos diferentes não importa no FastAPI, mas manter o agrupamento por recurso é o que o arquivo já faz.

- [ ] **Step 4: Escreva o teste do cliente (commerce)**

Em `back-end/commerce-service/tests/test_auth_client.py`, no mesmo padrão de `get_me`:

```python
def _cliente_falso(resposta=None, erro=None, capturado=None):
    """Dublê de `httpx.AsyncClient` no mesmo formato do teste de `get_me`.

    Um só helper para os três testes abaixo: ou devolve `resposta`, ou
    levanta `erro`, e registra url/headers em `capturado`.
    """

    class _Cliente:
        def __init__(self, **kwargs):
            if capturado is not None:
                capturado["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            if capturado is not None:
                capturado["url"] = url
                capturado["headers"] = headers
            if erro is not None:
                raise erro
            return resposta

    return _Cliente


class _Resposta:
    def __init__(self, status_code, corpo=None):
        self.status_code = status_code
        self._corpo = corpo or {}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(str(self.status_code), request=None, response=self)


async def test_get_address_returns_none_on_404(monkeypatch):
    """404 é "endereço inválido" (400 no checkout), não "auth fora do ar"."""
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient",
        _cliente_falso(resposta=_Resposta(404, {"detail": "Endereço não encontrado"})),
    )
    assert await get_address("token", uuid.uuid4()) is None


async def test_get_address_raises_when_auth_is_down(monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient",
        _cliente_falso(erro=httpx.ConnectError("recusado")),
    )
    with pytest.raises(AuthServiceUnavailable):
        await get_address("token", uuid.uuid4())


async def test_get_address_raises_on_a_server_error(monkeypatch):
    """5xx do auth não pode virar "endereço inválido" — o endereço pode
    existir perfeitamente."""
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient", _cliente_falso(resposta=_Resposta(500))
    )
    with pytest.raises(AuthServiceUnavailable):
        await get_address("token", uuid.uuid4())


async def test_get_address_forwards_the_bearer(monkeypatch):
    capturado: dict = {}
    address_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.services.auth_client.httpx.AsyncClient",
        _cliente_falso(
            resposta=_Resposta(200, {"street": "Av. Paulista", "city": "São Paulo"}),
            capturado=capturado,
        ),
    )

    resultado = await get_address("token-do-aluno", address_id)

    assert resultado["street"] == "Av. Paulista"
    assert capturado["headers"]["Authorization"] == "Bearer token-do-aluno"
    assert capturado["url"].endswith(f"/auth/addresses/{address_id}")
    assert capturado["timeout"] == 10.0
```

> **Constraint 14:** o alvo é `app.services.auth_client.httpx.AsyncClient` — o módulo faz `import httpx`, então `httpx` é um nome no namespace dele. Se algum dia virar `from httpx import AsyncClient`, o alvo passa a ser `app.services.auth_client.AsyncClient`.

- [ ] **Step 5: Acrescente `get_address` ao cliente existente**

Em `back-end/commerce-service/app/services/auth_client.py` — **o mesmo arquivo que a task B7 criou**, não um novo:

```python
async def get_address(raw_token: str, address_id: uuid.UUID) -> dict | None:
    """`GET /auth/addresses/{id}` — devolve o endereço, ou `None` se ele não
    existe / não é do aluno.

    A distinção importa: o checkout traduz `None` em 400 "Invalid delivery
    address" (é assim que o legacy trata id obsoleto, não 404) e
    `AuthServiceUnavailable` em 503. Um único tipo de erro obrigaria o
    chamador a inspecionar mensagem para decidir o status.
    """
    url = f"{settings.auth_service_url}/auth/addresses/{address_id}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {raw_token}"})
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("auth_client: /auth/addresses respondeu {}", exc.response.status_code)
        raise AuthServiceUnavailable("auth-users-service indisponível") from None
    except httpx.HTTPError:
        logger.warning("auth_client: /auth/addresses inalcançável")
        raise AuthServiceUnavailable("auth-users-service indisponível") from None
```

> `raise ... from None` pelo mesmo motivo de `get_me`: o `repr` de um `HTTPStatusError` inclui a requisição, com o header `Authorization`. `from exc` vazaria o token para o log de erro.
>
> A URL do log **não** inclui o `address_id` porque ele é um identificador do aluno — a mensagem genérica basta para diagnosticar.

- [ ] **Step 6: Rode as duas suítes**

Run: `cd back-end/auth-users-service && uv run pytest -q && cd ../commerce-service && uv run pytest -q`

Expected: PASS nas duas.

- [ ] **Step 7: Prove que o 404 não vira 503 (constraint 11)**

Troque o `if response.status_code == 404: return None` por nada (deixe o `raise_for_status` pegar), rode `test_get_address_returns_none_on_404`, confirme que levanta `AuthServiceUnavailable`, reaplique.

- [ ] **Step 8: Commit (dois serviços, dois commits)**

```bash
cd back-end/auth-users-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/auth-users-service/
git commit -m "feat(auth): expose a single address by id

The commerce checkout copies the delivery address into the order snapshot
and cannot read the auth database. A foreign address answers the same 404
as a missing one, so the route is not an enumeration oracle.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git commit -m "feat(commerce): fetch the delivery address through the auth client

Returns None on 404 and raises on transport failure, so the checkout can
answer 400 \"Invalid delivery address\" for a stale id and 503 when auth is
down without parsing a message.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C6: `POST /orders` lê o carrinho, `GET /orders` devolve array puro

Esta task fecha a falha vendorizada que o bloco A deixou para trás de propósito: `pedidos.py:32` compõe `valor_total` a partir do `preco_unitario` que o **cliente** enviou, sem nunca importar `Produto`. A rota é substituída, não remendada.

E `GET /orders/mine` some — é a razão de `GET /orders` responder 405.

**Files:**
- Create/Modify: `back-end/commerce-service/app/services/pedidos.py`
- Modify: `back-end/commerce-service/app/routers/pedidos.py`
- Modify: `back-end/commerce-service/app/schemas/pedido.py`
- Modify: `back-end/commerce-service/app/exceptions.py`
- Test: `back-end/commerce-service/tests/test_orders_parity.py` (portado)

**Interfaces:**
- Produces:
  - `OrderCreateIn{payment_method: str = "" (≤120), address_id: uuid.UUID | None = None}`
  - `OrderItemOut{product_id, product_name, unit_price (string), quantity, image_url, rating_avg, rating_count}`
  - `OrderOut{id, total (string), status (StatusContrato), payment_method, created_at, items}`
  - `services.criar_pedido_do_carrinho(db, user_id, payment_method, *, address: dict | None) -> Order`
  - `services.listar_pedidos(db, user_id, *, limit, offset) -> list[Order]`
  - `services.buscar_pedido(db, user_id, order_id) -> Order` (levanta `OrderNotFound`)
  - `EmptyCart`, `OrderNotFound` em `app/exceptions.py`

- [ ] **Step 1: Porte o teste do legacy (Red)**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
cp legacy/tests/modules/orders/test_routes.py commerce-service/tests/test_orders_parity.py
cp legacy/tests/modules/orders/test_services.py commerce-service/tests/test_orders_services_parity.py
```

Adaptações: sem `/api`; imports para `app.models.pedido`/`app.services.pedidos`; auth para `headers_for("student", sub=...)`; 401 → 403 com o comentário de B0.

**Adaptação que não é mecânica:** o legacy resolve o endereço chamando `addresses_services.get_address` na mesma sessão. Aqui é HTTP. Os testes que exercitam `address_id` precisam remendar `app.routers.pedidos.get_address` (constraint 14 — o nome onde o **router** importa) com um dublê que devolve o dict do endereço, e um que devolve `None` para o caso de id inválido.

**Não porte** `test_lifecycle.py` nem `test_status_pipeline.py` — carve-out declarado (constraint 22). Registre.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/commerce-service && uv run pytest tests/test_orders_parity.py -v`

Expected: 405 em `GET /orders` (a rota `/mine` ocupa o lugar), 422 no `POST` (o corpo é outro).

- [ ] **Step 3: Escreva o serviço de checkout**

Em `back-end/commerce-service/app/services/pedidos.py`:

```python
async def criar_pedido_do_carrinho(
    db: AsyncSession,
    user_id: uuid.UUID,
    payment_method: str,
    *,
    address: dict | None = None,
) -> Order:
    """Cria o pedido a partir do carrinho do aluno, numa transação só.

    O PREÇO VEM DO CATÁLOGO, nunca do cliente. A rota anterior compunha
    `valor_total` a partir do `preco_unitario` que veio na requisição e nunca
    importava o model de produto — qualquer aluno comprava qualquer coisa por
    um centavo. Essa rota é substituída inteira aqui, não remendada.

    O carrinho é travado com `with_for_update()` para que um checkout
    duplicado (duplo toque, retry do app) não construa dois pedidos do mesmo
    carrinho: o segundo o encontra já esvaziado e recebe "Cart is empty".

    `address` é o dict que `auth_client.get_address` devolveu — a validação
    de existência e de dono já aconteceu lá, no serviço que é dono do dado.
    """
    cart = (
        await db.execute(select(Cart).where(Cart.user_id == user_id).with_for_update())
    ).scalar_one_or_none()
    if cart is None:
        raise EmptyCart()

    cart_items = list(
        (await db.execute(select(CartItem).where(CartItem.cart_id == cart.id))).scalars().all()
    )
    if not cart_items:
        raise EmptyCart()

    products = {
        p.id: p
        for p in (
            await db.execute(
                select(Product).where(Product.id.in_([i.product_id for i in cart_items]))
            )
        ).scalars().all()
    }

    order = Order(
        user_id=user_id,
        status=StatusPedido.CRIADO.value,
        payment_method=payment_method,
        total=Decimal("0.00"),
        ship_label=address["label"] if address else None,
        ship_zip_code=address["zip_code"] if address else None,
        ship_street=address["street"] if address else None,
        ship_number=address["number"] if address else None,
        ship_complement=address["complement"] if address else None,
        ship_neighborhood=address["neighborhood"] if address else None,
        ship_city=address["city"] if address else None,
        ship_state=address["state"] if address else None,
    )

    total = Decimal("0.00")
    for cart_item in cart_items:
        product = products.get(cart_item.product_id)
        if product is None:
            # Produto saiu do catálogo entre o add e o checkout — pula.
            continue
        total += product.price * cart_item.quantity
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=cart_item.quantity,
                image_url=product.image_url,
                rating_avg=float(product.rating_avg),
                rating_count=product.rating_count,
                # `supplier_id` fica None: o carrinho não tem fornecedor.
                # Quem o define é a separação.
            )
        )

    if not order.items:
        raise EmptyCart()

    order.total = total
    db.add(order)
    db.add(PedidoStatusHistorico(order_id=order.id, status=StatusPedido.CRIADO.value))

    # Esvazia o carrinho na MESMA transação — é o que torna o checkout
    # atômico e o retry inofensivo.
    for cart_item in cart_items:
        await db.delete(cart_item)

    await db.commit()
    logger.info("orders: pedido criado id={} user={} total={}", order.id, user_id, total)

    refreshed = await _buscar_com_itens(db, user_id, order.id)
    assert refreshed is not None  # acabou de ser criado nesta transação
    return refreshed
```

> **`advance_order_status_task.delay(...)` do legacy NÃO é portado.** Não há simulador na fase 2 (constraint 22). O pedido fica em `CRIADO`/`pending` até um admin confirmar o pagamento. Escreva isso como comentário no fim da função, senão a próxima pessoa vai achar que é esquecimento.

E as duas leituras:

```python
async def listar_pedidos(
    db: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def buscar_pedido(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await _buscar_com_itens(db, user_id, order_id)
    if order is None:
        raise OrderNotFound()
    return order
```

com `_buscar_com_itens` filtrando por `Order.user_id == user_id` **sempre** (regra 2).

- [ ] **Step 4: Escreva os schemas do contrato**

```python
class OrderCreateIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Rótulo escolhido no cliente ("PIX", "Visa ••••1234"). Opcional para
    # ficar perto do contrato de corpo vazio do legacy.
    payment_method: str = Field(default="", max_length=120)
    # Qual endereço salvo recebe o pedido. Opcional pelo mesmo motivo; o app
    # sempre manda o id do endereço selecionado.
    address_id: uuid.UUID | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("unit_price")
    def _price_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class OrderOut(BaseModel):
    """Contrato do aluno. `status` é o valor do CONTRATO (seis), não o
    interno (nove) — a tradução acontece em `de_order` abaixo.

    NÃO inclui `picker_id`/`deliverer_id`: identificadores operacionais não
    são assunto do aluno. Staff usa `PedidoStaffOut`.
    """

    id: uuid.UUID
    total: Decimal
    status: StatusContrato
    payment_method: str = ""
    created_at: datetime
    items: list[OrderItemOut]

    @field_serializer("total")
    def _total_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @classmethod
    def de_order(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            total=order.total,
            status=status_do_contrato(order.status),
            payment_method=order.payment_method,
            created_at=order.created_at,
            items=[OrderItemOut.model_validate(i) for i in order.items],
        )
```

- [ ] **Step 5: Reescreva o router**

```python
router = APIRouter(prefix="/orders", tags=["orders"])


async def _order_out(order: Order, *, storage, redis) -> OrderOut:
    out = OrderOut.de_order(order)
    for item in out.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return out


@router.get("", response_model=list[OrderOut])
async def listar_pedidos(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OrderOut]:
    """ARRAY PURO, sem envelope — ao contrário de `/products` e `/cart`.

    Isso é contrato, não descuido: o app faz `jsonDecode(body) as List` aqui
    e `jsonDecode(body)['items']` lá. Reproduzir a inconsistência é o
    trabalho; "consertá-la" quebraria a tela de pedidos.

    Ordenado por `created_at desc`; `limit` 1–100 com default 50 (o de
    `/products` é 20 — também medido, também diferente de propósito).
    """
    pedidos = await services.listar_pedidos(
        db, uuid.UUID(user["sub"]), limit=limit, offset=offset
    )
    return [await _order_out(p, storage=storage, redis=redis) for p in pedidos]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def criar_pedido(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    payload: OrderCreateIn | None = None,
) -> OrderOut:
    """Corpo OPCIONAL — `payload: OrderCreateIn | None = None`. O legacy
    aceita `POST /orders` sem corpo nenhum, e o app antigo fazia isso."""
    payment_method = payload.payment_method if payload is not None else ""
    address_id = payload.address_id if payload is not None else None

    address: dict | None = None
    if address_id is not None:
        try:
            address = await get_address(user["raw_token"], address_id)
        except AuthServiceUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Serviço de usuários indisponível",
            ) from exc
        if address is None:
            # Id obsoleto ou de outro usuário é erro do cliente, não 404 do
            # pedido — é assim que o legacy trata.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid delivery address"
            )

    try:
        order = await services.criar_pedido_do_carrinho(
            db, uuid.UUID(user["sub"]), payment_method, address=address
        )
    except EmptyCart as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        ) from exc

    await publish_event(
        "order.created",
        {
            "pedido_id": str(order.id),
            "aluno_id": str(order.user_id),
            "valor_total": float(order.total),
        },
    )
    return await _order_out(order, storage=storage, redis=redis)


@router.get("/{order_id}", response_model=OrderOut)
async def detalhe_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> OrderOut:
    """Não existe no legacy, não colide com nada, e fica — traduzida: devolve
    o MESMO `OrderOut` da listagem."""
    try:
        order = await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    return await _order_out(order, storage=storage, redis=redis)
```

**Apague `GET /orders/mine`.** Ela é absorvida por `GET /orders` e é a causa medida do 405.

`GET /orders/{id}/delivery-estimate` **fica**, traduzida. Ela não existe no legacy, não colide com nada, e é o que `previsao_entrega.py` alimenta. Duas mudanças:

```python
@router.get("/{order_id}/delivery-estimate", response_model=PrevisaoEntregaOut)
async def previsao_entrega_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Estimativa de prazo de entrega — se o pedido já tem uma data definida
    (pela previsão automática ao confirmar coleta, ou por uma ocorrência de
    atraso que o aluno aceitou), devolve ela. Caso contrário calcula "a
    partir de agora" com base no histórico real, e é transparente sobre
    quantas entregas embasam o número (`amostras_historicas`) e se ele é
    confiável (`confiavel`, false com poucas amostras).
    """
    try:
        pedido = await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    _estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
    if pedido.estimated_delivery_at is not None:
        # Já existe data definida — não recalcula por cima.
        return PrevisaoEntregaOut(
            data_estimada=pedido.estimated_delivery_at,
            amostras_historicas=amostras,
            confiavel=amostras >= MINIMO_AMOSTRAS,
        )

    estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
    return PrevisaoEntregaOut(
        data_estimada=estimativa,
        amostras_historicas=amostras,
        confiavel=amostras >= MINIMO_AMOSTRAS,
    )
```

1. O ownership deixa de ser um `where` inline e passa por `services.buscar_pedido`, que é o único lugar que sabe filtrar por dono.
2. `pedido.data_prevista_entrega` → `pedido.estimated_delivery_at` (o rename da task C2).

`PrevisaoEntregaOut` **não muda de nome de campo**: `data_estimada`/`amostras_historicas`/`confiavel` vêm de `previsao_entrega.py`, que calcula sobre `pedido_status_historico` — agregado sem cliente. É a regra de língua por agregado, e esta rota não tem consumidor no app.

> **Chaves de evento continuam em português.** `"pedido_id"`, `"aluno_id"`, `"valor_total"`. Só o **tipo** de `pedido_id` muda (int → UUID string), e isso é a task C10.

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS.

- [ ] **Step 7: Prove que o preço não vem mais do cliente (constraint 11)**

```python
async def test_the_total_comes_from_the_catalog_not_from_the_request(
    client, db_session, monkeypatch
):
    """A rota antiga compunha o total com o `preco_unitario` da requisição e
    nunca importava o model de produto."""
    produto = Product(name="Guia", type="apostila", price=Decimal("49.90"))
    db_session.add(produto)
    await db_session.commit()

    await client.post(
        "/cart/items",
        json={"product_id": str(produto.id), "quantity": 2},
        headers=headers_for("student", sub=ALUNO),
    )
    response = await client.post(
        "/orders",
        json={"payment_method": "PIX", "preco_unitario": "0.01"},
        headers=headers_for("student", sub=ALUNO),
    )

    assert response.status_code == 201
    assert response.json()["total"] == "99.80"
```

Note que `preco_unitario` no corpo é **ignorado** — `OrderCreateIn` não o declara. Se você adicionar `model_config = ConfigDict(extra="forbid")` ele viraria 422; o legacy não o faz, então não faça. Registre a escolha.

- [ ] **Step 8: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): build the order from the cart at catalog prices

The previous POST /orders summed the unit price the CLIENT sent and never
imported the product model, so any student bought anything for a cent. The
route is replaced, not patched: it reads the cart under a row lock,
snapshots name/price/image/rating from the catalog, and empties the cart in
the same transaction.

GET /orders/mine is gone — it is why GET /orders answered 405. The listing
returns a bare array, deliberately unlike /products and /cart.

The Celery simulator is not ported: it is phase 3. Until then an order sits
in CRIADO until an admin confirms payment.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C7: `POST /orders/{id}/rebuy`

Repopula o carrinho a partir de um pedido passado. Produto fora do catálogo é **pulado**, não falha.

**Files:**
- Modify: `back-end/commerce-service/app/routers/pedidos.py`
- Test: `back-end/commerce-service/tests/test_orders_parity.py`

**Interfaces:**
- Produces: `POST /orders/{order_id}/rebuy` → `CartOut` (o schema do bloco B), 200.

- [ ] **Step 1: Porte os testes de rebuy (Red)**

Traga do `test_routes.py` do legacy a classe de rebuy, com as adaptações de sempre. O teste que importa é o do produto ausente:

```python
async def test_rebuy_skips_a_product_that_left_the_catalog(client, db_session):
    """Pular, não falhar: um pedido antigo com um produto descontinuado ainda
    tem que conseguir repor o resto no carrinho."""
```

- [ ] **Step 2: Rode e confirme que falha**

Expected: 404/405 — a rota não existe.

- [ ] **Step 3: Escreva a rota**

```python
@router.post("/{order_id}/rebuy", response_model=CartOut)
async def recomprar(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> CartOut:
    """Repõe no carrinho os itens de um pedido passado.

    Costura de composição no router, não no serviço: `services/pedidos.py`
    fica desacoplado de escrita no carrinho.

    Produto que saiu do catálogo é PULADO, não derruba a recompra — um
    pedido de meses atrás quase sempre tem pelo menos um item descontinuado,
    e falhar por causa dele tornaria o botão inútil.
    """
    user_id = uuid.UUID(user["sub"])
    try:
        order = await services.buscar_pedido(db, user_id, order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Order not found") from exc

    cart: CartOut | None = None
    for item in order.items:
        try:
            cart = await cart_services.adicionar_item(
                db, user_id, CartItemIn(product_id=item.product_id, quantity=item.quantity)
            )
        except CartProductNotFound:
            continue

    if cart is None:
        # Nenhum produto do pedido existe mais — devolve o carrinho atual.
        cart = await cart_services.obter_carrinho(db, user_id)

    for item in cart.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return cart
```

- [ ] **Step 4: Rode, prove, commite**

```bash
cd back-end/commerce-service && uv run pytest -q
```

Prova (constraint 11): troque o `continue` do `except CartProductNotFound` por `raise`, rode o teste do produto ausente, confirme FAIL, reaplique.

```bash
uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git commit -m "feat(commerce): add rebuy from a past order

Skips a product that left the catalog instead of failing: an order from
months ago almost always has one discontinued item, and failing on it would
make the button useless.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C8: rastreio — a rota ocupada muda de dono

`GET /orders/{id}/tracking` hoje devolve o **histórico de status**. O app espera o **objeto que a tela renderiza**. A réplica exata fica com a rota; o histórico se muda para `GET /orders/{id}/status-history`.

Esta é a primeira das duas correções ao design da fase 1 que o spec registra.

**Files:**
- Create: `back-end/commerce-service/app/services/rastreio_builder.py`
- Create: `back-end/commerce-service/app/schemas/rastreio.py`
- Create: `back-end/commerce-service/app/routers/rastreio.py`
- Modify: `back-end/commerce-service/app/routers/pedidos.py` (tira `/tracking`, põe `/status-history`)
- Modify: `back-end/commerce-service/app/main.py`
- Test: seis arquivos portados de `legacy/tests/test_tracking_*.py`

**Interfaces:**
- Produces:
  - `build_order_tracking(order: Order) -> OrderTrackingOut` — **pura**, sem I/O.
  - Schemas `TrackingStepOut`, `TrackingLocationOut`, `KitItemOut`, `OrderTrackingOut` (idênticos aos do legacy).
  - `GET /orders/{id}/tracking` → `OrderTrackingOut`; 404 `"Pedido não encontrado"`.
  - `GET /orders/{id}/status-history` → `list[PedidoStatusHistoricoOut]`, paginado.

> **O construtor opera sobre o status do CONTRATO, não sobre o interno.** O do legacy usa `ORDER_FLOW` de cinco valores; aqui a entrada é `status_do_contrato(order.status)` e o fluxo é `FLUXO_CONTRATO`. E há um caso novo que o legacy não tem: **`cancelled` não está em `FLUXO_CONTRATO`**, então `_step_status` e `_COPY` precisam tratá-lo antes de qualquer `.index()`, senão o rastreio de um pedido cancelado estoura `ValueError` e vira 500.

- [ ] **Step 1: Porte os seis arquivos de teste (Red)**

```bash
cd /home/elias/programming/fiap/estuda_app/back-end
for f in builders directions routes routing schemas services; do
  cp legacy/tests/test_tracking_$f.py commerce-service/tests/test_tracking_$f.py
done
```

Adaptações: sem `/api`; `app.modules.tracking.*` → `app.services.rastreio_*` / `app.schemas.rastreio` / `app.routers.rastreio`; `app.modules.orders.models.Order` → `app.models.pedido.Order`; `OrderStatus.SEPARATING` → `StatusContrato.SEPARATING`; o seed de pedido usa o status **interno** (`StatusPedido.EM_SEPARACAO.value`), não o do contrato.

Acrescente o teste que o legacy não tem, porque `cancelled` não existe lá:

```python
def test_tracking_of_a_cancelled_order_does_not_raise():
    """`cancelled` não está em FLUXO_CONTRATO. Um `.index()` sobre ele
    levantaria ValueError, e o rastreio viraria 500."""
    order = _order_falso(status=StatusPedido.CANCELADO.value)
    tracking = build_order_tracking(order)
    assert tracking.headline == "Pedido cancelado"
    assert all(s.status == TrackingStepStatus.PENDING for s in tracking.steps)
```

- [ ] **Step 2: Rode e confirme que falha**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Porte os schemas**

Copie `legacy/app/modules/tracking/schemas.py` e `enums.py` para `back-end/commerce-service/app/schemas/rastreio.py` (junte os dois; o serviço não tem um `enums.py` por módulo). Nenhum campo muda — este é o contrato que a tela renderiza, e o docstring do legacy já diz que ele é **do app**, não do backend.

- [ ] **Step 4: Porte o construtor, adaptado ao contrato de seis valores**

Em `back-end/commerce-service/app/services/rastreio_builder.py`, copie de `legacy/app/modules/tracking/builders.py` e mude:

```python
from app.models.pedido import Order
from app.schemas.rastreio import (
    KitItemOut,
    OrderTrackingOut,
    TrackingLocationOut,
    TrackingStepOut,
    TrackingStepStatus,
)
from app.services.status_pedido import FLUXO_CONTRATO, StatusContrato, status_do_contrato

_CARRIER = "Logistics Intel Express"
_DELIVERY_WINDOW = timedelta(days=4)

_STEPS: tuple[tuple[str, str, StatusContrato], ...] = (
    ("confirmed", "Confirmado", StatusContrato.CONFIRMED),
    ("separating", "Em separação", StatusContrato.SEPARATING),
    ("out_for_delivery", "Saiu para entrega", StatusContrato.OUT_FOR_DELIVERY),
    ("delivered", "Entregue", StatusContrato.DELIVERED),
)

_COPY: dict[StatusContrato, tuple[str, str]] = {
    StatusContrato.PENDING: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    StatusContrato.CONFIRMED: (
        "Pedido confirmado",
        "Recebemos seu pedido e já estamos preparando tudo.",
    ),
    StatusContrato.SEPARATING: (
        "Em separação",
        "Estamos separando os itens do seu pedido com carinho.",
    ),
    StatusContrato.OUT_FOR_DELIVERY: (
        "Saiu para entrega",
        "Seu pedido está a caminho do seu endereço. Chega já já!",
    ),
    StatusContrato.DELIVERED: (
        "Pedido entregue",
        "Seu pedido foi entregue. Bons estudos!",
    ),
    # Entrada que o legacy não tem: lá `cancelled` não existe. Sem ela,
    # `_COPY[status]` levantaria KeyError e o rastreio de um pedido
    # cancelado viraria 500.
    StatusContrato.CANCELLED: (
        "Pedido cancelado",
        "Este pedido foi cancelado. Se você não reconhece o cancelamento, "
        "fale com o suporte.",
    ),
}


def _step_status(atual: StatusContrato, passo: StatusContrato) -> TrackingStepStatus:
    """Onde um passo da timeline está em relação ao status real do pedido."""
    # `CANCELLED` não pertence a FLUXO_CONTRATO — `.index()` sobre ele
    # levantaria ValueError. Um pedido cancelado não tem passo corrente: a
    # timeline inteira fica pendente e o headline conta o que houve.
    if atual == StatusContrato.CANCELLED:
        return TrackingStepStatus.PENDING
    if atual == StatusContrato.DELIVERED:
        return TrackingStepStatus.DONE

    idx_atual = FLUXO_CONTRATO.index(atual)
    idx_passo = FLUXO_CONTRATO.index(passo)
    if idx_passo < idx_atual:
        return TrackingStepStatus.DONE
    if idx_passo == idx_atual:
        return TrackingStepStatus.CURRENT
    # PENDING (índice 0) não tem passo visível próprio: expõe CONFIRMED como
    # o ativo, para a tela nunca mostrar uma timeline toda pendente.
    if idx_atual == 0 and passo == StatusContrato.CONFIRMED:
        return TrackingStepStatus.CURRENT
    return TrackingStepStatus.PENDING
```

e em `build_order_tracking`, a primeira linha vira:

```python
    status = status_do_contrato(order.status)
```

O resto (timestamps, `estimated_arrival`, `location`, `kit`, `carrier`) fica **literalmente** como no legacy, com `order.items` já trazendo `product_name`.

> `_LOCATION_NAME` e `at_destination` continuam checando `OUT_FOR_DELIVERY`/`DELIVERED`; `cancelled` cai no `_DEFAULT_LOCATION_NAME`, que é o comportamento certo.

- [ ] **Step 5: Escreva o router e mude o histórico de lugar**

Crie `back-end/commerce-service/app/routers/rastreio.py`:

```python
router = APIRouter(prefix="/orders", tags=["tracking"])


@router.get("/{order_id}/tracking", response_model=OrderTrackingOut)
async def rastreio_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderTrackingOut:
    """Tudo que a tela de rastreio precisa renderizar.

    Esta rota ANTES devolvia o histórico de status. O app espera o objeto da
    tela, então a réplica exata fica com a rota e o histórico se mudou para
    `GET /orders/{id}/status-history` — ver "Correções ao design da fase 1"
    no spec da fase 2.
    """
    try:
        order = await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    return build_order_tracking(order)
```

Em `app/routers/pedidos.py`, a rota antiga vira:

```python
@router.get("/{order_id}/status-history", response_model=list[PedidoStatusHistoricoOut])
async def historico_status(
    order_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Histórico completo dos NOVE estados internos.

    Mudou de `/tracking` para cá na fase 2: aquela rota é o objeto que a tela
    do app renderiza. Aqui o aluno vê a trilha real da operação — é a única
    superfície onde `CONFIRMADO` é observável, já que `confirm-payment`
    encadeia até `AGUARDANDO_SEPARACAO`.
    """
    # Garante que o pedido é do aluno antes de expor o histórico.
    try:
        await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    historico = await db.execute(
        select(PedidoStatusHistorico)
        .where(PedidoStatusHistorico.order_id == order_id)
        .order_by(PedidoStatusHistorico.criado_em.asc())
        .limit(limit)
        .offset(offset)
    )
    return historico.scalars().all()
```

Registre `rastreio.router` em `app/main.py`. **Ordem importa:** `rastreio` monta `/orders/{id}/tracking`; `pedidos` monta `/orders/{id}`. Se `pedidos` for incluído primeiro, `/orders/{id}` não engole `/orders/{id}/tracking` (paths diferentes), então a ordem é indiferente aqui — mas confirme com `curl` no portão.

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS, incluindo os seis arquivos de tracking portados.

- [ ] **Step 7: Prove o caso cancelado (constraint 11)**

Remova a cláusula `if atual == StatusContrato.CANCELLED` de `_step_status`, rode `test_tracking_of_a_cancelled_order_does_not_raise`, confirme `ValueError: tuple.index(x): x not in tuple`, reaplique.

- [ ] **Step 8: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): serve the tracking screen object at /orders/{id}/tracking

That path used to return the status history; the app expects the object it
renders, so the history moves to /orders/{id}/status-history. This replaces
a sentence in the phase 1 design, written before the Flutter code was read.

The builder works on the six contract statuses. cancelled is not in the
visible flow, so it is handled before any .index() — otherwise tracking a
cancelled order would raise ValueError and become a 500.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C9: rota no mapa e previsão de ETA

`GET /orders/{id}/route` chama a Google Directions API a partir do snapshot de endereço e memoiza no Redis. `POST /orders/{id}/predict-eta` faz a matemática de Haversine.

**Esta é a task que finalmente lê `google_maps_api_key`** — o campo que a task 22 do bloco A foi instruída a **não** remover.

**Files:**
- Create: `back-end/commerce-service/app/services/directions.py`
- Create: `back-end/commerce-service/app/services/rastreio_routing.py`
- Modify: `back-end/commerce-service/app/routers/rastreio.py`
- Modify: `back-end/commerce-service/app/config.py`
- Modify: `back-end/commerce-service/app/exceptions.py` (`RouteUnavailable`)
- Test: `tests/test_tracking_directions.py`, `test_tracking_routing.py`, `test_tracking_routes.py` (já portados em C8)

**Interfaces:**
- Produces:
  - `directions.fetch_directions(client, *, origin, destination, api_key) -> DirectionsResult`
  - `rastreio_routing.predict_route(*, courier, destination, average_speed_kmh, urban_route_factor) -> RoutePrediction`
  - `services.rota_do_pedido(db, redis, user_id: uuid.UUID, order_id: uuid.UUID) -> RouteOut` — levanta `OrderNotFound` ou `RouteUnavailable`
  - `services.prever_eta(user_id: uuid.UUID, order_id: uuid.UUID, courier: CourierLocationIn) -> ETAPredictionOut`
  - `RouteUnavailable` em `app/exceptions.py`
  - `GET /orders/{id}/route` → `RouteOut`; **503 `"Rota indisponível no momento"`** quando falta chave, falta endereço, ou o provedor falha.
  - `POST /orders/{id}/predict-eta` → `ETAPredictionOut`.
  - `settings.tracking_average_speed_kmh: float = 30.0`, `tracking_urban_route_factor: float = 1.4`, `tracking_route_cache_ttl_seconds: int = 21600`

> **Os dois módulos e o serviço vivem em arquivos diferentes de propósito:** `directions.py` é a fronteira HTTP (só fala com o Google), `rastreio_routing.py` é matemática pura (Haversine, sem I/O), e `services/rastreio.py` é quem carrega o pedido e orquestra. É a mesma separação do legacy, e é o que torna `test_tracking_routing.py` um teste sem rede.

- [ ] **Step 1: Confirme que `google_maps_api_key` ainda está lá**

Run: `cd back-end/commerce-service && grep -n google_maps_api_key app/config.py && grep -n GOOGLE_MAPS ../docker-compose.yml`

Expected: o campo existe e o compose o liga a `GOOGLE_MAPS_API_PLATAFORM`. **Se sumiu, a task 22 do bloco A o removeu apesar do aviso** — devolva-o com o mesmo nome e o compose intacto, e registre o incidente.

- [ ] **Step 2: Rode os testes já portados (Red)**

Run: `cd back-end/commerce-service && uv run pytest tests/test_tracking_directions.py tests/test_tracking_routing.py -v`

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Porte `directions.py` e `routing.py`**

Copie `legacy/app/modules/tracking/directions.py` → `app/services/directions.py` e `legacy/app/modules/tracking/routing.py` → `app/services/rastreio_routing.py`. Mudanças: os imports de `RouteUnavailable` apontam para `app.exceptions`; `settings.TRACKING_*` vira minúsculo.

**Não mude a lógica.** A validação de `end_location` ausente (que falha rápido em vez de cair em `(0, 0)`) e a conversão de qualquer falha em `RouteUnavailable` são o que mantém o 503 limpo.

- [ ] **Step 4: Acrescente os settings**

```python
    # Rastreio. Os três batem com `legacy/app/core/config.py:70,71,80` — a
    # suíte portada asserta sobre eles, então mudar qualquer um aqui faz um
    # teste de paridade falhar (que é o comportamento certo).
    tracking_average_speed_kmh: float = 30.0
    tracking_urban_route_factor: float = 1.4
    tracking_route_cache_ttl_seconds: int = 21600  # 6 horas
```

Confirme antes de seguir: `grep -n "TRACKING_" back-end/legacy/app/core/config.py` tem que devolver exatamente `30.0`, `1.4` e `21600`. Se divergir, o legacy mudou depois deste plano — use o valor de lá, não o daqui.

- [ ] **Step 5: Escreva o serviço de rota**

Em `app/services/rastreio.py` (ou no fim de `rastreio_builder.py` — escolha um e seja consistente), porte `get_order_route` e `predict_eta` de `legacy/app/modules/tracking/services.py`, com:

- `orders_services.get_order(session, user_id, parsed_id)` → `services.buscar_pedido(db, user_id, order_id)`.
- O `try: uuid.UUID(order_id) except ValueError` **sai**: o path param já é `uuid.UUID`, então o FastAPI devolve 422 antes de chegar aqui. Isso é uma divergência do legacy (que aceita string e devolve 404) — **registre-a** e prefira o 422, que é a resposta honesta para um id malformado.
- `settings.GOOGLE_MAPS_API_PLATAFORM` → `settings.google_maps_api_key`.
- `_MOCK_ORIGIN`, `_MOCK_DESTINATION`, `_ORIGIN_LABEL`, `_DESTINATION_LABEL`, `_ROUTE_CACHE_PREFIX` e `_destination_query` vêm literais.

> `_MOCK_DESTINATION` é usado **só** por `predict-eta`, que não tem consumidor no app ainda (é para um futuro app de entregador). O comentário do legacy diz isso; preserve-o, porque é ele que impede alguém de achar que a rota real está mockada.

- [ ] **Step 6: Escreva as duas rotas**

```python
@router.get("/{order_id}/route", response_model=RouteOut)
async def rota_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> RouteOut:
    """Rota de rua do centro de distribuição até o endereço do pedido."""
    try:
        return await services.rota_do_pedido(db, redis, uuid.UUID(user["sub"]), order_id)
    except OrderNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    except RouteUnavailable as exc:
        # Provedor fora do ar, sem cota, sem rota, sem endereço ou chave não
        # configurada — 503 limpo, nunca ecoando o detalhe do provedor (que
        # pode conter a chave ou o endereço completo).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rota indisponível no momento",
        ) from exc


@router.post("/{order_id}/predict-eta", response_model=ETAPredictionOut)
async def prever_eta(
    order_id: uuid.UUID,
    payload: CourierLocationIn,
    user: dict = Depends(get_current_user),
) -> ETAPredictionOut:
    """Estimativa do tempo restante dada a posição atual do entregador."""
    return await services.prever_eta(uuid.UUID(user["sub"]), order_id, payload)
```

- [ ] **Step 7: Rode e confirme que passa**

Run: `cd back-end/commerce-service && uv run pytest -q`

Expected: PASS, incluindo os seis arquivos de tracking.

- [ ] **Step 8: Prove que a chave nunca vaza (constraint 11)**

```python
async def test_route_503_never_echoes_the_provider_detail(client, db_session, monkeypatch):
    pedido = await _seed_pedido_com_endereco(db_session, user_id=ALUNO)

    async def _falha(*args, **kwargs):
        raise RouteUnavailable("directions status: REQUEST_DENIED key=SEGREDO")

    monkeypatch.setattr("app.services.rastreio.directions.fetch_directions", _falha)

    response = await client.get(
        f"/orders/{pedido.id}/route", headers=headers_for("student", sub=ALUNO)
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Rota indisponível no momento"
    assert "SEGREDO" not in response.text
```

Troque o `detail` do handler por `str(exc)`, rode, confirme que `SEGREDO` aparece, reaplique.

- [ ] **Step 9: Commit**

```bash
cd back-end/commerce-service && uv run ruff check . && uv run ruff format . && cd ../..
git add back-end/commerce-service/
git diff --staged
git commit -m "feat(commerce): add the order route map and the ETA prediction

The route is built from the order's address snapshot and memoized in Redis,
because Directions calls are paid and origin/destination are fixed per
order. Any provider failure becomes a clean 503 that never echoes the
provider detail — it can carry the API key or the full address.

This is what finally reads google_maps_api_key, the setting phase 2A was
told to leave standing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C10: `pedido_id` deixa de ser inteiro nos cinco eventos

`order.created`, `order.status_changed`, `order.stock_issue`, `order.delivery_delayed`, `order.occurrence_resolved`. As **chaves** continuam em português; só o **tipo** muda.

Isso fecha um item da fase 4: o backlog registra que `data.order_id` chega como UUID string do legacy e como inteiro do notification-service. Depois desta task, os dois concordam.

**Files:**
- Modify: `back-end/commerce-service/app/routers/pedidos.py`, `ocorrencias.py`, `separacao.py`
- Modify: `back-end/notification-service/app/models/notificacao.py`
- Modify: `back-end/notification-service/app/events/consumer.py`
- Create: `back-end/notification-service/alembic/versions/<hash>_notificacao_pedido_id_uuid.py`
- Test: `back-end/commerce-service/tests/`, `back-end/notification-service/tests/test_consumer.py`, `back-end/analytics-service/tests/test_consumer.py`

**Interfaces:**
- Produces: todo payload de evento de pedido carrega `"pedido_id": str(uuid)`.
  `Notificacao.pedido_id` vira `UUID(as_uuid=True)`, nullable.

> O `analytics-service` grava `payload` como JSONB e não tipa `pedido_id` — ele não precisa de mudança de schema, só de um teste que trave o tipo. O `notification-service` **tem** uma coluna tipada.

- [ ] **Step 1: Escreva os testes que falham**

No commerce, um teste por produtor:

```python
@pytest.mark.parametrize(
    "routing_key",
    [
        "order.created",
        "order.status_changed",
        "order.stock_issue",
        "order.delivery_delayed",
        "order.occurrence_resolved",
    ],
)
async def test_every_order_event_carries_pedido_id_as_a_uuid_string(
    routing_key, client, db_session, _stub_publish_event
):
    """As CHAVES ficam em português — renomeá-las dessincronizaria produtor e
    consumidor sem nenhum cliente pedindo. Só o tipo muda."""
    await _exercitar_o_produtor_de(routing_key, client, db_session)

    payloads = [p for key, p in _stub_publish_event if key == routing_key]
    assert payloads, f"nada publicou {routing_key}"
    for payload in payloads:
        assert isinstance(payload["pedido_id"], str)
        uuid.UUID(payload["pedido_id"])
```

`_exercitar_o_produtor_de` é o despachante que aciona a rota dona de cada evento. Escreva-o no mesmo arquivo:

```python
async def _exercitar_o_produtor_de(routing_key: str, client, db_session) -> None:
    """Aciona a rota que publica `routing_key`.

    Um despachante em vez de cinco testes quase iguais: o que está sendo
    travado é uma propriedade do PAYLOAD, idêntica nos cinco, e o que muda é
    só como se chega lá.
    """
    if routing_key == "order.created":
        produto = await _seed_produto(db_session)
        await client.post(
            "/cart/items",
            json={"product_id": str(produto.id), "quantity": 1},
            headers=headers_for("student", sub=ALUNO),
        )
        await client.post("/orders", json={}, headers=headers_for("student", sub=ALUNO))

    elif routing_key == "order.status_changed":
        pedido = await _seed_pedido_com_endereco(db_session)
        await client.patch(
            f"/admin/orders/{pedido.id}/confirm-payment", headers=headers_for("admin", sub=ADMIN)
        )

    elif routing_key == "order.stock_issue":
        produto = await _seed_produto(db_session)
        pedido = await _seed_pedido_com_endereco(
            db_session, status=StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A
        )
        await client.post(
            "/occurrences/stock-shortage",
            json={"pedido_id": str(pedido.id), "produto_id": str(produto.id), "motivo": "sem estoque"},
            headers=headers_for("separador", sub=PICKER_A),
        )

    elif routing_key == "order.delivery_delayed":
        pedido = await _seed_pedido_com_endereco(
            db_session, status=StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
        )
        await client.post(
            "/occurrences/delivery-delay",
            json={
                "pedido_id": str(pedido.id),
                "nova_data_sugerida": "2026-08-20T12:00:00+00:00",
                "motivo": "chuva",
            },
            headers=headers_for("entregador", sub=DELIVERER_A),
        )

    elif routing_key == "order.occurrence_resolved":
        pedido = await _seed_pedido_com_endereco(
            db_session, status=StatusPedido.EM_TRANSITO.value, deliverer_id=DELIVERER_A
        )
        criar = await client.post(
            "/occurrences/delivery-delay",
            json={
                "pedido_id": str(pedido.id),
                "nova_data_sugerida": "2026-08-20T12:00:00+00:00",
                "motivo": "chuva",
            },
            headers=headers_for("entregador", sub=DELIVERER_A),
        )
        await client.post(
            f"/occurrences/{criar.json()['id']}/resolve",
            json={"resolucao": "aceitar_nova_data"},
            headers=headers_for("student", sub=ALUNO),
        )

    else:
        raise AssertionError(f"routing key sem produtor mapeado: {routing_key}")
```

> Confira os corpos de `FaltaEstoqueIn` e `AtrasoEntregaIn` em `app/schemas/ocorrencia.py` antes de rodar — se algum campo mudou nas tasks anteriores, o `POST` devolve 422 e o `assert payloads` falha com "nada publicou", que é uma mensagem enganosa. O `else` que levanta existe para que uma routing key nova no `parametrize` sem produtor mapeado falhe alto, em vez de passar com zero payloads.

O helper `_fake_message` do notification e do analytics já existe nas suítes dos dois serviços (o analytics ganhou o dele na task 12 do bloco A). Reaproveite; não crie um segundo.

No notification-service:

```python
async def test_order_notification_stores_a_uuid_order_id(db_session):
    pedido_id = str(uuid.uuid4())
    await handle_order_status_changed(
        _fake_message(
            {
                "pedido_id": pedido_id,
                "aluno_id": str(uuid.uuid4()),
                "status": "EM_TRANSITO",
            }
        )
    )
    result = await db_session.execute(select(Notificacao))
    notificacao = result.scalar_one()
    assert str(notificacao.pedido_id) == pedido_id
```

No analytics-service:

```python
async def test_order_event_payload_keeps_pedido_id_as_a_string(db_session):
    pedido_id = str(uuid.uuid4())
    await handle_event(_fake_message("order.created", {"pedido_id": pedido_id, "aluno_id": "x"}))
    result = await db_session.execute(select(EventLog))
    assert result.scalar_one().payload["pedido_id"] == pedido_id
```

- [ ] **Step 2: Rode e confirme que falham**

Expected: no commerce, `assert isinstance(1, str)`. No notification, `DataError`/`invalid input syntax for type integer`.

- [ ] **Step 3: Converta nos produtores**

Em `pedidos.py`, `ocorrencias.py` (quatro publishes) e `separacao.py::transicionar_pedido`, todo `"pedido_id": pedido.id` vira `"pedido_id": str(pedido.id)`.

Acrescente, num só lugar por arquivo, o comentário:

```python
            # `str(...)`: `orders.id` é UUID desde a fase 2, e JSON não tem
            # tipo UUID. A CHAVE continua `pedido_id` de propósito — renomeá-la
            # dessincronizaria produtor e consumidor sem nenhum cliente pedindo.
```

- [ ] **Step 4: Troque o tipo da coluna no notification-service**

Em `back-end/notification-service/app/models/notificacao.py`:

```python
    # UUID desde a fase 2: `orders.id` do commerce virou UUID. Antes era
    # Integer, e o backlog da fase 1 registrou que `data.order_id` chegava
    # como UUID string vindo do legacy e como inteiro vindo daqui — mesma
    # chave, tipo diferente. Depois desta mudança os dois concordam.
    pedido_id = Column(UUID(as_uuid=True), nullable=True, index=True)
```

Gere a migration. `commerce_db` está vazio, mas `notification_db` **pode não estar** — meça antes:

```bash
cd back-end && docker compose exec -T postgres psql -U edu -d notification_db -c \
  "SELECT count(*) FROM notificacoes WHERE pedido_id IS NOT NULL;"
```

- **0:** `ALTER ... TYPE uuid USING NULL` basta.
- **> 0:** os ids antigos são inteiros que não correspondem a nada no schema novo. Zere-os (`SET pedido_id = NULL`) e diga isso no docstring da revision — eles apontam para pedidos que a reconstrução do commerce apagou.

- [ ] **Step 5: Rode as três suítes**

Run:
```bash
cd back-end/commerce-service && uv run pytest -q
cd ../notification-service && uv run pytest -q
cd ../analytics-service && uv run pytest -q
```

Expected: PASS nas três.

- [ ] **Step 6: Prove ponta a ponta com o stack de pé**

```bash
cd back-end && make stack-up
# Crie um pedido pelo commerce com um bearer de aluno, depois:
docker compose exec -T postgres psql -U edu -d analytics_db -c \
  "SELECT payload->>'pedido_id' FROM event_log WHERE tipo='order.created' ORDER BY criado_em DESC LIMIT 1;"
docker compose exec -T postgres psql -U edu -d notification_db -c \
  "SELECT pedido_id FROM notificacoes ORDER BY criado_em DESC LIMIT 1;"
```

Expected: os dois mostram o **mesmo** UUID. É a prova de que produtor e consumidor concordam — o item da fase 4 fechado.

- [ ] **Step 7: Commit (três commits, três serviços)**

```bash
git add back-end/commerce-service/
git commit -m "refactor(commerce): publish pedido_id as a UUID string

orders.id is a UUID since phase 2 and JSON has no UUID type. The payload
KEYS stay Portuguese on purpose: renaming them would desynchronize producer
and consumer with no client asking for it.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git add back-end/notification-service/
git commit -m "refactor(notification): store pedido_id as a UUID

Closes a phase 4 item: data.order_id arrived as a UUID string from the
legacy and as an integer from here — same key, different type. Now they
agree.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git add back-end/analytics-service/
git commit -m "test(analytics): lock pedido_id as a string in the event log

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C11: o caso `cancelled` no Flutter

A única mudança de Dart da fase 2. É **aditiva**: fica código morto enquanto o app fala com o legacy (que nunca emite `cancelled`), e no dia do corte a tela já está certa.

**Files:**
- Modify: `front-end-flutter/lib/features/marketplace/domain/order_summary.dart`
- Modify: `front-end-flutter/lib/features/marketplace/presentation/orders_provider.dart`
- Modify: `front-end-flutter/lib/features/marketplace/presentation/orders_screen.dart` (se o stepper precisar)
- Test: `front-end-flutter/test/` (siga o que existir; se não houver teste desse model, escreva um)

> **O spec chamou isso de "uma linha".** Não é. Os dois `switch` de `order_summary.dart` são **exaustivos** (sem `default`), então o compilador do Dart rejeita um caso não tratado — o que é exatamente o que queremos. São: o valor do enum, o `case` em `_statusFromJson`, um braço em `stepIndex`, um braço em `statusLabel`, e o predicado que tira o pedido cancelado da lista de ativos. Registre a diferença; ela não muda o escopo, mas muda a estimativa.

- [ ] **Step 1: Escreva o teste que falha**

Em `front-end-flutter/test/features/marketplace/order_summary_test.dart` (crie se não existir):

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:<pacote>/features/marketplace/domain/order_summary.dart';

void main() {
  test('um pedido cancelado não é lido como pendente', () {
    final order = OrderSummary.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'total': '99.80',
      'status': 'cancelled',
      'created_at': '2026-08-05T12:00:00Z',
      'items': [],
    });

    expect(order.status, OrderSummaryStatus.cancelled);
    expect(order.statusLabel, 'Cancelado');
  });

  test('um pedido cancelado não conta como ativo', () {
    final order = OrderSummary.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'total': '99.80',
      'status': 'cancelled',
      'created_at': '2026-08-05T12:00:00Z',
      'items': [],
    });

    expect(order.isFinished, isTrue);
  });

  test('um status desconhecido continua caindo em pendente', () {
    final order = OrderSummary.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'total': '10.00',
      'status': 'estado_que_nao_existe',
      'created_at': '2026-08-05T12:00:00Z',
      'items': [],
    });

    expect(order.status, OrderSummaryStatus.pending);
  });
}
```

> Substitua `<pacote>` pelo nome real em `pubspec.yaml`.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd front-end-flutter && flutter test test/features/marketplace/order_summary_test.dart`

Expected: erro de compilação — `OrderSummaryStatus.cancelled` não existe.

- [ ] **Step 3: Acrescente o caso**

```dart
/// Status de entrega de um pedido. Espelha `StatusContrato` do backend
/// (pending -> confirmed -> separating -> out_for_delivery -> delivered),
/// mais `cancelled`, que é a saída do fluxo e não um passo dele.
enum OrderSummaryStatus {
  pending,
  confirmed,
  separating,
  outForDelivery,
  delivered,
  cancelled,
}

OrderSummaryStatus _statusFromJson(String? raw) {
  switch (raw) {
    case 'confirmed':
      return OrderSummaryStatus.confirmed;
    case 'separating':
      return OrderSummaryStatus.separating;
    case 'out_for_delivery':
      return OrderSummaryStatus.outForDelivery;
    case 'delivered':
      return OrderSummaryStatus.delivered;
    // Sem este caso, o `default` abaixo faria um pedido cancelado aparecer
    // como "Pendente", no passo 0 do stepper, para sempre — e ele nunca
    // sairia da lista de pedidos ativos.
    case 'cancelled':
      return OrderSummaryStatus.cancelled;
    case 'pending':
    default:
      return OrderSummaryStatus.pending;
  }
}
```

```dart
  /// Pedido que saiu do fluxo: entregue OU cancelado.
  ///
  /// `isDelivered` sozinho não serve para dividir "ativos" de "concluídos":
  /// um pedido cancelado não está entregue, mas também não está em curso.
  bool get isFinished =>
      status == OrderSummaryStatus.delivered ||
      status == OrderSummaryStatus.cancelled;

  int get stepIndex {
    switch (status) {
      case OrderSummaryStatus.pending:
      case OrderSummaryStatus.confirmed:
      case OrderSummaryStatus.separating:
        return 0;
      case OrderSummaryStatus.outForDelivery:
        return 1;
      case OrderSummaryStatus.delivered:
      // Um pedido cancelado não está no stepper. Devolve o último índice
      // para o widget não renderizar barra de progresso pela metade; quem
      // decide não mostrar o stepper é a tela, via `isFinished`.
      case OrderSummaryStatus.cancelled:
        return 2;
    }
  }

  String get statusLabel {
    switch (status) {
      case OrderSummaryStatus.pending:
        return 'Pendente';
      case OrderSummaryStatus.confirmed:
        return 'Confirmado';
      case OrderSummaryStatus.separating:
        return 'Em separação';
      case OrderSummaryStatus.outForDelivery:
        return 'Saiu para entrega';
      case OrderSummaryStatus.delivered:
        return 'Entregue';
      case OrderSummaryStatus.cancelled:
        return 'Cancelado';
    }
  }
```

`isDelivered` fica como está — `order_tracking/presentation/order_provider.dart:77,93` o usa para parar o polling, e ali a semântica certa é "entregue". Mas o polling de um pedido cancelado nunca pararia; acrescente `|| isCancelled` **lá**, ou troque por `isFinished` se o model de rastreio tiver o mesmo predicado. Leia `order_tracking/domain/order_model.dart:185` antes de decidir; ele tem um `isDelivered` próprio.

Em `orders_provider.dart:38,42`:

```dart
      _orders.where((o) => !o.isFinished).toList();
...
      _orders.where((o) => o.isFinished).toList();
```

- [ ] **Step 4: Rode teste e análise**

Run: `cd front-end-flutter && flutter test && flutter analyze lib/`

Expected: PASS e zero avisos. Se `flutter analyze` acusar `non_exhaustive_switch`, um dos dois `switch` ficou sem o braço novo — é o compilador fazendo o trabalho que o `default` do `_statusFromJson` não faz.

- [ ] **Step 5: Confirme que é código morto hoje**

Run: `cd back-end/legacy && grep -rn "cancelled" app/modules/orders/enums.py`

Expected: nenhuma ocorrência. O legacy não emite `cancelled`, então esta mudança não altera nada do que o app vê hoje — que é o ponto.

- [ ] **Step 6: Commit**

```bash
cd /home/elias/programming/fiap/estuda_app
git add front-end-flutter/lib/features/marketplace/ front-end-flutter/test/
git diff --staged
git commit -m "feat(marketplace): handle a cancelled order in the app

The enum fell back to pending for any unknown status, so a cancelled order
would have rendered as active on step 0 forever and never left the active
list. Additive and dead until the cutover: the legacy never emits
cancelled.

Both switches are exhaustive, so the compiler required the new arm in each
— which is why this is five edits and not the one line the spec estimated.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task C12: portão do bloco C

**Files:** nenhum. Produz o relatório que a fase 4 vai ler.

- [ ] **Step 1: As 17 suítes do critério de aceite**

O spec define o critério binário: **17 arquivos de teste do legacy entram no critério**. Confira um a um:

| Origem | Arquivo | Bloco | Portado? |
|---|---|---|---|
| `modules/products/` | `test_routes.py` | B | |
| | `test_services.py` | B | |
| `modules/cart/` | `test_routes.py` | B | |
| | `test_services.py` | B | |
| `modules/orders/` | `test_routes.py` | C | |
| | `test_services.py` | C | |
| `modules/payment_methods/` | `test_routes.py` | B | |
| `modules/support/` | `test_routes.py` | D | |
| `tests/` | `test_tracking_builders.py` | C | |
| | `test_tracking_directions.py` | C | |
| | `test_tracking_routes.py` | C | |
| | `test_tracking_routing.py` | C | |
| | `test_tracking_schemas.py` | C | |
| | `test_tracking_services.py` | C | |
| `seeds/` | `test_products_seed.py` | B | |
| `core/` | `test_media.py` | B | |
| | `test_storage.py` (leitura) | B | |

Marque cada linha. **Dezesseis destes já devem estar verdes ao fim de C** — `modules/support/test_routes.py` é o bloco D.

E os **três adiados**, que têm que estar ausentes e registrados: `modules/products/test_image_upload.py`, `modules/orders/test_lifecycle.py`, `modules/orders/test_status_pipeline.py`.

- [ ] **Step 2: Frota verde**

Run: `make services-test && make services-lint && cd front-end-flutter && flutter test && flutter analyze lib/`

- [ ] **Step 3: Sync-check dos cinco bancos**

Mesmo procedimento das tasks anteriores, com o `grep -l compare_server_default */alembic/env.py | wc -l` → 5 antes de confiar no resultado.

- [ ] **Step 4: Reconciliação campo a campo contra o legacy**

Esta é a razão de o bloco existir. Com o stack de pé, um bearer do legacy e um do commerce:

```bash
LEG="Authorization: Bearer <token legacy>"
NEW="Authorization: Bearer <token commerce>"

for rota in "orders?limit=2" "payment-methods"; do
  echo "=== /$rota"
  curl -s -H "$LEG" "localhost:8001/api/$rota" | python -c "import json,sys; print(sorted(json.load(sys.stdin)[0].keys()))" 2>/dev/null
  curl -s -H "$NEW" "localhost:8103/$rota"    | python -c "import json,sys; print(sorted(json.load(sys.stdin)[0].keys()))" 2>/dev/null
done
```

As listas de chaves têm que ser **idênticas**. Faça o mesmo para `/orders/{id}/tracking` (objeto, não array) comparando `sorted(json.load(sys.stdin).keys())`, e para `steps[0]`.

Registre qualquer diferença. Uma diferença aqui é um bug do bloco C, não uma observação.

- [ ] **Step 5: Prove o ciclo completo à mão**

Com o stack de pé:

1. Aluno: `POST /cart/items` → `POST /orders` (com `address_id` real) → confira `status: "pending"` em `GET /orders`.
2. Admin: `PATCH /admin/orders/{id}/confirm-payment` → confira `status: "separating"` em `GET /orders` e `["CONFIRMADO", "AGUARDANDO_SEPARACAO"]` em `GET /orders/{id}/status-history`.
3. Separador: `PATCH /picking/{id}/start` → `PATCH /picking/{id}/finish`.
4. Entregador: `PATCH /delivery/{id}/collect` → `status: "out_for_delivery"` → `PATCH /delivery/{id}/deliver` → `status: "delivered"`.
5. `GET /orders/{id}/tracking` em cada etapa: confira que o passo corrente anda.
6. Um pedido separado, cancelado via ocorrência: confira `status: "cancelled"` e que `GET /orders/{id}/tracking` responde **200**, não 500.

- [ ] **Step 6: Relate**

Relatório com: a tabela das 17 preenchida, o resultado da reconciliação de chaves, o log do ciclo completo, a lista consolidada de asserções adaptadas (B0 + as deste bloco), e os três carve-outs de fase 3 nomeados.

Nada a commitar.

---

## Notas de sequência para o bloco D

- O bloco D é independente deste. Ele só precisa do bloco A (task 19, nome da dependência) e da entrada `"support": "chatbot"` que já existe no `SERVICE_MAP` do gateway.
- `modules/support/test_routes.py` é a 17ª suíte do critério de aceite. Sem o bloco D, o critério da fase 2 não fecha.
