"""Ajuste de estoque com trilha de auditoria. Porte de `InventoryAdjustment`.

UM núcleo de escrita, DUAS portas. `aplicar_ajuste` recebe delta;
`definir_quantidade` recebe o valor absoluto, converte para delta DENTRO do
mesmo lock e delega. As duas portas existem porque o painel Angular manda
valor absoluto (`PATCH /inventory/{productId}` com `{quantity, reason}`,
igual ao `InventoryService.adjust` do Java) e a spec pede uma rota de delta.
Duplicar o caminho de escrita para atender as duas seria duplicar o lock e a
regra de saldo negativo.

`with_for_update()` aqui não é ornamento, ao contrário do que era na rota
absoluta original (`admin.py`, cujo comentário registra que, gravando valor
ABSOLUTO, o último commit vence com ou sem lock). Com delta, o read→write é
real: sem o lock, dois +5 concorrentes sobre 10 produzem 15, e um lote some.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EstoqueNegativoError, EstoqueNotFoundError
from app.models.estoque_ajuste import EstoqueAjuste
from app.models.produto import Estoque


async def obter_estoque_do_produto(db: AsyncSession, produto_id: uuid.UUID) -> int:
    """Id da linha de estoque do produto — não a entidade.

    Fix round 1, finding 5: esta função só existe para os chamadores
    descobrirem QUAL `estoque_id` passar para `aplicar_ajuste`/
    `definir_quantidade`/`listar_ajustes`. Carregar a entidade `Estoque`
    inteira aqui punha um objeto SEM lock no identity map da sessão — e é
    exatamente essa entidade "pré-lock" que, se a mesma sessão depois faz um
    `SELECT ... FOR UPDATE` no mesmo id, arma a armadilha que
    `execution_options(populate_existing=True)` (em `aplicar_ajuste` e
    `definir_quantidade`) existe para desarmar. `populate_existing` continua
    ali como defesa de última linha — mas `select(Estoque.id)` em vez de
    `select(Estoque)` fecha o problema NESTA ponta: nenhuma entidade entra na
    sessão por este caminho, então não há o que ficar velho.

    Correção à task 3 (rodada original): `Estoque` tem `uq_produto_fornecedor`
    na PAR (produto_id, fornecedor_id) — um produto com mais de um fornecedor
    gera mais de uma linha aqui. `scalar_one_or_none()` estouraria
    `MultipleResultsFound` nesse caso; `order_by(id).limit(1)` resolve de
    forma determinística para a linha mais antiga (a de id menor). Ver
    test_a_product_stocked_by_two_suppliers_still_resolves_to_one_row.
    """
    result = await db.execute(
        select(Estoque.id).where(Estoque.produto_id == produto_id).order_by(Estoque.id).limit(1)
    )
    estoque_id = result.scalars().first()
    if estoque_id is None:
        raise EstoqueNotFoundError()
    return estoque_id


async def aplicar_ajuste(
    db: AsyncSession, *, estoque_id: int, delta: int, motivo: str, autor_id: uuid.UUID
) -> tuple[Estoque, EstoqueAjuste]:
    # `populate_existing=True`: defesa de última linha contra o identity map.
    # `obter_estoque_do_produto` (usada pelo router antes de chegar aqui) só
    # busca a COLUNA `Estoque.id` desde o fix round 1 — nenhuma entidade
    # `Estoque` entra na sessão por aquele caminho, então hoje não há cache
    # pré-lock para este SELECT herdar. Mas QUALQUER outro chamador futuro
    # (tasks 6, 11, 13) que carregue a entidade sem lock antes de chamar
    # `aplicar_ajuste` na mesma sessão reabriria o mesmo buraco: o SQL
    # `FOR UPDATE` abaixo bloqueia corretamente e o Postgres devolve a linha
    # ATUALIZADA quando destrava, mas o ORM, achando o id já carregado,
    # devolveria a instância antiga em memória SEM reescrever `quantidade` —
    # exatamente o gotcha que o comentário de `admin.py::confirmar_pagamento`
    # documenta para `Order`. Medido originalmente (task 3, antes deste fix):
    # sem `populate_existing`, `test_concurrent_deltas_do_not_lose_an_adjustment`
    # perdia um ajuste (10 +5 +5 virava 15, não 20) porque uma das duas
    # requisições lia `anterior=10` do cache, não do SELECT que acabou de
    # esperar o lock. Mantido aqui como o núcleo de escrita — é o lugar certo
    # para a defesa valer para QUALQUER chamador, não só o de hoje.
    estoque = (
        await db.execute(
            select(Estoque)
            .where(Estoque.id == estoque_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if estoque is None:
        raise EstoqueNotFoundError()

    anterior = estoque.quantidade
    nova = anterior + delta
    if nova < 0:
        # Antes de qualquer escrita. A sessão é descartada pelo router sem
        # commit, então nem o estoque nem a trilha mudam.
        raise EstoqueNegativoError()

    estoque.quantidade = nova
    ajuste = EstoqueAjuste(
        estoque_id=estoque.id,
        quantidade_anterior=anterior,
        quantidade_nova=nova,
        motivo=motivo,
        autor_id=autor_id,
    )
    db.add(ajuste)
    # Uma transação só: o UPDATE do estoque e o INSERT da auditoria sobem
    # juntos ou não sobem.
    await db.commit()
    await db.refresh(estoque)
    await db.refresh(ajuste)
    return estoque, ajuste


async def definir_quantidade(
    db: AsyncSession, *, estoque_id: int, quantidade: int, motivo: str, autor_id: uuid.UUID
) -> tuple[Estoque, EstoqueAjuste]:
    """Porta absoluta. O delta é calculado sob o MESMO lock de linha que
    `aplicar_ajuste` toma — por isso a leitura aqui também é
    `with_for_update()`: sem ela, o valor lido para calcular o delta poderia
    ser obsoleto no instante em que o lock fosse adquirido lá dentro.

    O lock é reentrante na mesma transação (Postgres: um segundo
    `SELECT ... FOR UPDATE` na mesma linha, na mesma transação, não bloqueia),
    então as duas tomadas não se travam mutuamente.

    `populate_existing=True` pela mesma razão de `aplicar_ajuste`: esta rota
    (`PATCH /admin/inventory/{id}/adjust`) é chamada direto, sem leitura prévia
    desbloqueada nesta função, mas o mesmo `db` pode chegar aqui com o
    `Estoque` já no identity map por outro caminho — manter a opção aqui
    também custa nada e fecha a mesma classe de bug por completo, não só no
    caso que o teste de concorrência cobre.
    """
    estoque = (
        await db.execute(
            select(Estoque)
            .where(Estoque.id == estoque_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if estoque is None:
        raise EstoqueNotFoundError()
    return await aplicar_ajuste(
        db,
        estoque_id=estoque_id,
        delta=quantidade - estoque.quantidade,
        motivo=motivo,
        autor_id=autor_id,
    )


async def listar_ajustes(
    db: AsyncSession, *, produto_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[EstoqueAjuste], int]:
    estoque_id = await obter_estoque_do_produto(db, produto_id)
    stmt = (
        select(EstoqueAjuste)
        .where(EstoqueAjuste.estoque_id == estoque_id)
        .order_by(EstoqueAjuste.criado_em.desc(), EstoqueAjuste.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count())
            .select_from(EstoqueAjuste)
            .where(EstoqueAjuste.estoque_id == estoque_id)
        )
    ).scalar_one()
    return items, total
