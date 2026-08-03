from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # `default=` covers ORM inserts; `server_default` matches schema.sql's
    # `DEFAULT 'CRIADO'` for any insert bypassing the ORM — fix round 1,
    # reviewer finding.
    status = Column(
        String(30), nullable=False, default="CRIADO", server_default=text("'CRIADO'"), index=True
    )
    endereco_entrega = Column(Text, nullable=False)
    valor_total = Column(Numeric(10, 2), nullable=False)
    separador_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    entregador_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    transportadora_nome = Column(String(100), nullable=True)  # mock por enquanto
    data_prevista_entrega = Column(DateTime(timezone=True), nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PedidoItem(Base):
    __tablename__ = "pedido_itens"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"))
    produto_id = Column(Integer, ForeignKey("produtos.id"))
    fornecedor_id = Column(Integer, ForeignKey("fornecedores.id"))
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Numeric(10, 2), nullable=False)


class PedidoStatusHistorico(Base):
    __tablename__ = "pedido_status_historico"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"))
    status = Column(String(30), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # quem fez a transição
    observacao = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
