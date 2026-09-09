"""Rotas de transportadora. Porte do `CarrierController` do Java.

Todas as cinco rotas são admin-only: a frota de transportadora é dado
operacional interno, sem análogo ao `GET /partners` aberto a qualquer papel
autenticado — nenhum app de aluno/separador/entregador lê `/carriers`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.exceptions import TransportadoraNotFoundError
from app.ids import Int32Id
from app.models.transportadora import CarrierStatus
from app.schemas.transportadora import (
    TransportadoraIn,
    TransportadoraList,
    TransportadoraOut,
    TransportadoraStatusIn,
)
from app.services import transportadoras as services

router = APIRouter(prefix="/carriers", tags=["carriers"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier not found")


@router.get("", response_model=TransportadoraList)
async def listar_transportadoras(
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=150),
    status: CarrierStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TransportadoraList:
    items, total = await services.listar_transportadoras(
        db,
        busca=search,
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )
    return TransportadoraList(
        items=[TransportadoraOut.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{carrier_id}", response_model=TransportadoraOut)
async def detalhe_transportadora(
    carrier_id: Int32Id,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> TransportadoraOut:
    try:
        return TransportadoraOut.model_validate(await services.obter_transportadora(db, carrier_id))
    except TransportadoraNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.post("", response_model=TransportadoraOut, status_code=status.HTTP_201_CREATED)
async def criar_transportadora(
    payload: TransportadoraIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> TransportadoraOut:
    return TransportadoraOut.model_validate(await services.criar_transportadora(db, payload))


@router.put("/{carrier_id}", response_model=TransportadoraOut)
async def atualizar_transportadora(
    carrier_id: Int32Id,
    payload: TransportadoraIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> TransportadoraOut:
    try:
        return TransportadoraOut.model_validate(
            await services.atualizar_transportadora(db, carrier_id, payload)
        )
    except TransportadoraNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.patch("/{carrier_id}/status", response_model=TransportadoraOut)
async def definir_status_transportadora(
    carrier_id: Int32Id,
    payload: TransportadoraStatusIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> TransportadoraOut:
    try:
        return TransportadoraOut.model_validate(
            await services.definir_status(db, carrier_id, payload.status)
        )
    except TransportadoraNotFoundError as exc:
        raise _NOT_FOUND from exc
