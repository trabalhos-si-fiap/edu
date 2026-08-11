from sqlalchemy import CheckConstraint, Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.ids import new_uuid


class SupportMessage(Base):
    """Uma mensagem da conversa de suporte.

    Em inglês — tabela e colunas — porque é um agregado com cliente: o app
    Flutter lê `/support` na fase 4.

    `user_id` é FK LÓGICA para o `auth-users-service`: banco diferente,
    nenhuma FK física possível. A posse é garantida em toda query, sem
    exceção — é a única defesa que existe aqui.

    O CHECK de `sender` vive no banco, e não só no schema Pydantic, porque a
    conversa é renderizada como dois lados; um valor fora do par quebraria a
    tela e não haveria nada para pegá-lo se a escrita viesse por fora do ORM.
    """

    __tablename__ = "support_messages"
    __table_args__ = (
        CheckConstraint("sender IN ('user', 'support')", name="ck_support_messages_sender"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # `default=` cobre insert pelo ORM; `server_default` cobre insert que
    # passa por fora dele — constraint 15.
    sender = Column(String(16), nullable=False, default="user", server_default=text("'user'"))
    # 2000 no model E no schema (regra 4 do CLAUDE.md). O legacy declara os
    # dois; declarar só um deixa o limite a cargo de quem chamar.
    body = Column(String(2000), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
