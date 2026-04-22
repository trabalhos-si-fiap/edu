import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth import services
from app.modules.auth.models import User
from app.modules.auth.security import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED

    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise _UNAUTHORIZED from exc

    if payload.get("type") != "access":
        raise _UNAUTHORIZED

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise _UNAUTHORIZED

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError) as exc:
        raise _UNAUTHORIZED from exc

    user = await services.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED

    return user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    # get_current_user already validates is_active; this wrapper exists so
    # future role/2FA gating can attach without changing call sites.
    return user
