from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NotificationDataOut(BaseModel):
    """Sub-objeto `data` — usado pelo Flutter para escolher ícone
    (`NotificationModel.type` lê `data['type']`) e, nas telas que
    implementarmos, navegar direto para o pedido/ocorrência."""

    type: str
    # `str`, não `int`, desde a task C10: `Notificacao.pedido_id` virou UUID
    # (ver app/models/notificacao.py) — JSON não tem tipo UUID, e o router
    # (`_para_notification_out`) já converte com `str(...)` antes de montar
    # este schema.
    order_id: str | None = None
    occurrence_id: int | None = None


class NotificationOut(BaseModel):
    """Casa com `NotificationModel.fromJson()`: id como string, title/body,
    data aninhado, created_at/read_at em vez de criado_em/lida.

    Campos explícitos — nunca devolvemos o objeto ORM `Notificacao` cru; ver
    `_para_notification_out` em `app/routers/notificacoes.py`.
    """

    id: str
    title: str
    body: str
    data: NotificationDataOut
    created_at: datetime
    read_at: datetime | None = None


class DeviceRegisterIn(BaseModel):
    """`token` é uma credencial (identifica o dispositivo junto ao FCM) —
    nunca deve ser logado. `max_length` casa com `DeviceToken.token`
    (`String(255)`) em `app/models/device_token.py`."""

    token: str = Field(min_length=1, max_length=255)
    platform: Literal["android", "ios", "web"] = "android"
