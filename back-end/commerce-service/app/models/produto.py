from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)

from app.database import Base


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id = Column(Integer, primary_key=True)
    nome = Column(String(150), nullable=False)
    contato = Column(String(150), nullable=True)
    # `default=True` covers ORM inserts; `server_default` matches schema.sql's
    # `DEFAULT TRUE` for any insert that bypasses the ORM (raw SQL, seed
    # scripts, SQLAdmin, a future service) — fix round 1, reviewer finding.
    ativo = Column(Boolean, default=True, server_default=text("true"))


class Product(Base):
    """Catálogo. Em inglês — tabela e colunas — porque este é o primeiro
    agregado do commerce a ganhar cliente (o app Flutter, na fase 4), e a
    regra do design é: o agregado que ganha cliente vira inglês; o que não
    ganha, fica.

    `fornecedores`, `estoque` e `ocorrencias` continuam em português pelo
    mesmo critério — nenhum tem cliente.

    `type` absorveu `categoria`: eram o mesmo conceito com dois nomes. Os
    valores do seed do legacy são `apostila`, `curso`, `digital`.
    """

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    type = Column(String(50), nullable=True)
    image_url = Column(String(255), nullable=True)


class Estoque(Base):
    __tablename__ = "estoque"
    __table_args__ = (
        UniqueConstraint("produto_id", "fornecedor_id", name="uq_produto_fornecedor"),
    )

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, ForeignKey("products.id"))
    fornecedor_id = Column(Integer, ForeignKey("fornecedores.id"))
    quantidade = Column(Integer, nullable=False, default=0, server_default=text("0"))
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
