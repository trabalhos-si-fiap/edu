"""Serviço de formas de pagamento. Porte de
`legacy/app/modules/payment_methods/services.py` (task B9).

Nomes de função em português (`listar_metodos`, `obter_metodo`,
`criar_metodo`, `definir_padrao`, `apagar_metodo`) — mesmo critério de
B6/B7/B8 (`listar_produtos`, `criar_review`, `obter_carrinho`,
`adicionar_item`): a seção "Interfaces" do brief especifica os nomes em
português mesmo o legacy usando inglês (correção 3 do CONTEXTO DO
CONTROLADOR do brief B9, ratificando o precedente da B8).

Achado (não uma correção): a promoção do primeiro método a default
(`criar_metodo`) e a promoção do mais antigo remanescente ao apagar o
default (`apagar_metodo`) são read→write sobre o mesmo agregado
(`payment_methods` de um `user_id`) SEM `with_for_update()` — medido que o
legacy também não tem lock nenhum aqui (`grep -rn "with_for_update|FOR
UPDATE" legacy/app/modules/payment_methods/` não acha nada). O
CONTEXTO DO CONTROLADOR do brief B9 pede para medir e replicar, registrando
como achado em vez de "consertar" sem escalar — ver task-B9-report.md.
`_limpar_outros_padroes` em si é uma única instrução `UPDATE` (atômica por
natureza), mas o par leitura-de-lista + escrita ao redor dela não é.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PaymentMethodNotFoundError
from app.models.pagamento import PaymentMethod
from app.schemas.pagamento import PaymentMethodIn, PaymentMethodPatch


async def listar_metodos(db: AsyncSession, user_id: uuid.UUID) -> list[PaymentMethod]:
    stmt = (
        select(PaymentMethod)
        .where(PaymentMethod.user_id == user_id)
        .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def obter_metodo(db: AsyncSession, user_id: uuid.UUID, method_id: uuid.UUID) -> PaymentMethod:
    stmt = select(PaymentMethod).where(
        PaymentMethod.id == method_id, PaymentMethod.user_id == user_id
    )
    method = (await db.execute(stmt)).scalar_one_or_none()
    if method is None:
        raise PaymentMethodNotFoundError()
    return method


async def _limpar_outros_padroes(
    db: AsyncSession, user_id: uuid.UUID, manter_id: uuid.UUID | None
) -> None:
    stmt = (
        update(PaymentMethod)
        .where(PaymentMethod.user_id == user_id, PaymentMethod.is_default.is_(True))
        .values(is_default=False)
    )
    if manter_id is not None:
        stmt = stmt.where(PaymentMethod.id != manter_id)
    await db.execute(stmt)


async def criar_metodo(
    db: AsyncSession, user_id: uuid.UUID, data: PaymentMethodIn
) -> PaymentMethod:
    method = PaymentMethod(
        user_id=user_id, type=data.type.value, **data.model_dump(exclude={"type"})
    )

    existing = await listar_metodos(db, user_id)
    if not existing:
        method.is_default = True

    if method.is_default:
        await _limpar_outros_padroes(db, user_id, manter_id=None)

    db.add(method)
    await db.commit()
    await db.refresh(method)
    return method


async def definir_padrao(
    db: AsyncSession,
    user_id: uuid.UUID,
    method_id: uuid.UUID,
    patch: PaymentMethodPatch,
) -> PaymentMethod:
    method = await obter_metodo(db, user_id, method_id)
    if patch.is_default is True:
        await _limpar_outros_padroes(db, user_id, manter_id=method.id)
        method.is_default = True
    elif patch.is_default is False:
        method.is_default = False
    await db.commit()
    await db.refresh(method)
    return method


async def apagar_metodo(db: AsyncSession, user_id: uuid.UUID, method_id: uuid.UUID) -> None:
    method = await obter_metodo(db, user_id, method_id)
    era_padrao = method.is_default
    await db.delete(method)
    await db.flush()

    # Promove o mais antigo remanescente a default, para o usuário sempre
    # ter um método padrão.
    if era_padrao:
        remaining = await listar_metodos(db, user_id)
        if remaining:
            remaining[0].is_default = True
    await db.commit()
