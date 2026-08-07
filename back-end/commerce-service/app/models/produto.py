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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.ids import new_uuid


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

    # `default=` cobre insert pelo ORM; `server_default` cobre insert que
    # passa por fora dele (psql, seed em SQL, SQLAdmin) — mesmo padrão da
    # regra 3/constraint já usada em `ativo`/`status` acima. `new_uuid` é
    # UUIDv7 (ordenado no tempo, ver app/ids.py), `gen_random_uuid()` é v4:
    # o server_default é rede de segurança, não o caminho normal.
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(160), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True)
    subtype = Column(String(64), nullable=False, default="", server_default=text("''"))
    description = Column(Text, nullable=False, default="", server_default=text("''"))
    price = Column(Numeric(10, 2), nullable=False)
    # Chave de objeto (`products/<uuid>.jpg`), NÃO uma URL. A serialização a
    # transforma em GET presignado de vida curta — ver app/services/media.py.
    image_url = Column(String(512), nullable=False, default="", server_default=text("''"))
    # Agregados desnormalizados, mantidos em sincronia na criação da review
    # sob lock de linha (ver app/services/produtos.py::criar_review), para a
    # listagem não precisar de um join por linha.
    rating_avg = Column(Numeric(3, 2), nullable=False, default=0, server_default=text("0"))
    rating_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reviews = relationship(
        "Review", back_populates="product", cascade="all, delete-orphan", passive_deletes=True
    )


class Estoque(Base):
    __tablename__ = "estoque"
    __table_args__ = (
        UniqueConstraint("produto_id", "fornecedor_id", name="uq_produto_fornecedor"),
    )

    id = Column(Integer, primary_key=True)
    produto_id = Column(UUID(as_uuid=True), ForeignKey("products.id"))
    fornecedor_id = Column(Integer, ForeignKey("fornecedores.id"))
    quantidade = Column(Integer, nullable=False, default=0, server_default=text("0"))
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
