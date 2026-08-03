"""Schema público de estoque, usado pelo painel admin.

Adicionado além do escopo original do brief da task 11: `GET /admin/estoque`
e `PATCH /admin/estoque/{id}/ajustar` devolviam o objeto ORM `Estoque` puro,
sem `response_model` — violação direta da regra "schemas com campos
explícitos, nenhum endpoint devolve objeto ORM cru". Como os dois já
precisavam ser tocados para traduzir o prefixo (`/estoque` -> `/inventory`),
fechamos a lacuna aqui em vez de deixá-la para uma próxima rodada de fix.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EstoqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    produto_id: int
    fornecedor_id: int
    quantidade: int
    atualizado_em: datetime | None = None
