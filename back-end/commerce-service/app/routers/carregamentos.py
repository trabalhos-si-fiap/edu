"""Rotas do carregamento. Prefixo `/shipments` — inglês na ROTA, português no
agregado, mesmo critério de `/partners` sobre `fornecedores` (spec B)."""

import uuid

from edu_common.security import create_access_token
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import requer_papel, uuid_do_usuario
from app.events.publisher import publish_event
from app.exceptions import (
    CarregamentoNotFoundError,
    CarregamentoOrigemDivergenteError,
    CredencialCarregamentoInvalidaError,
    OrderNotFoundError,
    PedidoJaCarregadoError,
    TransportadoraNotFoundError,
)
from app.ids import Int32Id
from app.models.transportadora import Carrier
from app.schemas.carregamento import (
    CarregamentoCriadoOut,
    CarregamentoIn,
    CarregamentoList,
    CarregamentoLoginIn,
    CarregamentoLoginOut,
    CarregamentoOut,
    PedidoDoCarregamentoIn,
)
from app.schemas.pedido import PedidoStaffOut
from app.services import carregamentos as services

router = APIRouter(prefix="/shipments", tags=["shipments"])

# Uma jornada, não uma semana. Ver `CarregamentoLoginOut`.
_EXPIRACAO_TOKEN_MINUTOS = 12 * 60


@router.post("/login", response_model=CarregamentoLoginOut)
async def login_carregamento(
    payload: CarregamentoLoginIn,
    db: AsyncSession = Depends(get_db),
) -> CarregamentoLoginOut:
    """Rota PÚBLICA por construção — é o ponto de entrada de quem ainda não
    tem credencial nenhuma, como `POST /auth/login`. A autorização que ela
    concede é estreita: um token de escopo de UM carregamento (ver
    `app/dependencies.py::ator_de_entrega`), nunca um papel da frota.
    """
    try:
        carregamento = await services.autenticar_carregamento(
            db,
            codigo=payload.codigo,
            senha=payload.senha,
            nome=payload.nome,
            contato=payload.contato,
        )
    except CredencialCarregamentoInvalidaError as exc:
        raise HTTPException(401, "Código ou senha inválidos") from exc

    token = create_access_token(
        str(carregamento.id),
        "carregamento",
        settings.jwt_secret,
        settings.jwt_algorithm,
        expires_minutes=_EXPIRACAO_TOKEN_MINUTOS,
    )
    return CarregamentoLoginOut(
        access_token=token,
        carregamento_id=carregamento.id,
        codigo=carregamento.codigo,
        origem_rotulo=carregamento.origem_rotulo,
    )


@router.post("", response_model=CarregamentoCriadoOut, status_code=status.HTTP_201_CREATED)
async def criar_carregamento(
    payload: CarregamentoIn,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> CarregamentoCriadoOut:
    try:
        carregamento, senha = await services.criar_carregamento(
            db,
            transportadora_id=payload.transportadora_id,
            criado_por=uuid_do_usuario(user),
        )
    except TransportadoraNotFoundError as exc:
        raise HTTPException(404, "Transportadora não encontrada") from exc

    carrier = await db.get(Carrier, carregamento.transportadora_id)
    # A senha em claro sai daqui para o barramento UMA vez, para a task 9
    # transformar em e-mail. Nenhum log deste módulo a menciona.
    await publish_event(
        "shipment.created",
        {
            "carregamento_id": carregamento.id,
            "codigo": carregamento.codigo,
            "senha": senha,
            "transportadora_id": carrier.id,
            "transportadora_nome": carrier.name,
            "transportadora_email": carrier.email,
        },
    )
    return CarregamentoCriadoOut(
        **CarregamentoOut.model_validate(carregamento).model_dump(), senha=senha
    )


@router.get("", response_model=CarregamentoList)
async def listar_carregamentos(
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CarregamentoList:
    itens, total = await services.listar_carregamentos(db, limit=limit, offset=offset)
    return CarregamentoList(
        items=[CarregamentoOut.model_validate(c) for c in itens],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{carregamento_id}", response_model=CarregamentoOut)
async def detalhe_carregamento(
    carregamento_id: Int32Id,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> CarregamentoOut:
    try:
        carregamento = await services.buscar_carregamento(db, carregamento_id)
    except CarregamentoNotFoundError as exc:
        raise HTTPException(404, "Carregamento não encontrado") from exc
    return CarregamentoOut.model_validate(carregamento)


@router.post("/{carregamento_id}/orders", response_model=PedidoStaffOut)
async def atribuir_pedido(
    carregamento_id: Int32Id,
    payload: PedidoDoCarregamentoIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> PedidoStaffOut:
    try:
        pedido = await services.atribuir_pedido(
            db,
            carregamento_id=carregamento_id,
            pedido_id=uuid.UUID(payload.pedido_id),
        )
    except ValueError as exc:  # uuid malformado no corpo
        raise HTTPException(422, "pedido_id inválido") from exc
    except CarregamentoNotFoundError as exc:
        raise HTTPException(404, "Carregamento não encontrado") from exc
    except OrderNotFoundError as exc:
        raise HTTPException(404, "Pedido não encontrado") from exc
    except CarregamentoOrigemDivergenteError as exc:
        raise HTTPException(409, CarregamentoOrigemDivergenteError.MENSAGEM) from exc
    except PedidoJaCarregadoError as exc:
        raise HTTPException(409, "Este pedido já está em outro carregamento") from exc
    return PedidoStaffOut.de_order(pedido)


@router.get("/{carregamento_id}/orders", response_model=list[PedidoStaffOut])
async def listar_pedidos_do_carregamento(
    carregamento_id: Int32Id,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PedidoStaffOut]:
    pedidos = await services.pedidos_do_carregamento(
        db, carregamento_id=carregamento_id, limit=limit, offset=offset
    )
    return [PedidoStaffOut.de_order(p) for p in pedidos]
