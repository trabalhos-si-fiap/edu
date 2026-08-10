import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas import SupportMessageIn, SupportMessageOut
from app.services import suporte as services

router = APIRouter(prefix="/support", tags=["support"])


@router.get("", response_model=list[SupportMessageOut])
async def listar_mensagens(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SupportMessageOut]:
    """ARRAY PURO, sem envelope — como `/orders` e `/payment-methods`, e ao
    contrário de `/products` e `/cart`. É o contrato, medido contra o legacy."""
    mensagens = await services.listar_mensagens(db, uuid.UUID(user_id))
    return [SupportMessageOut.model_validate(m) for m in mensagens]


@router.post("", response_model=list[SupportMessageOut], status_code=status.HTTP_201_CREATED)
async def enviar_mensagem(
    payload: SupportMessageIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SupportMessageOut]:
    """201 com a conversa COMPLETA, não só a mensagem criada.

    Os dois detalhes são contrato: o app troca a conversa inteira pela
    resposta, então devolver só a nova mensagem esvaziaria a tela.
    """
    mensagens = await services.enviar_mensagem(db, uuid.UUID(user_id), payload.body)
    return [SupportMessageOut.model_validate(m) for m in mensagens]
