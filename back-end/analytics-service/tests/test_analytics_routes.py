import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from edu_common.contracts import DiagnosticCompleted
from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.events import consumer as consumer_module
from app.models.event_log import EventLog

ALUNO_A = "11111111-1111-1111-1111-111111111111"
ALUNO_B = "22222222-2222-2222-2222-222222222222"


def headers_for(role: str) -> dict[str, str]:
    token = create_access_token("00000000-0000-0000-0000-000000000001", role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def diagnostic_payload(aluno_id: str, tema_id: int, dominio_tema: float, acao: str) -> dict:
    """Construído pela MESMA definição que o produtor usa para publicar
    (`edu_common.contracts.DiagnosticCompleted`, montada em
    `learning-service/app/routers/diagnostico.py`) — não por um literal local.

    Era um literal, com uma docstring prometendo espelhar o produtor sem
    importar nada dele. A promessa era falsa e foi medida: renomear
    `dominio_tema` no produtor deixava esta suíte inteira verde (achado B8).
    Agora a renomeação chega até aqui pelo próprio payload — o
    `payload.get("dominio_tema")` de `app/routers/analytics.py` devolve
    `None`, e a asserção sobre os valores da linha do tempo falha.
    """
    return DiagnosticCompleted(
        aluno_id=aluno_id,
        tema_id=tema_id,
        dominio_tema=dominio_tema,
        acao=acao,
    ).to_payload()


async def seed_event(db_session, tipo: str, payload: dict, minutos_atras: int = 0) -> None:
    db_session.add(
        EventLog(
            tipo=tipo,
            payload=payload,
            criado_em=datetime.now(UTC) - timedelta(minutes=minutos_atras),
        )
    )
    await db_session.commit()


async def test_analytics_requires_authentication(client):
    assert (await client.get("/analytics/anomalies")).status_code == 403


async def test_analytics_forbids_students(client):
    response = await client.get("/analytics/anomalies", headers=headers_for("student"))
    assert response.status_code == 403


async def test_analytics_allows_admin(client):
    response = await client.get("/analytics/anomalies", headers=headers_for("admin"))
    assert response.status_code == 200


async def test_public_paths_are_english(client):
    """O contrato público é em inglês (design doc, "Regra de contrato").
    Literais aqui de propósito: importar as rotas do router faria o teste
    concordar com qualquer renomeação futura em vez de barrá-la."""
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert sorted(p for p in paths if p.startswith("/analytics")) == [
        "/analytics/anomalies",
        "/analytics/deliveries",
        "/analytics/executive-summary",
        "/analytics/students/{aluno_id}",
        "/analytics/summary",
    ]


async def test_every_analytics_route_is_admin_only(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    for path in paths:
        if not path.startswith("/analytics"):
            continue
        response = await client.get(path, headers=headers_for("student"))
        assert response.status_code in (403, 405), f"{path} não é admin-only"


async def test_null_grouping_key_does_not_break_the_executive_summary(client, db_session):
    """`payload["status"].astext` devolve NULL quando a chave não existe no
    payload. Analytics loga payload bruto produzido por outros serviços — um
    evento sem a chave não pode virar 500.

    A rota substitui esse NULL por um sentinela de verdade antes de montar o
    agregado. Sem isso, `{None: n}` sairia no JSON como a string `"None"` —
    o `repr` do Python vazando para um contrato público — e ia parar assim no
    prompt do LLM (`_montar_prompt_usuario`). "None" é literal aqui de
    propósito: é exatamente o que não pode voltar a aparecer."""
    await seed_event(db_session, "order.status_changed", {"pedido_id": 1})
    await seed_event(db_session, "diagnostic.completed", {"aluno_id": ALUNO_A})

    response = await client.get("/analytics/executive-summary", headers=headers_for("admin"))

    assert response.status_code == 200
    metricas = response.json()["metricas"]
    assert sum(metricas["pedidos_por_status"].values()) == 1
    assert sum(metricas["diagnosticos_por_acao"].values()) == 1
    assert metricas["pedidos_por_status"] == {"sem_status": 1}
    assert metricas["diagnosticos_por_acao"] == {"sem_acao": 1}
    assert "None" not in metricas["pedidos_por_status"]
    assert "None" not in metricas["diagnosticos_por_acao"]


async def test_student_timeline_returns_the_published_fields(client, db_session):
    """Corpo da resposta, não só o status. Os quatro campos vêm do payload que
    `learning-service` publica de fato — foi lendo `subtema_id`/`dominio`, que
    nunca existiram, que a rota devolvia null em todo evento real."""
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 12, 0.85, "avancar"), 10
    )
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 34, 0.25, "retroceder"), 5
    )

    response = await client.get(f"/analytics/students/{ALUNO_A}", headers=headers_for("admin"))

    assert response.status_code == 200
    corpo = response.json()
    assert len(corpo) == 2
    # Ordenado por `criado_em` ascendente: o de 10 minutos atrás vem primeiro.
    assert [linha["tema_id"] for linha in corpo] == [12, 34]
    assert [linha["dominio_tema"] for linha in corpo] == [0.85, 0.25]
    assert [linha["acao"] for linha in corpo] == ["avancar", "retroceder"]
    assert all(linha["data"] is not None for linha in corpo)


async def test_student_timeline_never_returns_another_student(client, db_session):
    """O `payload["aluno_id"].astext == aluno_id` da query é a única garantia
    de que a linha do tempo de um aluno não devolve a de outro.

    O `order.created` semeado aqui é do MESMO aluno e carrega `aluno_id`
    (`commerce-service/app/routers/pedidos.py`), então só o filtro por
    `tipo == "diagnostic.completed"` o mantém fora da linha do tempo — não é
    vazamento entre alunos, mas é linha errada num contrato de eventos de
    diagnóstico."""
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 12, 0.85, "avancar"), 10
    )
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_B, 99, 0.15, "retroceder"), 5
    )
    await seed_event(
        db_session, "order.created", {"pedido_id": 7, "aluno_id": ALUNO_A, "valor_total": 99.9}, 1
    )

    response = await client.get(f"/analytics/students/{ALUNO_A}", headers=headers_for("admin"))

    assert response.status_code == 200
    corpo = response.json()
    assert len(corpo) == 1
    assert [linha["tema_id"] for linha in corpo] == [12]


async def test_student_timeline_applies_limit_and_offset(client, db_session):
    """Os testes de teto provam que `limit=201` devolve 422; nenhum provava que
    o `limit` chega à query. Sem isto, apagar `.limit()`/`.offset()` do
    `select()` deixaria um admin puxar a tabela de eventos inteira com a suíte
    inteira verde — a paginação obrigatória do plano viraria decoração."""
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 1, 0.10, "estudar"), 30
    )
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 2, 0.50, "retroceder"), 20
    )
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 3, 0.90, "avancar"), 10
    )

    primeira = await client.get(
        f"/analytics/students/{ALUNO_A}?limit=2", headers=headers_for("admin")
    )

    assert primeira.status_code == 200
    # Ordenado por `criado_em` ascendente: os dois mais antigos, e só eles.
    assert [linha["tema_id"] for linha in primeira.json()] == [1, 2]

    segunda = await client.get(
        f"/analytics/students/{ALUNO_A}?limit=2&offset=2", headers=headers_for("admin")
    )

    assert segunda.status_code == 200
    assert [linha["tema_id"] for linha in segunda.json()] == [3]


async def test_deliveries_counts_orders_by_status(client, db_session):
    await seed_event(db_session, "order.status_changed", {"pedido_id": 1, "status": "EM_TRANSITO"})
    await seed_event(db_session, "order.status_changed", {"pedido_id": 2, "status": "EM_TRANSITO"})
    await seed_event(db_session, "order.status_changed", {"pedido_id": 3, "status": "ENTREGUE"})
    # Tipo diferente: não pode entrar na contagem de entregas.
    await seed_event(db_session, "order.created", {"pedido_id": 4})

    response = await client.get("/analytics/deliveries", headers=headers_for("admin"))

    assert response.status_code == 200
    assert {linha["status"]: linha["total"] for linha in response.json()} == {
        "EM_TRANSITO": 2,
        "ENTREGUE": 1,
    }


async def test_deliveries_reports_a_missing_status_as_the_sentinel(client, db_session):
    """Um `order.status_changed` sem a chave `status` no payload."""
    await seed_event(db_session, "order.status_changed", {"pedido_id": 1, "aluno_id": "x"})

    response = await client.get("/analytics/deliveries", headers=headers_for("admin"))

    assert response.status_code == 200
    linhas = response.json()
    assert len(linhas) == 1
    assert linhas[0]["status"] == "sem_status"


async def test_deliveries_and_executive_summary_agree_on_the_sentinel(client, db_session):
    await seed_event(db_session, "order.status_changed", {"pedido_id": 1, "aluno_id": "x"})

    deliveries = await client.get("/analytics/deliveries", headers=headers_for("admin"))
    resumo = await client.get("/analytics/executive-summary", headers=headers_for("admin"))

    chave_deliveries = deliveries.json()[0]["status"]
    chaves_resumo = list(resumo.json()["metricas"]["pedidos_por_status"].keys())
    assert chave_deliveries in chaves_resumo


async def test_summary_counts_events_by_type(client, db_session):
    await seed_event(db_session, "order.created", {"pedido_id": 1})
    await seed_event(db_session, "order.created", {"pedido_id": 2})
    await seed_event(
        db_session, "diagnostic.completed", diagnostic_payload(ALUNO_A, 12, 0.85, "avancar")
    )

    response = await client.get("/analytics/summary", headers=headers_for("admin"))

    assert response.status_code == 200
    assert {linha["tipo"]: linha["total"] for linha in response.json()} == {
        "order.created": 2,
        "diagnostic.completed": 1,
    }


async def test_student_timeline_accepts_the_cap_and_rejects_above_it(client):
    """Teto de paginação como literal: `MAX_PAGE_SIZE + 1` continuaria
    verdadeiro se alguém apagasse o `le=`."""
    no_teto = await client.get(
        f"/analytics/students/{ALUNO_A}?limit=200", headers=headers_for("admin")
    )
    assert no_teto.status_code == 200

    acima = await client.get(
        f"/analytics/students/{ALUNO_A}?limit=201", headers=headers_for("admin")
    )
    assert acima.status_code == 422


async def test_executive_summary_accepts_the_cap_and_rejects_above_it(client):
    no_teto = await client.get(
        "/analytics/executive-summary?dias=365", headers=headers_for("admin")
    )
    assert no_teto.status_code == 200

    acima = await client.get("/analytics/executive-summary?dias=366", headers=headers_for("admin"))
    assert acima.status_code == 422


async def test_anomalies_accepts_the_cap_and_rejects_above_it(client):
    no_teto = await client.get(
        "/analytics/anomalies?dias_historico=365", headers=headers_for("admin")
    )
    assert no_teto.status_code == 200

    acima = await client.get(
        "/analytics/anomalies?dias_historico=366", headers=headers_for("admin")
    )
    assert acima.status_code == 422


def test_every_choreography_routing_key_is_bound():
    """Congela `ROUTING_KEYS` contra a lista literal das nove chaves, cada uma
    verificada contra um `publish_event(...)` real dos outros serviços. O
    trabalho inteiro deste serviço é logar todo evento de coreografia: uma
    chave apagada em silêncio vira dashboard sem dado, e nada mais na suíte
    perceberia — os testes de rota semeiam `EventLog` direto."""
    assert consumer_module.ROUTING_KEYS == [
        "student.created",
        "staff.created",
        "diagnostic.completed",
        "revision.scheduled",
        "order.created",
        "order.status_changed",
        "order.stock_issue",
        "order.delivery_delayed",
        "order.occurrence_resolved",
    ]


def fake_message(routing_key: str, payload: dict) -> MagicMock:
    message = MagicMock()
    message.body = json.dumps(payload).encode()
    message.routing_key = routing_key

    @asynccontextmanager
    async def process():
        yield

    message.process = process
    return message


async def test_consumer_logs_the_raw_event(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_event(fake_message("order.created", {"pedido_id": 7}))

    stored = (await db_session.execute(select(EventLog))).scalars().all()
    assert len(stored) == 1
    assert stored[0].tipo == "order.created"
    assert stored[0].payload == {"pedido_id": 7}
