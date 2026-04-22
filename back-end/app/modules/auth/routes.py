from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.redis_client import get_redis
from app.modules.auth import services
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidToken,
    RateLimitExceeded,
    UserInactive,
)
from app.modules.auth.models import User
from app.modules.auth.rate_limit import check_login_rate_limit
from app.modules.auth.schemas import (
    AuthResponse,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthResponse:
    try:
        user = await services.register(session, payload)
    except EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    return AuthResponse(
        user=UserOut.model_validate(user),
        tokens=services.issue_token_pair(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> AuthResponse:
    ip = request.client.host if request.client else "unknown"
    try:
        await check_login_rate_limit(redis, ip=ip, email=payload.email)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    try:
        user = await services.authenticate(session, payload.email, payload.password)
    except (InvalidCredentials, UserInactive) as exc:
        raise _INVALID_CREDENTIALS from exc

    return AuthResponse(
        user=UserOut.model_validate(user),
        tokens=services.issue_token_pair(user),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenPair:
    try:
        return await services.refresh_tokens(session, payload.refresh_token)
    except InvalidToken as exc:
        raise _INVALID_CREDENTIALS from exc


@router.get("/me", response_model=UserOut)
async def me(
    user: Annotated[User, Depends(get_current_user)],
) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/logout")
async def logout(
    _user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    # MVP no-op: the client drops its tokens. Server-side revocation via a
    # Redis blocklist keyed by jti is a future enhancement — see the Auth TODOs.
    return {"detail": "ok"}
