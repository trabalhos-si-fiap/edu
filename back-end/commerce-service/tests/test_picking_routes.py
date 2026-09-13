import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import insert

from app.config import settings
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order, OrderItem
from app.models.transportadora import Carrier
from app.services.status_pedido import StatusPedido

# Precisa bater com CANDIDATOS_FILA_MAXIMO em app/routers/separacao.py — mas
# como LITERAL aqui, não como import da constante (nunca alimentar a
# constante da implementação de volta no teste que a fixa).
CANDIDATOS_FILA_MAXIMO_ESPERADO = 500


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


async def test_picking_queue_requires_authentication(client):
    assert (await client.get("/picking/queue")).status_code == 403


async def test_picking_queue_forbids_students(client):
    assert (await client.get("/picking/queue", headers=headers_for("student"))).status_code == 403


async def test_picking_queue_allows_separador(client):
    assert (await client.get("/picking/queue", headers=headers_for("separador"))).status_code == 200


async def test_old_portuguese_picking_path_is_gone(client):
    response = await client.get("/separacao/fila", headers=headers_for("separador"))
    assert response.status_code == 404


async def test_picking_queue_rejects_limit_above_the_cap(client):
    response = await client.get("/picking/queue?limit=5000", headers=headers_for("separador"))
    assert response.status_code == 422


# ── Gap de autorização #3: finalizar_separacao/finish não checava posse ──

PICKER_A = "00000000-0000-0000-0000-0000000000a1"
PICKER_B = "00000000-0000-0000-0000-0000000000b2"
ADMIN = "00000000-0000-0000-0000-0000000000a9"


async def _seed_pedido_em_separacao(db_session, separador_id: str | None) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.EM_SEPARACAO.value,
        total=Decimal("100.00"),
        picker_id=separador_id,
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_pedido_aguardando_separacao(db_session) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=StatusPedido.AGUARDANDO_SEPARACAO.value,
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_finish_picking_forbids_a_separador_who_never_claimed_the_order(client, db_session):
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_B)
    )
    assert response.status_code == 403


async def test_finish_picking_allows_the_separador_who_claimed_the_order(client, db_session):
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 200
    assert response.json()["status"] == StatusPedido.AGUARDANDO_COLETA.value


# ── Fix round 1, reviewer finding #2: start must honor a pre-set
# picker_id (e.g. from admin's assign-picker) instead of letting any
# other separador overwrite it on claim. ────────────────────────────────


async def test_start_rejects_a_separador_when_admin_already_assigned_someone_else(
    client, db_session
):
    """Mesmo cenário do reviewer, espelhado para picking: admin atribui o
    pedido a P1 (sem mudar status), e P2 tenta "iniciar" a separação
    depois."""
    pedido = await _seed_pedido_aguardando_separacao(db_session)

    assign_response = await client.patch(
        f"/admin/orders/{pedido.id}/assign-picker?separador_id={PICKER_A}",
        headers=headers_for("admin", sub=ADMIN),
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["picker_id"] == PICKER_A

    hijack_response = await client.patch(
        f"/picking/{pedido.id}/start", headers=headers_for("separador", sub=PICKER_B)
    )
    assert hijack_response.status_code == 403


async def test_start_allows_the_separador_admin_already_assigned(client, db_session):
    pedido = await _seed_pedido_aguardando_separacao(db_session)

    await client.patch(
        f"/admin/orders/{pedido.id}/assign-picker?separador_id={PICKER_A}",
        headers=headers_for("admin", sub=ADMIN),
    )

    response = await client.patch(
        f"/picking/{pedido.id}/start", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 200


# ── Fix round 1, reviewer finding #5: the candidate fetch behind
# /picking/queue must itself be capped, not just the paginated response. ─


async def test_picking_queue_candidate_fetch_is_capped(client, db_session):
    """Semeia mais pedidos do que `CANDIDATOS_FILA_MAXIMO_ESPERADO` e prova
    que o pool de candidatos pontuados/ordenados tem exatamente esse
    tamanho — não o total semeado.

    Todos os pedidos são idênticos em espera/risco (sem itens, portanto
    sem risco de estoque, e criados quase simultaneamente), então
    `priorizar_fila` empata todos os scores; como `list.sort` é estável, a
    ordem final == ordem de chegada do SELECT, que é `created_at ASC, id
    ASC` — ou seja, ordem de inserção. Pedindo `offset=490&limit=200`:
    se o fetch está corretamente limitado ao teto, sobram só os últimos
    `CANDIDATOS_FILA_MAXIMO_ESPERADO - 490 = 10` candidatos; sem o cap
    (bug), sobrariam `total_semeado - 490 = 15`.
    """
    total_semeado = CANDIDATOS_FILA_MAXIMO_ESPERADO + 5
    await db_session.execute(
        insert(Order),
        [
            {
                "user_id": str(uuid.uuid4()),
                "status": StatusPedido.AGUARDANDO_SEPARACAO.value,
                "total": Decimal("100.00"),
            }
            for _ in range(total_semeado)
        ],
    )
    await db_session.commit()

    response = await client.get(
        "/picking/queue?limit=200&offset=490", headers=headers_for("separador")
    )
    assert response.status_code == 200
    assert len(response.json()) == 10


async def test_old_portuguese_finalizar_path_is_gone(client, db_session):
    """Fix round 1 (reviewer finding #1): o pedido usado precisa EXISTIR e
    estar em EM_SEPARACAO com `picker_id=PICKER_A` — a rota antiga
    (`finalizar_separacao`) 404a em "Pedido não encontrado" para QUALQUER
    id inexistente, então um id chumbado como `1` sem seed passaria com
    404 mesmo se o path nunca tivesse sido traduzido. Com um pedido real
    que satisfaz TODAS as pré-condições (existe, dono correto, sem
    ocorrência aberta, transição válida), a rota antiga responderia 200 se
    ainda existisse — o 404 aqui só pode vir da rota não existir mais."""
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)
    response = await client.patch(
        f"/separacao/{pedido.id}/finalizar", headers=headers_for("separador", sub=PICKER_A)
    )
    assert response.status_code == 404


# ── Revisão final de branch, findings 1 e 2 ────────────────────────────────
#
# A suíte herdada nunca pôs DUAS ocorrências abertas no mesmo pedido, e a
# task 5 acrescentou um TERCEIRO produtor independente de linha `ABERTA`
# (`POST /occurrences/carrier`). O smoke test documentado alcança o estado:
# etapa 6 abre uma ocorrência de falta de estoque, etapa 7 abre uma de
# transportadora no MESMO pedido.


async def _abrir_ocorrencia(
    db_session,
    pedido: Order,
    *,
    tipo: str = "FALTA_ESTOQUE",
    transportadora_id: int | None = None,
) -> Ocorrencia:
    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo=tipo,
        status="ABERTA",
        motivo="ocorrência de teste",
        criado_por=uuid.UUID(int=1),
        transportadora_id=transportadora_id,
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)
    return ocorrencia


async def _seed_carrier(db_session) -> Carrier:
    carrier = Carrier(
        name="Rápido Cajamar",
        location="Cajamar, SP",
        email="ops@example.com",
        average_delivery_days=3,
        rating=Decimal("4.5"),
        sla_percentage=Decimal("98.50"),
        status="ACTIVE",
    )
    db_session.add(carrier)
    await db_session.commit()
    await db_session.refresh(carrier)
    return carrier


async def test_finish_with_two_open_student_occurrences_answers_400_not_500(client, db_session):
    """Finding 1: o filtro `(pedido_id, status='ABERTA')` NÃO é único, e
    `scalar_one_or_none()` sobre ele levanta `MultipleResultsFound` — 500 sem
    handler para o separador, num estado que o seed torna alcançável."""
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)
    await _abrir_ocorrencia(db_session, pedido)
    await _abrir_ocorrencia(db_session, pedido, tipo="ATRASO_ENTREGA")

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_A)
    )

    assert response.status_code == 400
    assert "aguardando decisão do aluno" in response.json()["detail"]


async def test_a_carrier_occurrence_does_not_hold_the_picking_queue(client, db_session):
    """Finding 2: o aluno NÃO pode resolver ocorrência de transportadora — o
    guard de `ocorrencias.py` a recusa por construção. Bloquear a separação
    nela deixava o pedido travado até um admin chamar `/close`, com uma
    mensagem mandando esperar por uma decisão que não pode acontecer."""
    carrier = await _seed_carrier(db_session)
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)
    await _abrir_ocorrencia(db_session, pedido, tipo="DANO", transportadora_id=carrier.id)

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_A)
    )

    assert response.status_code == 200
    assert response.json()["status"] == StatusPedido.AGUARDANDO_COLETA.value


async def test_a_student_facing_occurrence_still_blocks_the_picker(client, db_session):
    """A outra metade do finding 2: escopar o guard não pode afrouxá-lo para
    a ocorrência que o aluno REALMENTE decide."""
    pedido = await _seed_pedido_em_separacao(db_session, separador_id=PICKER_A)
    await _abrir_ocorrencia(db_session, pedido)

    response = await client.patch(
        f"/picking/{pedido.id}/finish", headers=headers_for("separador", sub=PICKER_A)
    )

    assert response.status_code == 400
    assert "aguardando decisão do aluno" in response.json()["detail"]


# ── A fila devolve ao separador o pedido que ele já começou ────────────────
#
# O desvio de substituição tira o pedido de EM_SEPARACAO e o devolve para lá
# quando o aluno decide. Enquanto a fila listava só AGUARDANDO_SEPARACAO, um
# separador que saía da tela de separação (trocar de perfil num aparelho só
# limpa a pilha de navegação) nunca mais alcançava o pedido, e `finish`
# ficava inalcançável na prática.


async def _seed_pedido(
    db_session, status: str, *, picker_id: str | None = None, horas_atras: float = 0
) -> Order:
    pedido = Order(
        user_id=str(uuid.uuid4()),
        status=status,
        total=Decimal("100.00"),
        picker_id=picker_id,
        created_at=datetime.now(UTC) - timedelta(hours=horas_atras),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _ids_da_fila(client, sub: str, query: str = "") -> list[str]:
    response = await client.get(f"/picking/queue{query}", headers=headers_for("separador", sub))
    assert response.status_code == 200, response.text
    return [pedido["id"] for pedido in response.json()]


async def test_picking_queue_lists_my_in_progress_order_before_the_waiting_ones(client, db_session):
    """O pedido aguardando é mais antigo — pontua MAIS pela espera do que o
    pedido em andamento, criado agora. Mesmo assim o em andamento vem
    primeiro: é trabalho que o separador já assumiu."""
    aguardando = await _seed_pedido(
        db_session, StatusPedido.AGUARDANDO_SEPARACAO.value, horas_atras=40
    )
    em_andamento = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A
    )

    response = await client.get("/picking/queue", headers=headers_for("separador", PICKER_A))

    assert response.status_code == 200
    corpo = response.json()
    assert [p["id"] for p in corpo] == [str(em_andamento.id), str(aguardando.id)]
    assert corpo[0]["status"] == StatusPedido.EM_SEPARACAO.value
    assert corpo[0]["picker_id"] == PICKER_A
    assert isinstance(corpo[0]["score_risco"], float)


async def test_picking_queue_hides_an_order_another_picker_is_working_on(client, db_session):
    await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)
    aguardando = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value)

    assert await _ids_da_fila(client, PICKER_B) == [str(aguardando.id)]


async def test_picking_queue_leaves_out_an_order_waiting_on_the_student(client, db_session):
    """AGUARDANDO_SUBSTITUICAO espera a decisão do aluno — nada que o
    separador possa fazer nele ainda."""
    await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SUBSTITUICAO.value, picker_id=PICKER_A)

    assert await _ids_da_fila(client, PICKER_A) == []


async def test_picking_queue_paginates_over_in_progress_and_waiting_together(client, db_session):
    """`limit`/`offset` cortam a lista JÁ concatenada: em andamento primeiro,
    depois a fila por risco (o mais antigo pontua mais)."""
    recente = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value, horas_atras=1)
    antigo = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value, horas_atras=30)
    em_andamento = await _seed_pedido(
        db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A
    )

    assert await _ids_da_fila(client, PICKER_A, "?limit=2&offset=0") == [
        str(em_andamento.id),
        str(antigo.id),
    ]
    assert await _ids_da_fila(client, PICKER_A, "?limit=2&offset=2") == [str(recente.id)]


# ── GET /picking/{id}: o pedido com os itens de AGORA ──────────────────────
#
# Nenhum schema de staff devolvia os itens, e a substituição troca ou remove
# item no meio da separação — o separador que retoma o pedido precisa
# conferir o que o pedido tem hoje, não o que tinha quando a fila carregou.


async def _seed_item(db_session, pedido: Order, nome: str, quantidade: int = 1) -> OrderItem:
    item = OrderItem(
        order_id=pedido.id,
        product_id=uuid.uuid4(),
        product_name=nome,
        unit_price=Decimal("19.90"),
        quantity=quantidade,
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)
    return item


async def test_order_detail_returns_the_current_items_to_the_picker(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)
    item = await _seed_item(db_session, pedido, "Caderno", quantidade=2)

    response = await client.get(f"/picking/{pedido.id}", headers=headers_for("separador", PICKER_A))

    assert response.status_code == 200, response.text
    corpo = response.json()
    assert corpo["id"] == str(pedido.id)
    assert corpo["status"] == StatusPedido.EM_SEPARACAO.value
    assert [(i["product_id"], i["product_name"], i["quantity"]) for i in corpo["items"]] == [
        (str(item.product_id), "Caderno", 2)
    ]


async def test_order_detail_is_open_to_any_picker_while_the_order_waits_in_the_queue(
    client, db_session
):
    """A fila mostra AGUARDANDO_SEPARACAO a todo separador; o detalhe segue a
    mesma regra, para a tela mostrar os itens antes do `start`."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value)

    response = await client.get(f"/picking/{pedido.id}", headers=headers_for("separador", PICKER_B))

    assert response.status_code == 200


async def test_order_detail_refuses_an_order_another_picker_is_working_on(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.EM_SEPARACAO.value, picker_id=PICKER_A)

    alheio = await client.get(f"/picking/{pedido.id}", headers=headers_for("separador", PICKER_B))
    admin = await client.get(f"/picking/{pedido.id}", headers=headers_for("admin", ADMIN))

    assert alheio.status_code == 403
    assert admin.status_code == 200


async def test_order_detail_forbids_students(client, db_session):
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_SEPARACAO.value)

    response = await client.get(f"/picking/{pedido.id}", headers=headers_for("student"))

    assert response.status_code == 403


async def test_order_detail_of_an_unknown_order_is_404(client):
    response = await client.get(f"/picking/{uuid.uuid4()}", headers=headers_for("separador"))

    assert response.status_code == 404
