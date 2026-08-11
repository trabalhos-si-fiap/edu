import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.suporte import SupportMessage


async def test_a_message_is_stored_with_its_owner(db_session):
    user_id = uuid.uuid4()
    mensagem = SupportMessage(user_id=user_id, sender="user", body="Não consigo pagar")
    db_session.add(mensagem)
    await db_session.commit()
    await db_session.refresh(mensagem)

    assert isinstance(mensagem.id, uuid.UUID)
    assert mensagem.user_id == user_id
    assert mensagem.created_at is not None


async def test_sender_defaults_to_user(db_session):
    mensagem = SupportMessage(user_id=uuid.uuid4(), body="olá")
    db_session.add(mensagem)
    await db_session.commit()
    await db_session.refresh(mensagem)
    assert mensagem.sender == "user"


async def test_an_unknown_sender_is_rejected_by_the_database(db_session):
    """O CHECK vive no banco, não só no schema Pydantic: a conversa é lida
    por duas partes e um `sender` fora do par quebraria a renderização."""
    mensagem = SupportMessage(user_id=uuid.uuid4(), sender="robo", body="olá")
    db_session.add(mensagem)
    with pytest.raises(IntegrityError):
        await db_session.commit()
