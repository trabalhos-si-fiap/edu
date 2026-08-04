from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id, requer_papel
from app.models.user import User
from app.schemas.user import UserOut, UserUpdateIn

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@router.put("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdateIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if payload.nome is not None:
        user.nome = payload.nome
    if payload.telefone is not None:
        user.telefone = payload.telefone

    await db.commit()
    await db.refresh(user)
    return user


@router.get("", response_model=list[UserOut])
async def listar_usuarios(
    role: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Gestão de staff — só admin. Permite filtrar por papel (ex: ?role=separador)."""
    query = select(User)
    if role:
        query = query.where(User.role == role)
    query = query.order_by(User.criado_em.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
