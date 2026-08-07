from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.ids import new_uuid


class Review(Base):
    """Avaliação de produto.

    Em inglês porque `products` é o agregado que ganhou cliente.

    `user_id` é FK lógica para o auth-users-service (banco diferente, sem FK
    física possível). `author` é o nome desnormalizado, resolvido via
    `GET /auth/me` no momento da criação — o JWT não carrega o nome.
    """

    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),)

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=text("gen_random_uuid()"),
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    author = Column(String(120), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(String(2000), nullable=False, default="", server_default=text("''"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product", back_populates="reviews")
