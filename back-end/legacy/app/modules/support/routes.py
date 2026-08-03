from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.support import services
from app.modules.support.schemas import SupportMessageIn, SupportMessageOut

router = APIRouter(prefix="/support", tags=["support"])


@router.get("", response_model=list[SupportMessageOut])
async def list_messages(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[SupportMessageOut]:
    messages = await services.list_messages(session, user.id)
    return [SupportMessageOut.model_validate(m) for m in messages]


@router.post("", response_model=list[SupportMessageOut], status_code=status.HTTP_201_CREATED)
async def send_message(
    payload: SupportMessageIn,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[SupportMessageOut]:
    messages = await services.send_message(session, user.id, payload.body)
    return [SupportMessageOut.model_validate(m) for m in messages]
