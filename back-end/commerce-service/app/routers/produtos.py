from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.produto import Product
from app.schemas.produto import ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def listar_produtos(
    category: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Catálogo — exige autenticação (qualquer papel).

    Gap de autorização #1 do sweep de segurança: a rota original não tinha
    NENHUM `Depends`, ficando completamente aberta. Não restringe por papel
    porque não há razão de negócio para isso — aluno monta carrinho,
    separador/entregador/admin também podem precisar consultar o catálogo.

    Paginado por contrato — sem teto, um catálogo grande derruba o app e o
    serviço junto.
    """
    query = select(Product)
    if category:
        query = query.where(Product.type == category)
    query = query.order_by(Product.id).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()
