from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.notifications import services
from app.modules.notifications.exceptions import DeviceTokenNotFound
from app.modules.notifications.schemas import DeviceTokenIn, DeviceTokenOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device token not found")


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[NotificationOut]:
    """Return the user's notification history, newest first."""
    items = await services.list_notifications(session, user.id, limit=limit, offset=offset)
    return [NotificationOut.model_validate(n) for n in items]


@router.post("/devices", response_model=DeviceTokenOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceTokenIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeviceTokenOut:
    device = await services.register_device_token(session, user.id, payload)
    return DeviceTokenOut.model_validate(device)


@router.delete("/devices/{token}", status_code=status.HTTP_204_NO_CONTENT)
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
