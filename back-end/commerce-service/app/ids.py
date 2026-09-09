import uuid
from typing import Annotated

import uuid_utils
from pydantic import Field


def new_uuid() -> uuid.UUID:
    """Gera um UUIDv7 (ordenado no tempo) como `uuid.UUID` da stdlib.

    Mesma função de `legacy/app/core/ids.py`. Id ordenado no tempo preserva
    a localidade de inserção no índice B-tree do Postgres; UUIDv4 aleatório
    fragmenta o índice a cada insert.
    """
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)


# Teto de um `integer` do Postgres. Toda chave primária inteira deste serviço
# (`fornecedores.id`, `estoque.id`, `carriers.id`, `ocorrencias.id`) é
# `Integer`, ou seja int32.
INT32_MAX = 2_147_483_647

Int32Id = Annotated[int, Field(ge=1, le=INT32_MAX)]
"""Identificador inteiro que CABE na coluna que ele vai consultar.

Sem o teto, um id fora da faixa (ex.: 3 bilhões) atravessa a validação do
Pydantic, chega no asyncpg e levanta
`asyncpg.exceptions.DataError: value out of int32 range` — 500 sem handler,
onde o contrato deve 422. Sem o piso, um id negativo ou zero vira uma consulta
que nunca casa, gastando uma ida ao banco para produzir um 404 que a validação
já sabia dar.

Este alias existe porque a classe foi corrigida ponto a ponto TRÊS vezes e
deixada aberta em outros nove sites — o mesmo conceito "id de parceiro" estava
limitado como query param (`GET /products?partner_id=`) e ilimitado como campo
de corpo (`ProductIn.fornecedor_id`), no mesmo serviço. Um tipo com nome é o
que impede a décima ocorrência: a próxima rota que receber um id inteiro
anota `Int32Id` e herda a faixa.

Vale para path param, query param e campo de corpo — o FastAPI achata
`Annotated` aninhado, então `Path(...)`/`Query(...)` continuam podendo trazer
`description`, `alias` e afins sem repetir a faixa.

NÃO se aplica a quantidade nem a delta de estoque: aqueles têm teto próprio
(`le=1_000_000`, em `app/schemas/estoque.py` e `app/schemas/produto.py`), que
é uma folga deliberada e não a borda do tipo.
"""
