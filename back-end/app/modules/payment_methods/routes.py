import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.payment_methods import services
from app.modules.payment_methods.exceptions import PaymentMethodNotFound
from app.modules.payment_methods.schemas import (
    PaymentMethodIn,
    PaymentMethodOut,
    PaymentMethodPatch,
)

router = APIRouter(prefix="/payment-methods", tags=["payment-methods"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found"
)


@router.get("", response_model=list[PaymentMethodOut])
async def list_methods(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PaymentMethodOut]:
    methods = await services.list_methods(session, user.id)
    return [PaymentMethodOut.model_validate(m) for m in methods]


@router.post("", response_model=PaymentMethodOut, status_code=status.HTTP_201_CREATED)
async def create_method(
    payload: PaymentMethodIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentMethodOut:
    method = await services.create_method(session, user.id, payload)
    return PaymentMethodOut.model_validate(method)


@router.patch("/{method_id}", response_model=PaymentMethodOut)
async def update_method(
    method_id: uuid.UUID,
    payload: PaymentMethodPatch,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentMethodOut:
    try:
        method = await services.set_default(session, user.id, method_id, payload)
    except PaymentMethodNotFound as exc:
        raise _NOT_FOUND from exc
    return PaymentMethodOut.model_validate(method)


@router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_method(
    method_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        await services.delete_method(session, user.id, method_id)
    except PaymentMethodNotFound as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
