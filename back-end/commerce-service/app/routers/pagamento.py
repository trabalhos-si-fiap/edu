import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.exceptions import PaymentMethodNotFoundError
from app.schemas.pagamento import PaymentMethodIn, PaymentMethodOut, PaymentMethodPatch
from app.services import pagamento as services

router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")


@router.get("", response_model=list[PaymentMethodOut])
async def listar_metodos(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentMethodOut]:
    # Array puro, SEM envelope — ao contrário de `/products` e `/cart`. Não é
    # esquecimento, é o contrato medido do legacy (ver task-B9-report.md,
    # seção "Divergência da paginação").
    methods = await services.listar_metodos(db, uuid.UUID(user["sub"]))
    return [PaymentMethodOut.model_validate(m) for m in methods]


@router.post("", response_model=PaymentMethodOut, status_code=status.HTTP_201_CREATED)
async def criar_metodo(
    payload: PaymentMethodIn,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodOut:
    method = await services.criar_metodo(db, uuid.UUID(user["sub"]), payload)
    return PaymentMethodOut.model_validate(method)


@router.patch("/{method_id}", response_model=PaymentMethodOut)
async def definir_padrao(
    method_id: uuid.UUID,
    payload: PaymentMethodPatch,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodOut:
    try:
        method = await services.definir_padrao(db, uuid.UUID(user["sub"]), method_id, payload)
    except PaymentMethodNotFoundError as exc:
        raise _NOT_FOUND from exc
    return PaymentMethodOut.model_validate(method)


@router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def apagar_metodo(
    method_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await services.apagar_metodo(db, uuid.UUID(user["sub"]), method_id)
    except PaymentMethodNotFoundError as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
