from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id
from app.models.device_token import DeviceToken
from app.models.notificacao import Notificacao
from app.schemas.notificacao import DeviceRegisterIn, NotificationDataOut, NotificationOut

# Path em inglês para casar com `NotificationsApi` (`GET /notifications`,
# `POST/DELETE /notifications/devices`) — ver notifications_api.dart.
router = APIRouter(prefix="/notifications", tags=["notifications"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _para_notification_out(n: Notificacao) -> NotificationOut:
    return NotificationOut(
        id=str(n.id),
        title=n.titulo,
        body=n.descricao,
        data=NotificationDataOut(type=n.tipo, pedido_id=n.pedido_id, ocorrencia_id=n.ocorrencia_id),
        created_at=n.criado_em,
        read_at=n.lido_em,
    )


@router.get("", response_model=list[NotificationOut])
async def listar_notificacoes(
    apenas_nao_lidas: bool = False,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notificacao).where(Notificacao.aluno_id == aluno_id)
    if apenas_nao_lidas:
        query = query.where(Notificacao.lido_em.is_(None))
    query = query.order_by(Notificacao.criado_em.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return [_para_notification_out(n) for n in result.scalars().all()]


@router.patch("/{notificacao_id}/read", response_model=NotificationOut)
async def marcar_lida(
    notificacao_id: int,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Não é chamado hoje pelo Flutter (a tela não tem esse gesto ainda),
    mas fica pronto para quando adicionarmos tap-to-read/navigate.

    O filtro por `aluno_id` na mesma query, e não uma checagem à parte
    depois de buscar por `id`, é o que impede um aluno de marcar como lida
    (ou de sequer descobrir a existência de) a notificação de outro — sem
    ele, `notificacao_id` sozinho bastaria para qualquer usuário autenticado.
    """
    result = await db.execute(
        select(Notificacao).where(
            Notificacao.id == notificacao_id, Notificacao.aluno_id == aluno_id
        )
    )
    notificacao = result.scalar_one_or_none()
    if not notificacao:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificação não encontrada")

    if notificacao.lido_em is None:
        notificacao.lido_em = datetime.now(UTC)
        await db.commit()
        await db.refresh(notificacao)

    return _para_notification_out(notificacao)


@router.post("/devices", status_code=status.HTTP_201_CREATED)
async def registrar_device(
    payload: DeviceRegisterIn,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Casa com `NotificationsApi.registerDevice()`. MVP: só armazena o
    token — nenhum push real é disparado a partir daqui ainda.

    `on_conflict_do_nothing` faz o registro idempotente de forma atômica —
    duas requisições concorrentes com o mesmo (aluno_id, token) nunca geram
    IntegrityError nem duas linhas, sem precisar de um SELECT antes do
    INSERT (que teria uma janela de corrida entre o check e o write).
    """
    stmt = (
        pg_insert(DeviceToken)
        .values(aluno_id=aluno_id, token=payload.token, platform=payload.platform)
        .on_conflict_do_nothing(index_elements=["aluno_id", "token"])
    )
    await db.execute(stmt)
    await db.commit()

    return {"detail": "Dispositivo registrado"}


@router.delete("/devices/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_device(
    token: str,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """Casa com `NotificationsApi.unregisterDevice()`.

    O filtro por `aluno_id` impede que um usuário apague o token de
    dispositivo de outro só por conhecer (ou adivinhar) o valor do token.
    """
    await db.execute(
        delete(DeviceToken).where(DeviceToken.aluno_id == aluno_id, DeviceToken.token == token)
    )
    await db.commit()
