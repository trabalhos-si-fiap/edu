import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.addresses import services
from app.modules.addresses.exceptions import AddressNotFound
from app.modules.addresses.schemas import AddressIn, AddressOut, AddressPatch
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

router = APIRouter(prefix="/auth/addresses", tags=["addresses"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")


@router.get("", response_model=list[AddressOut])
async def list_addresses(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AddressOut]:
    addresses = await services.list_addresses(session, user.id)
    return [AddressOut.model_validate(a) for a in addresses]


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(
    payload: AddressIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AddressOut:
    address = await services.create_address(session, user.id, payload)
    return AddressOut.model_validate(address)


@router.patch("/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: uuid.UUID,
    payload: AddressPatch,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AddressOut:
    try:
        address = await services.update_address(session, user.id, address_id, payload)
    except AddressNotFound as exc:
        raise _NOT_FOUND from exc
    return AddressOut.model_validate(address)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        await services.delete_address(session, user.id, address_id)
    except AddressNotFound as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
