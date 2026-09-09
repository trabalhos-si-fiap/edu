"""CRUD de transportadora. Porte do `CarrierService` do Java.

Sem lock: nenhuma operação aqui é read→write sobre valor compartilhado
(`definir_status` grava um valor absoluto vindo do cliente, não um
incremento). A regra 3 do CLAUDE.md não incide — e isso está escrito porque
a ausência de lock precisa ser uma decisão medida, não um esquecimento.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import TransportadoraNotFoundError
from app.models.transportadora import Carrier, CarrierStatus
from app.schemas.transportadora import TransportadoraIn


async def listar_transportadoras(
    db: AsyncSession,
    *,
    busca: str | None = None,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[Carrier], int]:
    stmt = select(Carrier)
    count_stmt = select(func.count()).select_from(Carrier)

    if busca:
        # `ilike` com parâmetro bound — o pattern vai como VALOR, nunca
        # concatenado na string SQL (regra 1 do CLAUDE.md).
        pattern = f"%{busca}%"
        stmt = stmt.where(Carrier.name.ilike(pattern))
        count_stmt = count_stmt.where(Carrier.name.ilike(pattern))
    if status:
        stmt = stmt.where(Carrier.status == status)
        count_stmt = count_stmt.where(Carrier.status == status)

    stmt = stmt.order_by(Carrier.name).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def obter_transportadora(db: AsyncSession, carrier_id: int) -> Carrier:
    carrier = await db.get(Carrier, carrier_id)
    if carrier is None:
        raise TransportadoraNotFoundError()
    return carrier


async def criar_transportadora(db: AsyncSession, data: TransportadoraIn) -> Carrier:
    payload = data.model_dump()
    payload["status"] = payload["status"].value
    carrier = Carrier(**payload)
    db.add(carrier)
    await db.commit()
    await db.refresh(carrier)
    return carrier


async def atualizar_transportadora(
    db: AsyncSession, carrier_id: int, data: TransportadoraIn
) -> Carrier:
    carrier = await obter_transportadora(db, carrier_id)
    payload = data.model_dump()
    payload["status"] = payload["status"].value
    for campo, valor in payload.items():
        setattr(carrier, campo, valor)
    await db.commit()
    await db.refresh(carrier)
    return carrier


async def definir_status(db: AsyncSession, carrier_id: int, status: CarrierStatus) -> Carrier:
    carrier = await obter_transportadora(db, carrier_id)
    carrier.status = status.value
    await db.commit()
    await db.refresh(carrier)
    return carrier
