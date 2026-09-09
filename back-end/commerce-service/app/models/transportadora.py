from enum import StrEnum

from sqlalchemy import Column, DateTime, Integer, Numeric, String, func, text

from app.database import Base


class CarrierStatus(StrEnum):
    """Enum de TEXTO, não booleano — o Java já distinguia mais de dois
    estados na modelagem (`CarrierStatus` é enum, não flag), e a spec pede
    que a porta preserve isso. Mesmo idioma de `StatusPedido`
    (`app/services/status_pedido.py`): o valor guardado é a string.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Carrier(Base):
    """Porte de `mobile_hybrid_app/api/.../carrier/entity/Carrier.java`.

    Em INGLÊS — tabela e colunas — porque este agregado nasce com dois
    clientes: o painel Angular (`web-admin/src/app/core/models/carrier.model.ts`,
    que já lê `name`/`location`/`averageDeliveryDays`/`slaPercentage`) e a
    rota `/carriers` do gateway. É o mesmo critério que pôs `products` e
    `orders` em inglês (ver docstring de `app/models/produto.py::Product`).

    Larguras copiadas do Java, não escolhidas aqui: `name` 150,
    `location` 150, `email` 254, `status` 20, `rating` Numeric(2,1),
    `sla_percentage` Numeric(5,2).
    """

    __tablename__ = "carriers"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, index=True)
    location = Column(String(150), nullable=False)
    email = Column(String(254), nullable=False)
    average_delivery_days = Column(Integer, nullable=False, default=0, server_default=text("0"))
    rating = Column(Numeric(2, 1), nullable=False, default=0, server_default=text("0"))
    sla_percentage = Column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    # `default=` cobre insert pelo ORM; `server_default` cobre insert que
    # passa por fora dele — mesmo par usado em `Fornecedor.ativo` e
    # `Order.status`.
    status = Column(
        String(20),
        nullable=False,
        default=CarrierStatus.ACTIVE.value,
        server_default=text("'ACTIVE'"),
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
