"""Posição do carregamento: a porta de escrita, a leitura, e o congelamento do
destino.

`registrar_posicao` é a ÚNICA função que escreve em `posicao_entrega`. O
simulador (`app/services/simulador_posicao.py`) é um chamador dela; um
aparelho com GPS seria outro, chamando exatamente esta assinatura. Trocar de
fonte é acrescentar um chamador e desligar o simulador — não reescrever a
leitura, o model nem a tela.
"""

from decimal import Decimal

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.carregamento import Carregamento, PosicaoEntrega
from app.models.pedido import Order
from app.services import directions
from app.services.rastreio import _destination_query

# Coordenadas ficam em `Numeric(9, 6)` (regra 4 do CLAUDE.md, coordenadas
# quantizadas): gravar mais casas do que a coluna guarda faria o valor lido
# de volta divergir do valor computado.
_CASAS = Decimal("0.000001")


async def registrar_posicao(
    db: AsyncSession, carregamento_id: int, lat: Decimal, lng: Decimal
) -> None:
    """A ÚNICA porta de escrita de posição. Um GPS real seria outro chamador."""
    db.add(PosicaoEntrega(carregamento_id=carregamento_id, lat=lat, lng=lng))
    await db.commit()


async def ultima_posicao(db: AsyncSession, carregamento_id: int) -> PosicaoEntrega | None:
    resultado = await db.execute(
        select(PosicaoEntrega)
        .where(PosicaoEntrega.carregamento_id == carregamento_id)
        .order_by(PosicaoEntrega.registrado_em.desc(), PosicaoEntrega.id.desc())
        .limit(1)
    )
    return resultado.scalars().first()


async def congelar_destino(db: AsyncSession, order: Order) -> None:
    """Resolve a coordenada do endereço de entrega e a grava no pedido.

    Roda UMA vez, na coleta. `addresses` não guarda coordenada (medido em
    `auth-users-service/app/models/address.py`), e quem sabe converter
    endereço em par lat/lng é a mesma fronteira que `GET /orders/{id}/route`
    já usa (`app/services/rastreio.py::_destination_query`, importada daqui
    em vez de duplicada).

    **Nunca levanta.** Sem chave, sem endereço, provedor fora do ar: o pedido
    segue sem coordenada, o simulador o ignora, e o rastreio devolve
    `courier_position: null`. Impedir uma coleta porque a Google não
    respondeu seria trocar um mapa parado por uma operação parada.
    """
    if order.destino_lat is not None or not order.ship_street:
        return
    carregamento = (
        await db.get(Carregamento, order.carregamento_id) if order.carregamento_id else None
    )
    if carregamento is None or carregamento.origem_lat is None:
        return
    if not settings.google_maps_api_key:
        logger.info("posicao: sem chave da Google, pedido {} fica sem destino", order.id)
        return

    try:
        async with httpx.AsyncClient() as client:
            resultado = await directions.fetch_directions(
                client,
                origin=(float(carregamento.origem_lat), float(carregamento.origem_lng)),
                destination=_destination_query(order),
                api_key=settings.google_maps_api_key,
            )
        # A conversão e o commit ficam DENTRO do mesmo `try` (fix round 1,
        # achado Important): um valor que a Google devolve com `status: OK`
        # mas que não vira `Decimal` (`decimal.InvalidOperation`), ou uma
        # falha pontual no commit, são exatamente o mesmo tipo de "o
        # provedor/a infra não cooperou" que o bloco de cima já protege — a
        # garantia é da FUNÇÃO, não de quem a chama (`confirmar_coleta` não
        # tem, nem deveria precisar de, um guard próprio aqui). As duas
        # conversões ficam em variáveis locais antes de tocar `order`: se a
        # segunda falhar, a primeira nunca chega a mutar o objeto rastreado
        # pela sessão.
        lat = Decimal(str(resultado.destination_latitude)).quantize(_CASAS)
        lng = Decimal(str(resultado.destination_longitude)).quantize(_CASAS)
        order.destino_lat = lat
        order.destino_lng = lng
        await db.commit()
    except Exception:
        # Sem `str(exc)` no log: o detalhe do provedor pode carregar a chave
        # da API ou o endereço completo do aluno (regra 5 do CLAUDE.md, mesma
        # razão registrada em `app/routers/rastreio.py`).
        logger.warning("posicao: destino não resolvido para o pedido {}", order.id)
