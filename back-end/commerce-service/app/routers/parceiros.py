"""CRUD de parceiro. A tabela é `fornecedores`; a rota é `/partners`.

O rename da tabela seria uma revision a mais e a spec não o pede — a decisão
está registrada nas Global Constraints do plano da spec B.

`GET` é aberto a QUALQUER papel autenticado, não só a admin: o app do aluno
precisa saber quais seções de parceiro mostrar (`GET /partners?active=true`,
fluxo de dados da spec). Escrita é só admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, requer_papel
from app.exceptions import ParceiroNotFoundError
from app.ids import Int32Id
from app.schemas.parceiro import ParceiroIn, ParceiroList, ParceiroOut
from app.services import parceiros as services

router = APIRouter(prefix="/partners", tags=["partners"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parceiro não encontrado")


@router.get("", response_model=ParceiroList)
async def listar_parceiros(
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    active: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ParceiroList:
    items, total = await services.listar_parceiros(
        db, apenas_ativos=active, limit=limit, offset=offset
    )
    return ParceiroList(
        items=[ParceiroOut.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{parceiro_id}", response_model=ParceiroOut)
async def detalhe_parceiro(
    parceiro_id: Int32Id,
    _user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParceiroOut:
    try:
        return ParceiroOut.model_validate(await services.obter_parceiro(db, parceiro_id))
    except ParceiroNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.post("", response_model=ParceiroOut, status_code=status.HTTP_201_CREATED)
async def criar_parceiro(
    payload: ParceiroIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> ParceiroOut:
    return ParceiroOut.model_validate(await services.criar_parceiro(db, payload))


@router.put("/{parceiro_id}", response_model=ParceiroOut)
async def atualizar_parceiro(
    parceiro_id: Int32Id,
    payload: ParceiroIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> ParceiroOut:
    try:
        return ParceiroOut.model_validate(
            await services.atualizar_parceiro(db, parceiro_id, payload)
        )
    except ParceiroNotFoundError as exc:
        raise _NOT_FOUND from exc
