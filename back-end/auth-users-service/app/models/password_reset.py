import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class PasswordResetCode(Base):
    """
    Código de verificação para redefinição de senha (fluxo
    forgot_password_screen -> reset_password_screen do Flutter).

    MVP: nenhum provedor de e-mail/SMS foi configurado ainda — o código não
    é persistido nem logado em texto plano, só o hash. Antes de ir para
    produção, plugar um serviço de e-mail real para o envio.
    """

    __tablename__ = "password_reset_codes"

    # Ver a nota em `user.py`: `server_default` restaura os DEFAULT de banco
    # que o schema.sql declarava e a baseline do Alembic perdeu.
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash = Column(String(255), nullable=False)
    usado = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    expira_em = Column(DateTime(timezone=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
