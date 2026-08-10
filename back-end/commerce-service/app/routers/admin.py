import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.models.pedido import Order
from app.models.produto import Estoque
from app.routers.separacao import transicionar_pedido
from app.schemas.estoque import EstoqueOut
from app.schemas.pedido import PedidoStaffOut
from app.services.status_pedido import StatusPedido

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/orders", response_model=list[PedidoStaffOut])
async def listar_pedidos(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order)
    if status:
        query = query.where(Order.status == status)
    query = query.order_by(Order.id).limit(limit).offset(offset)
    result = await db.execute(query)
    # `de_order`, não o ORM cru: `endereco_entrega` não é mais atributo do
    # model — precisa ser composto (ver PedidoStaffOut.de_order).
    return [PedidoStaffOut.de_order(pedido) for pedido in result.scalars().all()]


@router.patch("/orders/{pedido_id}/confirm-payment", response_model=PedidoStaffOut)
async def confirmar_pagamento(
    pedido_id: uuid.UUID,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO, na mesma chamada.

    `CONFIRMADO` é o estado que o contrato expõe como `confirmed`, e existir
    é o que dá ao aluno o passo "Confirmado" na timeline. Mas ele não é um
    estado de REPOUSO: não há simulador na fase 2 (é fase 3), e a fila de
    separação seleciona `AGUARDANDO_SEPARACAO` — parar em `CONFIRMADO`
    deixaria a fila sempre vazia e todo pedido preso atrás de um segundo
    clique manual.

    Encadear duas transições numa rota é o padrão que `finalizar_separacao`
    (separacao.py) já usa para SEPARADO -> AGUARDANDO_COLETA. As duas geram
    linha de histórico e evento, nessa ordem.

    A primeira transição é CONDICIONAL ao pedido ainda estar em `CRIADO`, e
    isso é o que torna a rota retentável. `transicionar_pedido` comita por
    dentro e só então publica o evento, e `EventPublisher.publish`
    (`edu_common.events`) propaga a exceção: um broker indisponível no meio
    do clique do admin deixa `CRIADO -> CONFIRMADO` gravado e aborta antes
    da segunda transição. `CONFIRMADO` não é estado de repouso — a fila de
    separação seleciona `AGUARDANDO_SEPARACAO` e esta rota é a única que
    oferece `CONFIRMADO -> AGUARDANDO_SEPARACAO` — então, sem o guard, o
    segundo clique tentaria `CONFIRMADO -> CONFIRMADO`, que
    `validar_transicao` recusa, e o pedido só sairia de lá por SQL manual.
    Com o guard, o segundo clique retoma de onde parou e não duplica a
    linha `CONFIRMADO` do histórico.

    O `SELECT` abaixo lê a COLUNA (`select(Order.status)`), não a entidade
    `Order`, e isso é obrigatório — não estilo. Ler a entidade a coloca no
    identity map da sessão; o `SELECT ... FOR UPDATE` de dentro de
    `transicionar_pedido`, na MESMA sessão, traz a linha nova do banco mas o
    ORM devolve a instância já carregada **sem repopular os atributos**
    (comportamento padrão do SQLAlchemy — só `populate_existing()` repopula).
    O `FOR UPDATE` fica desarmado para esta rota: o segundo admin revalida
    contra um status velho, passa, e reescreve por cima do primeiro. Medido
    com duas sessões contra Postgres, interleave determinístico (o pre-read
    de B, depois a rota inteira de A, depois B): com leitura de entidade B
    recebe 200, o histórico vira
    `[CONFIRMADO, AGUARDANDO_SEPARACAO, CONFIRMADO, AGUARDANDO_SEPARACAO]`,
    o evento sai duas vezes e o pedido volta para trás na fila; com a
    leitura escalar B recebe 400 e o histórico fica no par único. Coberto
    por `test_two_concurrent_confirm_payments_leave_one_pair_of_transitions`.

    Escalar, e não `with_for_update()` na entidade: o lock aqui também
    corrige o envenenamento, mas fica SEGURADO por toda a rota — na mesma
    medição, o admin concorrente bloqueia até o timeout de 3 s em vez de
    receber 400. A leitura escalar é uma dica de idempotência que não
    envenena nada e não segura lock nenhum; quem serializa continua sendo o
    `SELECT ... FOR UPDATE` de `transicionar_pedido`.
    """
    result = await db.execute(select(Order.status).where(Order.id == pedido_id))
    status_atual = result.scalar_one_or_none()
    if status_atual == StatusPedido.CRIADO.value:
        await transicionar_pedido(db, pedido_id, StatusPedido.CONFIRMADO.value, user["sub"])
    # Sem `if status_atual is None`: um id inexistente cai no 404 de
    # `transicionar_pedido`, que é a mesma resposta de antes deste guard.
    pedido = await transicionar_pedido(
        db, pedido_id, StatusPedido.AGUARDANDO_SEPARACAO.value, user["sub"]
    )
    return PedidoStaffOut.de_order(pedido)


@router.patch("/orders/{pedido_id}/assign-picker", response_model=PedidoStaffOut)
async def atribuir_separador(
    pedido_id: uuid.UUID,
    separador_id: str,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    pedido.picker_id = separador_id
    await db.commit()
    await db.refresh(pedido)
    return PedidoStaffOut.de_order(pedido)


@router.patch("/orders/{pedido_id}/assign-deliverer", response_model=PedidoStaffOut)
async def atribuir_entregador(
    pedido_id: uuid.UUID,
    entregador_id: str,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == pedido_id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    pedido.deliverer_id = entregador_id
    await db.commit()
    await db.refresh(pedido)
    return PedidoStaffOut.de_order(pedido)


@router.get("/inventory", response_model=list[EstoqueOut])
async def listar_estoque(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    `response_model` adicionado além do escopo original do brief — a rota
    devolvia o objeto ORM `Estoque` cru (sem schema nenhum), violando a
    regra "nenhum endpoint devolve objeto ORM cru". Ver
    app/schemas/estoque.py para o porquê.
    """
    result = await db.execute(select(Estoque).order_by(Estoque.id).limit(limit).offset(offset))
    return result.scalars().all()


@router.patch("/inventory/{estoque_id}/adjust", response_model=EstoqueOut)
async def ajustar_estoque(
    estoque_id: int,
    # `ge=0`: sem piso, um admin gravava estoque negativo e a separação
    # passava a trabalhar contra um número que não existe no mundo físico.
    quantidade: int = Query(ge=0),
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    # `with_for_update()`: o ajuste é um read→write sobre recurso compartilhado
    # (regra 3 do CLAUDE.md) — serializa dois ajustes concorrentes na mesma
    # linha em vez de deixá-los correr em paralelo contra o mesmo SELECT.
    # Não muda QUEM vence: esta rota grava um valor absoluto, não um delta,
    # então o último commit sempre define o valor final, com ou sem lock —
    # medido em task-11-report.md, não é apenas suposição.
    result = await db.execute(select(Estoque).where(Estoque.id == estoque_id).with_for_update())
    estoque = result.scalar_one_or_none()
    if not estoque:
        raise HTTPException(404, "Registro de estoque não encontrado")
    estoque.quantidade = quantidade
    await db.commit()
    await db.refresh(estoque)
    return estoque
