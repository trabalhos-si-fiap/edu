from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class DeviceToken(Base):
    """
    Registro de token FCM por usuário (`NotificationsApi.registerDevice` /
    `unregisterDevice` no Flutter, chamado via `MessagingService`).

    MVP: só armazena o token — nenhum envio de push real acontece a partir
    daqui ainda (isso exigiria integração com o Firebase Admin SDK no
    Notification Service, fora do escopo atual).
    """

    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("aluno_id", "token", name="uq_aluno_token"),)

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    token = Column(String(255), nullable=False, index=True)
    # `default=` cobre inserts pelo ORM; `server_default` casa com o
    # `DEFAULT 'android'` do schema.sql para qualquer insert que não passe
    # pelo ORM (seed em SQL puro, outro serviço, painel admin).
    platform = Column(
        String(20), nullable=False, default="android", server_default=text("'android'")
    )
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
