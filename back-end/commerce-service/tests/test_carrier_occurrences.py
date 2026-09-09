"""Ocorrência de transportadora — reconciliada DENTRO do `Ocorrencia`.

O Java tem `CarrierOccurrence`, ancorada na transportadora; o commerce tem
`Ocorrencia`, ancorada no pedido. Manter os dois criaria duas telas e dois
relatórios que nunca fecham. Aqui a transportadora é uma DIMENSÃO da
ocorrência de pedido, não um segundo dono — `pedido_id` continua NOT NULL.

O que este arquivo mais protege é a fronteira: as ocorrências que já existem
(FALTA_ESTOQUE e ATRASO_ENTREGA abertas por separador/entregador, resolvidas
pelo aluno) não podem mudar de comportamento.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order
from app.models.transportadora import Carrier
from app.services.status_pedido import StatusPedido


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed_pedido(db_session) -> Order:
    pedido = Order(
        user_id=uuid.uuid4(),
        status=StatusPedido.EM_TRANSITO.value,
        total=Decimal("100.00"),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def _seed_carrier(db_session, name: str = "Rápido Cajamar") -> Carrier:
    carrier = Carrier(
        name=name,
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


async def test_creating_a_carrier_occurrence_is_admin_only(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    corpo = {
        "pedido_id": str(pedido.id),
        "transportadora_id": carrier.id,
        "tipo": "DANO",
        "motivo": "Caixa amassada na chegada",
    }
    for papel in ("student", "separador", "entregador"):
        response = await client.post("/occurrences/carrier", json=corpo, headers=headers_for(papel))
        assert response.status_code == 403, papel


async def test_admin_creates_a_carrier_occurrence_anchored_on_the_order(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)

    response = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "FALHA_ENTREGA",
            "motivo": "Endereço não localizado",
        },
        headers=headers_for("admin"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["pedido_id"] == str(pedido.id)
    assert body["transportadora_id"] == carrier.id
    assert body["tipo"] == "FALHA_ENTREGA"
    assert body["status"] == "ABERTA"


async def test_the_four_java_types_are_accepted_and_delivery_delay_is_reused(client, db_session):
    """`DELIVERY_DELAY` do Java É o `ATRASO_ENTREGA` que já existia aqui —
    não virou um sexto valor. Os outros três entram."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    for tipo in ("ATRASO_ENTREGA", "DANO", "FALHA_ENTREGA", "OUTRO"):
        response = await client.post(
            "/occurrences/carrier",
            json={
                "pedido_id": str(pedido.id),
                "transportadora_id": carrier.id,
                "tipo": tipo,
                "motivo": "m",
            },
            headers=headers_for("admin"),
        )
        assert response.status_code == 201, tipo


async def test_a_stock_shortage_is_not_a_carrier_occurrence_type(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    response = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "FALTA_ESTOQUE",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    assert response.status_code == 422


async def test_listing_is_admin_only_paginated_and_filterable(client, db_session):
    pedido = await _seed_pedido(db_session)
    rapida = await _seed_carrier(db_session, "Rápida")
    lenta = await _seed_carrier(db_session, "Lenta")
    for carrier, tipo in ((rapida, "DANO"), (lenta, "FALHA_ENTREGA")):
        await client.post(
            "/occurrences/carrier",
            json={
                "pedido_id": str(pedido.id),
                "transportadora_id": carrier.id,
                "tipo": tipo,
                "motivo": "m",
            },
            headers=headers_for("admin"),
        )

    assert (await client.get("/occurrences", headers=headers_for("student"))).status_code == 403
    assert (
        await client.get("/occurrences?limit=5000", headers=headers_for("admin"))
    ).status_code == 422

    todas = await client.get("/occurrences", headers=headers_for("admin"))
    assert todas.json()["total"] == 2

    por_carrier = await client.get(
        f"/occurrences?carrier_id={rapida.id}", headers=headers_for("admin")
    )
    assert por_carrier.json()["total"] == 1
    assert por_carrier.json()["items"][0]["transportadora_id"] == rapida.id

    por_tipo = await client.get("/occurrences?tipo=DANO", headers=headers_for("admin"))
    assert por_tipo.json()["total"] == 1

    por_status = await client.get("/occurrences?status=RESOLVIDA", headers=headers_for("admin"))
    assert por_status.json()["total"] == 0


async def test_grouping_by_carrier_does_not_hide_the_order_occurrences(client, db_session):
    """A ocorrência de pedido sem transportadora continua na listagem — ela
    não deixou de existir por ter ganhado uma dimensão nova."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    db_session.add(
        Ocorrencia(
            pedido_id=pedido.id,
            tipo="FALTA_ESTOQUE",
            motivo="Sem estoque",
            criado_por=uuid.uuid4(),
        )
    )
    await db_session.commit()
    await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )

    todas = await client.get("/occurrences", headers=headers_for("admin"))
    assert todas.json()["total"] == 2
    sem_carrier = [o for o in todas.json()["items"] if o["transportadora_id"] is None]
    assert len(sem_carrier) == 1


async def test_closing_an_occurrence_is_admin_only_and_idempotent_guarded(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]

    negado = await client.post(
        f"/occurrences/{ocorrencia_id}/close", json={}, headers=headers_for("student")
    )
    assert negado.status_code == 403

    fechada = await client.post(
        f"/occurrences/{ocorrencia_id}/close",
        json={"observacao": "Reembolso emitido"},
        headers=headers_for("admin"),
    )
    assert fechada.status_code == 200
    assert fechada.json()["status"] == "RESOLVIDA"
    assert fechada.json()["resolvido_em"] is not None

    de_novo = await client.post(
        f"/occurrences/{ocorrencia_id}/close", json={}, headers=headers_for("admin")
    )
    assert de_novo.status_code == 400


async def test_close_does_not_touch_the_student_resolve_path(client, db_session):
    """`close` fecha; ele NÃO substitui item, não mexe em `orders.total` e não
    cancela pedido. Essa lógica é do `resolve` do aluno e continua lá."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    total_antes = pedido.total
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    await client.post(
        f"/occurrences/{criada.json()['id']}/close", json={}, headers=headers_for("admin")
    )
    await db_session.refresh(pedido)
    assert pedido.total == total_antes
    assert pedido.status == StatusPedido.EM_TRANSITO.value


async def test_creating_against_an_unknown_order_or_carrier_is_404(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)

    sem_pedido = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(uuid.uuid4()),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    assert sem_pedido.status_code == 404

    sem_carrier = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": 999999,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    assert sem_carrier.status_code == 404


# ── Ruling 3: uma negativa por rota, não uma por grupo ───────────────────
#
# As nove asserções acima já cobrem "student" sozinho contra cada rota nova
# (`test_creating_a_carrier_occurrence_is_admin_only`,
# `test_listing_is_admin_only_paginated_and_filterable`,
# `test_closing_an_occurrence_is_admin_only_and_idempotent_guarded`). O que
# falta, no mesmo formato de dois loops de `tests/test_carriers_routes.py`
# (`test_every_carrier_route_is_admin_only` /
# `test_every_carrier_route_requires_a_credential`), é: separador/entregador
# contra as três rotas, e a ausência total de credencial contra as três
# rotas — cada rota com sua própria asserção dentro do loop, identificada na
# mensagem.


async def test_every_new_occurrence_route_is_admin_only(client, db_session):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]

    chamadas = [
        ("get", "/occurrences", None),
        (
            "post",
            "/occurrences/carrier",
            {
                "pedido_id": str(pedido.id),
                "transportadora_id": carrier.id,
                "tipo": "DANO",
                "motivo": "m",
            },
        ),
        ("post", f"/occurrences/{ocorrencia_id}/close", {}),
    ]
    for metodo, url, corpo in chamadas:
        for papel in ("student", "separador", "entregador"):
            kwargs = {"headers": headers_for(papel)}
            if corpo is not None:
                kwargs["json"] = corpo
            response = await getattr(client, metodo)(url, **kwargs)
            assert response.status_code == 403, f"{metodo} {url} {papel}"


async def test_every_new_occurrence_route_requires_a_credential(client, db_session):
    """Sem `Authorization`, o contrato deste serviço
    (`edu_common.deps.get_current_user`) devolve 403 ("não autenticado"),
    não 401 — 401 é só para credencial presente e inválida."""
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]

    chamadas = [
        ("get", "/occurrences", None),
        (
            "post",
            "/occurrences/carrier",
            {
                "pedido_id": str(pedido.id),
                "transportadora_id": carrier.id,
                "tipo": "DANO",
                "motivo": "m",
            },
        ),
        ("post", f"/occurrences/{ocorrencia_id}/close", {}),
    ]
    for metodo, url, corpo in chamadas:
        kwargs = {}
        if corpo is not None:
            kwargs["json"] = corpo
        response = await getattr(client, metodo)(url, **kwargs)
        assert response.status_code == 403, f"{metodo} {url} sem credencial"


# ── Fix round 1: a fronteira também vale na direção contrária ────────────
#
# O texto de `resolver_ocorrencia` (`POST /occurrences/{id}/resolve`) é
# anterior a esta task e não mudou — mas o comportamento EFETIVO dele mudou
# no instante em que a ocorrência de transportadora passou a viver na mesma
# tabela. Sem guarda, o aluno "resolvia" (inclusive cancelando o pedido) uma
# ocorrência que o admin abriu sobre a transportadora, e o `/close`
# admin-only virava decoração — o reviewer reproduziu isso ao vivo contra o
# banco de teste.

# sub padrão de headers_for("student")
_ALUNO_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _seed_pedido_do_aluno(db_session, **overrides) -> Order:
    defaults = {
        "user_id": _ALUNO_ID,
        "status": StatusPedido.EM_TRANSITO.value,
        "total": Decimal("100.00"),
    }
    defaults.update(overrides)
    pedido = Order(**defaults)
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_student_resolve_refuses_a_carrier_occurrence(client, db_session):
    """Achado #1 do reviewer: admin abre `DANO` no pedido do aluno; o aluno
    chama `/resolve` com `cancelar_pedido` e, sem a guarda, o pedido ia para
    `CANCELADO` e a ocorrência do admin virava `RESOLVIDA` por baixo dele.
    O `cancelar_pedido` não checava `ocorrencia.tipo` nenhum."""
    pedido = await _seed_pedido_do_aluno(db_session)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "Caixa amassada",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]

    resolvido = await client.post(
        f"/occurrences/{ocorrencia_id}/resolve",
        json={"resolucao": "cancelar_pedido"},
        headers=headers_for("student"),
    )
    assert resolvido.status_code == 400

    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_TRANSITO.value

    ocorrencia_db = await db_session.get(Ocorrencia, ocorrencia_id)
    assert ocorrencia_db.status == "ABERTA"


async def test_student_resolve_refuses_accepting_a_new_date_without_one(client, db_session):
    """Achado #2 do reviewer: `POST /occurrences/carrier` nunca preenche
    `nova_data_sugerida` (só `POST /occurrences/delivery-delay`, do
    entregador, preenche). Sem a guarda, `aceitar_nova_data` gravava
    `pedido.estimated_delivery_at = None` silenciosamente — o `tipo ==
    "ATRASO_ENTREGA"` era checado, a presença da data não."""
    entrega_estimada = datetime(2026, 1, 1, tzinfo=UTC)
    pedido = await _seed_pedido_do_aluno(db_session, estimated_delivery_at=entrega_estimada)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "ATRASO_ENTREGA",
            "motivo": "Atraso da transportadora",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]
    assert criada.json()["nova_data_sugerida"] is None

    resolvido = await client.post(
        f"/occurrences/{ocorrencia_id}/resolve",
        json={"resolucao": "aceitar_nova_data"},
        headers=headers_for("student"),
    )
    assert resolvido.status_code == 400

    await db_session.refresh(pedido)
    assert pedido.estimated_delivery_at == entrega_estimada


# ── Fix round 1 (hardening): provar o lock de `close`, não só a idempotência
#
# `test_closing_an_occurrence_is_admin_only_and_idempotent_guarded` fecha a
# mesma ocorrência duas vezes SEQUENCIALMENTE no mesmo client — uma versão
# sem `with_for_update()` passaria nele igualzinho, porque a segunda chamada
# enxerga o `RESOLVIDA` que a primeira já commitou por leitura comum, sem
# precisar de lock nenhum. Este teste mirra
# `test_concurrent_resolves_apply_the_price_delta_once`
# (`tests/test_occurrences_routes.py`): duas requisições de verdade
# concorrentes, com o encontro forçado sem `sleep` fixo no meio do caminho
# (um `asyncio.gather` puro não basta — as queries locais voltam rápido
# demais para o event loop trocar de tarefa, medido lá e medido aqui de
# novo). A PRIMEIRA para no seu commit e só segue quando a SEGUNDA abriu a
# própria sessão (fez seu próprio primeiro `execute`).
#
# Diferença medida contra o `resolve`: o `close` só faz UM `execute` antes
# do commit (o `resolve` faz até quatro — outro SELECT FOR UPDATE, mais
# OrderItem/Product), então o SELECT simples da segunda sessão (sem lock)
# tem uma folga de só alguns milissegundos para voltar antes do commit da
# primeira — nesta máquina, ela vencia essa corrida de forma consistente,
# fazendo uma versão SEM `with_for_update()` passar aqui por acidente (medido: 5/5
# rodadas "verdes" com o lock removido, antes deste ajuste). Por isso o
# `asyncio.sleep(0.05)` abaixo, DEPOIS do sinal e ANTES do commit da
# primeira: ele não muda nada quando o lock existe (a segunda já está
# bloqueada no banco esperando a primeira terminar, não esperando este
# sleep), mas garante que, sem o lock, o SELECT sem lock da segunda teve
# tempo de sobra para voltar com "ABERTA" antes da primeira commitar —
# tornando o resultado sem lock ([200, 200], achado duplicado)
# deterministico em vez de uma corrida de sorte.
async def test_concurrent_closes_apply_the_resolution_once(client, db_session, monkeypatch):
    pedido = await _seed_pedido(db_session)
    carrier = await _seed_carrier(db_session)
    criada = await client.post(
        "/occurrences/carrier",
        json={
            "pedido_id": str(pedido.id),
            "transportadora_id": carrier.id,
            "tipo": "DANO",
            "motivo": "m",
        },
        headers=headers_for("admin"),
    )
    ocorrencia_id = criada.json()["id"]

    execute_real = AsyncSession.execute
    commit_real = AsyncSession.commit
    sessoes_vistas = {id(db_session)}
    a_segunda_abriu = asyncio.Event()
    estado = {"ja_esperou": False}

    async def execute_espiao(self, *args, **kwargs):
        if id(self) not in sessoes_vistas:
            sessoes_vistas.add(id(self))
            if len(sessoes_vistas) == 3:  # db_session + as duas sessões de rota
                a_segunda_abriu.set()
        return await execute_real(self, *args, **kwargs)

    async def commit_espiao(self):
        if id(self) != id(db_session) and not estado["ja_esperou"]:
            estado["ja_esperou"] = True
            await asyncio.wait_for(a_segunda_abriu.wait(), timeout=5)
            await asyncio.sleep(0.05)
        return await commit_real(self)

    monkeypatch.setattr(AsyncSession, "execute", execute_espiao)
    monkeypatch.setattr(AsyncSession, "commit", commit_espiao)

    primeira, segunda = await asyncio.gather(
        client.post(f"/occurrences/{ocorrencia_id}/close", json={}, headers=headers_for("admin")),
        client.post(f"/occurrences/{ocorrencia_id}/close", json={}, headers=headers_for("admin")),
    )

    monkeypatch.undo()

    codigos = sorted([primeira.status_code, segunda.status_code])
    assert codigos == [200, 400], f"{primeira.text} / {segunda.text}"

    ocorrencia_db = await db_session.get(Ocorrencia, ocorrencia_id)
    await db_session.refresh(ocorrencia_db)
    assert ocorrencia_db.status == "RESOLVIDA"
