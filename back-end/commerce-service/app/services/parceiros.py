"""Regra de parceiro. O filtro por ativo é uma REGRA, não um `if` por nome.

A spec proíbe `if parceiro.nome == "<nome do parceiro>"` em qualquer caminho
de decisão: quem decide se uma seção aparece é a coluna `ativo`, e desativar
o parceiro no painel esvazia a seção sem tocar em código. O nome de um
parceiro só existe em dado de seed (`app/seeds/parceiros.py`) — o teste
`test_no_partner_name_appears_in_a_decision_path` (task 11) trava isso
varrendo `app/` por nomes de parceiro fora daquele arquivo.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ParceiroNotFoundError
from app.models.produto import Fornecedor
from app.schemas.parceiro import ParceiroIn


async def listar_parceiros(
    db: AsyncSession, *, apenas_ativos: bool = False, limit: int, offset: int
) -> tuple[list[Fornecedor], int]:
    stmt = select(Fornecedor)
    count_stmt = select(func.count()).select_from(Fornecedor)
    if apenas_ativos:
        stmt = stmt.where(Fornecedor.ativo.is_(True))
        count_stmt = count_stmt.where(Fornecedor.ativo.is_(True))

    stmt = stmt.order_by(Fornecedor.nome).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def obter_parceiro(db: AsyncSession, parceiro_id: int) -> Fornecedor:
    parceiro = await db.get(Fornecedor, parceiro_id)
    if parceiro is None:
        raise ParceiroNotFoundError()
    return parceiro


async def criar_parceiro(db: AsyncSession, data: ParceiroIn) -> Fornecedor:
    parceiro = Fornecedor(**data.model_dump())
    db.add(parceiro)
    await db.commit()
    await db.refresh(parceiro)
    return parceiro


async def atualizar_parceiro(db: AsyncSession, parceiro_id: int, data: ParceiroIn) -> Fornecedor:
    parceiro = await obter_parceiro(db, parceiro_id)
    for campo, valor in data.model_dump().items():
        setattr(parceiro, campo, valor)
    await db.commit()
    await db.refresh(parceiro)
    return parceiro
