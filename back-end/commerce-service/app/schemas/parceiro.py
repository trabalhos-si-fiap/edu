"""Schema público de parceiro.

Campos um a um (regra 6): `Fornecedor` pode ganhar coluna interna (margem
negociada, contrato) que não pode vazar para o app só por existir no banco.

As coordenadas saem como STRING, não float — mesmo critério de
`ProductOut.price` (`app/schemas/produto.py`): o cliente nunca herda erro de
arredondamento de float num valor que atravessa JSON. O `Numeric(9, 6)` do
model vira "-23.355800", com as seis casas preservadas.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ParceiroIn(BaseModel):
    nome: str = Field(max_length=150)
    contato: str | None = Field(default=None, max_length=150)
    ativo: bool = True
    origem_rotulo: str = Field(max_length=120)
    origem_lat: Decimal | None = Field(default=None, ge=-90, le=90)
    origem_lng: Decimal | None = Field(default=None, ge=-180, le=180)


class ParceiroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    contato: str | None = None
    ativo: bool
    origem_rotulo: str = ""
    origem_lat: Decimal | None = None
    origem_lng: Decimal | None = None

    @field_serializer("origem_lat", "origem_lng")
    def _coord_as_string(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.6f}"


class ParceiroList(BaseModel):
    """Envelope igual ao de `ProductList` — `{items, total, limit, offset}`.
    A frota inteira usa esse formato; o painel Angular é reescrito para ele
    (decisão D9 do plano), não o contrário."""

    items: list[ParceiroOut]
    total: int
    limit: int
    offset: int
