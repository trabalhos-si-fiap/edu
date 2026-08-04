import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Address(Base):
    __tablename__ = "addresses"

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
    label = Column(String(60), nullable=False, default="", server_default="")
    zip_code = Column(String(9), nullable=False)
    street = Column(String(160), nullable=False)
    number = Column(String(20), nullable=False)
    complement = Column(String(120), nullable=False, default="", server_default="")
    neighborhood = Column(String(120), nullable=False)
    city = Column(String(120), nullable=False)
    state = Column(String(2), nullable=False)
    is_favorite = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
