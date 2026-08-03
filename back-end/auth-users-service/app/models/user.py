import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student", index=True)
    telefone = Column(String(20), nullable=True)
    documento = Column(String(20), nullable=True)
    # Campos exigidos pelo formulário de cadastro do Flutter (RegisterScreen).
    data_nascimento = Column(Date, nullable=True)
    escolaridade = Column(String(20), nullable=True)  # ver EducationLevel no schema
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
