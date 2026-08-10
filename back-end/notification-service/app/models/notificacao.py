from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    titulo = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=False)
    tipo = Column(String(30), nullable=False)  # estudo | order_status | sistema
    # Referências opcionais para navegação direta no app (Commerce Service).
    # UUID desde a fase 2 (task C10): `orders.id` do commerce virou UUID.
    # Antes era Integer, e o backlog da fase 1 registrou que `data.order_id`
    # chegava como UUID string vindo do legacy e como inteiro vindo daqui —
    # mesma chave, tipo diferente. Depois desta mudança os dois concordam.
    pedido_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    ocorrencia_id = Column(Integer, nullable=True)
    # Timestamp de leitura (nullable). Preferido a um bool `lida` porque o
    # Flutter (NotificationModel.readAt) espera um valor de data, não bool.
    # `index=True` casa com o `idx_notificacoes_lido_em` do schema.sql
    # original — a listagem filtra por `lido_em IS NULL` quando
    # `unread_only=True`.
    lido_em = Column(DateTime(timezone=True), nullable=True, index=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
