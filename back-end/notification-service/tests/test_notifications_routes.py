from datetime import UTC, datetime

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.device_token import DeviceToken
from app.models.notificacao import Notificacao

STUDENT_ID = "00000000-0000-0000-0000-000000000001"
OTHER_ID = "00000000-0000-0000-0000-000000000002"


def headers_for(user_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(user_id, 'student', settings.jwt_secret)}"
    }


async def test_list_requires_authentication(client):
    assert (await client.get("/notifications")).status_code == 403


async def test_list_returns_only_own_notifications(client, db_session):
    db_session.add_all(
        [
            Notificacao(aluno_id=STUDENT_ID, titulo="Minha", descricao="d", tipo="estudo"),
            Notificacao(aluno_id=OTHER_ID, titulo="Do outro", descricao="d", tipo="estudo"),
        ]
    )
    await db_session.commit()

    body = (await client.get("/notifications", headers=headers_for(STUDENT_ID))).json()
    # Contrato público em inglês (Global Constraints do plano) — o schema
    # `NotificationOut` devolve `title`, não `titulo`; a chave em português
    # aqui era um bug do brief (campo interno do model vazando pro teste).
    assert [n["title"] for n in body] == ["Minha"]


async def test_notification_data_uses_english_field_names(client, db_session):
    """Contrato público em inglês (Global Constraints do plano) — o
    sub-objeto `data` devolve `order_id`/`occurrence_id`, não os nomes
    internos do model (`pedido_id`/`ocorrencia_id`)."""
    db_session.add(
        Notificacao(
            aluno_id=STUDENT_ID,
            titulo="Pedido",
            descricao="d",
            tipo="order_status",
            pedido_id=42,
            ocorrencia_id=7,
        )
    )
    await db_session.commit()

    body = (await client.get("/notifications", headers=headers_for(STUDENT_ID))).json()
    assert body[0]["data"] == {"type": "order_status", "order_id": 42, "occurrence_id": 7}


async def test_list_unread_only_filters_read_notifications(client, db_session):
    unread = Notificacao(aluno_id=STUDENT_ID, titulo="Não lida", descricao="d", tipo="estudo")
    read = Notificacao(
        aluno_id=STUDENT_ID,
        titulo="Lida",
        descricao="d",
        tipo="estudo",
        lido_em=datetime.now(UTC),
    )
    db_session.add_all([unread, read])
    await db_session.commit()

    body = (
        await client.get("/notifications?unread_only=true", headers=headers_for(STUDENT_ID))
    ).json()
    assert [n["title"] for n in body] == ["Não lida"]


async def test_list_is_paginated(client, db_session):
    db_session.add_all(
        [
            Notificacao(aluno_id=STUDENT_ID, titulo=f"N{i}", descricao="d", tipo="estudo")
            for i in range(5)
        ]
    )
    await db_session.commit()
    body = (await client.get("/notifications?limit=2", headers=headers_for(STUDENT_ID))).json()
    assert len(body) == 2


async def test_cannot_mark_another_users_notification_as_read(client, db_session):
    notification = Notificacao(aluno_id=OTHER_ID, titulo="Do outro", descricao="d", tipo="estudo")
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)

    response = await client.patch(
        f"/notifications/{notification.id}/read", headers=headers_for(STUDENT_ID)
    )
    assert response.status_code == 404


async def test_register_device_stores_the_token(client, db_session):
    response = await client.post(
        "/notifications/devices",
        json={"token": "fcm-token-1", "platform": "android"},
        headers=headers_for(STUDENT_ID),
    )
    assert response.status_code == 201

    stored = (await db_session.execute(select(DeviceToken))).scalars().all()
    assert [t.token for t in stored] == ["fcm-token-1"]


async def test_register_device_is_idempotent(client, db_session):
    payload = {"token": "fcm-token-1", "platform": "android"}
    await client.post("/notifications/devices", json=payload, headers=headers_for(STUDENT_ID))
    await client.post("/notifications/devices", json=payload, headers=headers_for(STUDENT_ID))

    stored = (await db_session.execute(select(DeviceToken))).scalars().all()
    assert len(stored) == 1


async def test_unregister_device_only_removes_own_token(client, db_session):
    db_session.add(DeviceToken(aluno_id=OTHER_ID, token="alheio", platform="android"))
    await db_session.commit()

    await client.delete("/notifications/devices/alheio", headers=headers_for(STUDENT_ID))

    stored = (await db_session.execute(select(DeviceToken))).scalars().all()
    assert len(stored) == 1, "o token de outro usuário não pode ser apagado"


async def test_devices_require_authentication(client):
    response = await client.post(
        "/notifications/devices", json={"token": "x", "platform": "android"}
    )
    assert response.status_code == 403
