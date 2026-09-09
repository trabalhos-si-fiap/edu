"""Schema público de estoque, usado pelo painel admin.

Adicionado além do escopo original do brief da task 11: `GET /admin/estoque`
e `PATCH /admin/estoque/{id}/ajustar` devolviam o objeto ORM `Estoque` puro,
sem `response_model` — violação direta da regra "schemas com campos
explícitos, nenhum endpoint devolve objeto ORM cru". Como os dois já
precisavam ser tocados para traduzir o prefixo (`/estoque` -> `/inventory`),
fechamos a lacuna aqui em vez de deixá-la para uma próxima rodada de fix.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class EstoqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: uuid.UUID
    fornecedor_id: int
    quantidade: int
    estoque_minimo: int
    atualizado_em: datetime | None = None


class AjusteEstoqueIn(BaseModel):
    """`delta`, não quantidade absoluta: a rota é `POST .../stock-adjustments`,
    e o que se posta é o ajuste, não o novo saldo. A porta absoluta é
    `PATCH /admin/inventory/{id}/adjust`, que converte para delta dentro do
    lock e chama o mesmo núcleo (ver app/services/estoque.py)."""

    delta: int
    motivo: str = Field(min_length=1, max_length=300)

    @field_validator("delta")
    @classmethod
    def _delta_nao_pode_ser_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("delta não pode ser zero")
        return v


class EstoqueAjusteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estoque_id: int
    quantidade_anterior: int
    quantidade_nova: int
    motivo: str
    autor_id: uuid.UUID
    criado_em: datetime

    @computed_field
    @property
    def delta(self) -> int:
        """Derivado, não guardado. Gravar `delta` além das duas quantidades
        criaria uma terceira fonte da verdade para o mesmo fato, capaz de
        divergir das outras duas."""
        return self.quantidade_nova - self.quantidade_anterior


class EstoqueAjusteList(BaseModel):
    items: list[EstoqueAjusteOut]
    total: int
    limit: int
    offset: int
