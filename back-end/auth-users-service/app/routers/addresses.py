import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.address import Address
from app.schemas.address import AddressIn, AddressOut, AddressPatch

router = APIRouter(prefix="/auth/addresses", tags=["addresses"])


async def _desmarcar_outros_favoritos(db: AsyncSession, user_id: str, manter_id) -> None:
    """Garante no máximo um endereço favorito por usuário."""
    await db.execute(
        update(Address)
        .where(Address.user_id == user_id, Address.id != manter_id)
        .values(is_favorite=False)
    )


async def _buscar_endereco_do_usuario(
    db: AsyncSession, address_id: uuid.UUID, user_id: str
) -> Address:
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    endereco = result.scalar_one_or_none()
    if not endereco:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Endereço não encontrado")
    return endereco


@router.get("", response_model=list[AddressOut])
async def listar_enderecos(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Endereços do usuário, favorito primeiro."""
    result = await db.execute(
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_favorite.desc(), Address.criado_em.asc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def criar_endereco(
    payload: AddressIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # O primeiro endereço do usuário é sempre favorito, para garantir que
    # sempre haja um endereço padrão disponível no checkout.
    result = await db.execute(select(Address).where(Address.user_id == user_id))
    eh_primeiro = result.first() is None
    is_favorite = payload.is_favorite or eh_primeiro

    endereco = Address(
        user_id=user_id,
        label=payload.label,
        zip_code=payload.zip_code,
        street=payload.street,
        number=payload.number,
        complement=payload.complement,
        neighborhood=payload.neighborhood,
        city=payload.city,
        state=payload.state,
        is_favorite=is_favorite,
    )
    db.add(endereco)
    await db.flush()

    if is_favorite:
        await _desmarcar_outros_favoritos(db, user_id, endereco.id)

    await db.commit()
    await db.refresh(endereco)
    return endereco


@router.patch("/{address_id}", response_model=AddressOut)
async def atualizar_endereco(
    address_id: uuid.UUID,
    payload: AddressPatch,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    endereco = await _buscar_endereco_do_usuario(db, address_id, user_id)

    dados = payload.model_dump(exclude_unset=True)
    for campo, valor in dados.items():
        setattr(endereco, campo, valor)

    await db.flush()

    if dados.get("is_favorite") is True:
        await _desmarcar_outros_favoritos(db, user_id, endereco.id)

    await db.commit()
    await db.refresh(endereco)
    return endereco


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_endereco(
    address_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    endereco = await _buscar_endereco_do_usuario(db, address_id, user_id)
    era_favorito = endereco.is_favorite

    await db.delete(endereco)
    await db.flush()

    # Promove outro endereço a favorito, se algum restar, para o checkout
    # nunca ficar sem um endereço padrão quando existem outros cadastrados.
    if era_favorito:
        result = await db.execute(
            select(Address)
            .where(Address.user_id == user_id)
            .order_by(Address.criado_em.asc())
            .limit(1)
        )
        proximo = result.scalar_one_or_none()
        if proximo:
            proximo.is_favorite = True

    await db.commit()
