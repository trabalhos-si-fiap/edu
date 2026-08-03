from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.produto import Produto

router = APIRouter(prefix="/produtos", tags=["produtos"])


@router.get("")
async def listar_produtos(categoria: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Produto)
    if categoria:
        query = query.where(Produto.categoria == categoria)
    result = await db.execute(query)
    return result.scalars().all()
