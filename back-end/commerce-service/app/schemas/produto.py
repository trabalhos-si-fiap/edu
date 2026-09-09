"""Schema público de produto.

Campos declarados um a um de propósito: o model `Product` pode ganhar colunas
internas (custo, margem, fornecedor preferencial) que não podem vazar para o
app só porque foram adicionadas ao banco.
"""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sku: str = ""
    active: bool = True
    type: str
    subtype: str = ""
    description: str = ""
    price: Decimal
    image_url: str = ""
    rating_avg: float = 0.0
    rating_count: int = 0

    @field_serializer("price")
    def _price_as_string(self, value: Decimal) -> str:
        # O contrato original serializa dinheiro como string ("49.90") para o
        # cliente nunca herdar erro de arredondamento de float. Isso é
        # contrato, não formatação — o app o lê como String.
        return f"{value:.2f}"


class ProductList(BaseModel):
    """Envelope, não array puro. O app faz `jsonDecode(body)['items']` — um
    array puro levanta `TypeError` que o tratamento de erro dele não captura.
    Isso é contrato."""

    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class CategoryOut(BaseModel):
    type: str
    count: int


class CategoryList(BaseModel):
    items: list[CategoryOut]


class ProductIn(BaseModel):
    """Criação de produto pelo painel. Cria o produto E a linha de estoque.

    `fornecedor_id` é obrigatório porque a spec exige um único caminho de
    código para "de onde este pedido sai": todo produto tem estoque, todo
    estoque tem fornecedor, todo fornecedor tem origem. Um produto criado sem
    fornecedor reintroduziria o caso especial que a spec eliminou.

    `sku` tem `min_length=1` mesmo o índice do banco sendo parcial
    (`WHERE sku <> ''`, para não quebrar nos seis produtos já semeados): o
    banco tolera o vazio herdado, o validador impede um vazio novo.
    """

    name: str = Field(max_length=160)
    type: str = Field(max_length=64)
    subtype: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=4000)
    price: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    sku: str = Field(min_length=1, max_length=60)
    active: bool = True
    fornecedor_id: int
    # `le=1_000_000`: mesma razão do teto em `AjusteEstoqueIn.delta`
    # (app/schemas/estoque.py) — `Estoque.quantidade`/`estoque_minimo` são
    # `Integer` (int32); sem teto, um valor fora da faixa passaria da
    # validação do Pydantic direto para o INSERT e estouraria
    # `asyncpg.exceptions.DataError` não tratado (500) em vez de 422.
    quantidade_inicial: int = Field(default=0, ge=0, le=1_000_000)
    estoque_minimo: int = Field(default=0, ge=0, le=1_000_000)


class ProductPatch(BaseModel):
    """Edição de catálogo. NÃO carrega estoque: quantidade só muda por ajuste
    auditado (`POST /products/{id}/stock-adjustments`). Um PUT que mexesse no
    saldo contornaria a trilha que a task 3 existe para garantir."""

    name: str = Field(max_length=160)
    type: str = Field(max_length=64)
    subtype: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=4000)
    price: Decimal = Field(gt=0, le=Decimal("99999999.99"))
    sku: str = Field(min_length=1, max_length=60)
    active: bool = True
