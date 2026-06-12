from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.notifications import services
from app.modules.notifications.exceptions import DeviceTokenNotFound
from app.modules.notifications.schemas import DeviceTokenIn, DeviceTokenOut

router = APIRouter(prefix="/notifications/devices", tags=["notifications"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device token not found")


@router.post("", response_model=DeviceTokenOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceTokenIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceTokenOut:
    device = await services.register_device_token(session, user.id, payload)
    return DeviceTokenOut.model_validate(device)


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    token: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        await services.delete_token(session, user.id, token)
    except DeviceTokenNotFound as exc:
        raise _NOT_FOUND from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
