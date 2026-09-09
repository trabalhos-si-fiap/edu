"""Schema público de transportadora. Campos do `Carrier` do Java, um a um.

`rating` e `sla_percentage` saem como STRING pelo mesmo motivo de
`ProductOut.price` e `ParceiroOut.origem_lat`: dinheiro e nota não podem
herdar erro de arredondamento de float ao atravessar JSON. O painel Angular
lê os dois como number hoje (`carrier.model.ts`) e é ajustado na task 13.

Os limites de `rating` (0..5) e `sla_percentage` (0..100) não estão no Java —
lá `BigDecimal(2,1)` e `(5,2)` só limitam a LARGURA, e nada impedia um SLA de
999%. A regra 4 do CLAUDE.md pede limite, e um número fora de faixa aqui
mente para o painel inteiro.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.models.transportadora import CarrierStatus


class TransportadoraIn(BaseModel):
    name: str = Field(max_length=150)
    location: str = Field(max_length=150)
    email: str = Field(max_length=254)
    average_delivery_days: int = Field(ge=0, le=365)
    rating: Decimal = Field(ge=0, le=5)
    sla_percentage: Decimal = Field(ge=0, le=100)
    status: CarrierStatus = CarrierStatus.ACTIVE


class TransportadoraStatusIn(BaseModel):
    status: CarrierStatus


class TransportadoraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    email: str
    average_delivery_days: int
    rating: Decimal
    sla_percentage: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("rating")
    def _rating_as_string(self, value: Decimal) -> str:
        return f"{value:.1f}"

    @field_serializer("sla_percentage")
    def _sla_as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class TransportadoraList(BaseModel):
    items: list[TransportadoraOut]
    total: int
    limit: int
    offset: int
