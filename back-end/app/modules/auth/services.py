import uuid

from jose import JWTError
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.exceptions import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidToken,
    UserInactive,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterIn, TokenPair, UserPatch
from app.modules.auth.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def issue_token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


async def register(session: AsyncSession, data: RegisterIn) -> User:
    user = User(
        name=data.name,
        email=data.email,
        phone=data.phone,
        birth_date=data.birth_date,
        education_level=data.education_level.value,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise EmailAlreadyRegistered() from None
    await session.refresh(user)
    logger.info("auth: user registered id={}", user.id)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    normalized_email = email.lower()
    stmt = select(User).where(User.email == normalized_email)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        # Timing defense: always perform a verify so response time does not
        # reveal whether the account exists.
        verify_password(password, DUMMY_PASSWORD_HASH)
        raise InvalidCredentials()

    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()

    if not user.is_active:
        raise UserInactive()

    return user


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def update_me(session: AsyncSession, user: User, data: UserPatch) -> User:
    # Only the fields the client actually sent are applied (partial update).
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    logger.info("auth: user profile updated id={}", user.id)
    return user


async def refresh_tokens(session: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
    except JWTError as exc:
        raise InvalidToken() from exc

    if payload.get("type") != "refresh":
        raise InvalidToken()

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise InvalidToken()

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError) as exc:
        raise InvalidToken() from exc

    user = await get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise InvalidToken()

    return issue_token_pair(user)
