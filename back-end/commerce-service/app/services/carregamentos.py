"""Carregamento: o lote de pedidos que sai junto, de uma origem, por uma
transportadora — e a credencial com que o entregador o acessa.

A senha existe em claro em exatamente DOIS lugares e por um instante só: o
retorno de `criar_carregamento` e o payload de `shipment.created`. Nada aqui a
loga, e nenhuma leitura posterior a devolve.
"""

import secrets
import uuid

from edu_common.security import hash_password
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    CarregamentoNotFoundError,
    CarregamentoOrigemDivergenteError,
    OrderNotFoundError,
    PedidoJaCarregadoError,
    TransportadoraNotFoundError,
)
from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.models.transportadora import Carrier

# Sem I, O, 0 e 1: o código é ditado por telefone e digitado por quem está com
# a carga na mão. Ambiguidade visual aqui vira uma tentativa de login perdida.
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO = 8
TAMANHO_SENHA = 12

# Quantas vezes tentar um código novo diante de colisão. Com 32^8 (~1.1e12)
# combinações e dezenas de lotes, três tentativas é folga absurda; o laço
# existe para o caso patológico, não para o caso normal.
TENTATIVAS_CODIGO = 3


def gerar_codigo() -> str:
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_CODIGO))


def gerar_senha() -> str:
    """`secrets`, nunca `random`: `random` é um Mersenne Twister previsível a
    partir de saídas anteriores, e isto é credencial."""
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_SENHA))


async def criar_carregamento(
    db: AsyncSession, *, transportadora_id: int, criado_por: uuid.UUID
) -> tuple[Carregamento, str]:
    """Cria o lote e devolve `(carregamento, senha_em_claro)`.

    A colisão de `codigo` é detectada pelo ÍNDICE ÚNICO, não por um SELECT
    prévio: SELECT-depois-INSERT é uma corrida, e o índice é a única coisa que
    resolve duas criações simultâneas. Mesmo idioma de
    `services/produtos.py::criar_produto` com `sku`.
    """
    carrier = await db.get(Carrier, transportadora_id)
    if carrier is None:
        raise TransportadoraNotFoundError()

    senha = gerar_senha()
    senha_hash = hash_password(senha)

    for tentativa in range(TENTATIVAS_CODIGO):
        carregamento = Carregamento(
            transportadora_id=carrier.id,
            codigo=gerar_codigo(),
            senha_hash=senha_hash,
            criado_por=criado_por,
        )
        db.add(carregamento)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if tentativa == TENTATIVAS_CODIGO - 1:
                raise
            continue
        await db.refresh(carregamento)
        return carregamento, senha

    raise RuntimeError("inalcançável: o laço acima só sai por return ou raise")


async def atribuir_pedido(db: AsyncSession, *, carregamento_id: int, pedido_id: uuid.UUID) -> Order:
    """Põe o pedido no lote, congelando a origem do lote no primeiro pedido.

    `with_for_update()` nos dois (regra 3 do CLAUDE.md): sem ele, duas
    atribuições concorrentes leem o mesmo `origem_*` vazio, as duas congelam
    origens diferentes e a última vence — o lote passaria a alegar uma origem
    que não é a de todos os seus pedidos.
    """
    carregamento = (
        await db.execute(
            select(Carregamento).where(Carregamento.id == carregamento_id).with_for_update()
        )
    ).scalar_one_or_none()
    if carregamento is None:
        raise CarregamentoNotFoundError()

    pedido = (
        await db.execute(select(Order).where(Order.id == pedido_id).with_for_update())
    ).scalar_one_or_none()
    if pedido is None:
        raise OrderNotFoundError()

    if pedido.carregamento_id is not None and pedido.carregamento_id != carregamento.id:
        raise PedidoJaCarregadoError()

    # A sentinela de "origem ainda não congelada" é "este lote já tem algum
    # pedido?", não "o rótulo está vazio?". `orders.origem_rotulo` é
    # NULLABLE — checkout sem fornecedor resolvido deixa `origem_*` como
    # None (`app/services/pedidos.py`) — então um primeiro pedido de origem
    # nula fazia `origem_rotulo or ""` continuar vazio e o congelamento
    # nunca "pegava": um SEGUNDO pedido, de origem real, caía no mesmo ramo
    # "ainda não congelado" e sobrescrevia a origem do lote em silêncio, sem
    # 409 nenhum. Um lote de pedidos sem origem é um lote coerente — o
    # simulador de posição (task 6) e o rastreio degradam para posição
    # nula — só não pode se misturar com um lote de origem real, e é essa
    # mistura que a query abaixo, e não a string, detecta.
    ja_tem_pedido = (
        await db.execute(select(Order.id).where(Order.carregamento_id == carregamento.id).limit(1))
    ).scalar_one_or_none()

    if ja_tem_pedido is None:
        carregamento.origem_rotulo = pedido.origem_rotulo or ""
        carregamento.origem_lat = pedido.origem_lat
        carregamento.origem_lng = pedido.origem_lng
    elif (carregamento.origem_lat, carregamento.origem_lng) != (
        pedido.origem_lat,
        pedido.origem_lng,
    ):
        raise CarregamentoOrigemDivergenteError()

    carrier = await db.get(Carrier, carregamento.transportadora_id)
    pedido.carregamento_id = carregamento.id
    # O rastreio do aluno mostra este nome a partir da task 6 (D12) — antes
    # dela ele mostrava uma constante para todo pedido do sistema.
    pedido.carrier_name = carrier.name if carrier else pedido.carrier_name

    await db.commit()
    await db.refresh(pedido)
    return pedido


async def listar_carregamentos(
    db: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Carregamento], int]:
    itens = (
        (
            await db.execute(
                select(Carregamento)
                .order_by(Carregamento.criado_em.desc(), Carregamento.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    total = (await db.execute(select(func.count()).select_from(Carregamento))).scalar_one()
    return list(itens), total


async def buscar_carregamento(db: AsyncSession, carregamento_id: int) -> Carregamento:
    carregamento = await db.get(Carregamento, carregamento_id)
    if carregamento is None:
        raise CarregamentoNotFoundError()
    return carregamento


async def pedidos_do_carregamento(
    db: AsyncSession, *, carregamento_id: int, limit: int, offset: int
) -> list[Order]:
    resultado = await db.execute(
        select(Order)
        .where(Order.carregamento_id == carregamento_id)
        .order_by(Order.created_at.asc(), Order.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(resultado.scalars().all())
