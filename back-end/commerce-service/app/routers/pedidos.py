import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.events.publisher import publish_event
from app.exceptions import CartProductNotFoundError, EmptyCartError, OrderNotFoundError
from app.models.pedido import Order, PedidoStatusHistorico
from app.redis_client import get_redis
from app.schemas.carrinho import QUANTIDADE_MAXIMA, CartItemIn, CartOut
from app.schemas.pedido import (
    OrderCreateIn,
    OrderOut,
    PedidoStatusHistoricoOut,
    PrevisaoEntregaOut,
)
from app.services import carrinho as cart_services
from app.services import pedidos as services
from app.services.auth_client import AuthServiceUnavailableError, get_address
from app.services.media import presign_cart, presigned_image_url
from app.services.previsao_entrega import MINIMO_AMOSTRAS, estimar_prazo_entrega
from app.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/orders", tags=["orders"])


async def _order_out(order: Order, *, storage: ObjectStorage, redis: aioredis.Redis) -> OrderOut:
    out = OrderOut.de_order(order)
    for item in out.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return out


@router.get("", response_model=list[OrderOut])
async def listar_pedidos(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OrderOut]:
    """ARRAY PURO, sem envelope — ao contrário de `/products` e `/cart`.

    Isso é contrato, não descuido: o app faz `jsonDecode(body) as List` aqui
    e `jsonDecode(body)['items']` lá. Reproduzir a inconsistência é o
    trabalho; "consertá-la" quebraria a tela de pedidos.

    Ordenado por `created_at desc`; `limit` 1-100 com default 50 (o de
    `/products` é 20 — também medido, também diferente de propósito).
    """
    pedidos = await services.listar_pedidos(db, uuid.UUID(user["sub"]), limit=limit, offset=offset)
    return [await _order_out(p, storage=storage, redis=redis) for p in pedidos]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def criar_pedido(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
    payload: OrderCreateIn | None = None,
) -> OrderOut:
    """Corpo OPCIONAL — `payload: OrderCreateIn | None = None`. O legacy
    aceita `POST /orders` sem corpo nenhum, e o app antigo fazia isso."""
    payment_method = payload.payment_method if payload is not None else ""
    address_id = payload.address_id if payload is not None else None

    address: dict | None = None
    if address_id is not None:
        try:
            address = await get_address(user["raw_token"], address_id)
        except AuthServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Serviço de usuários indisponível",
            ) from exc
        if address is None:
            # Id obsoleto ou de outro usuário é erro do cliente, não 404 do
            # pedido — é assim que o legacy trata.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid delivery address"
            )

    try:
        order = await services.criar_pedido_do_carrinho(
            db, uuid.UUID(user["sub"]), payment_method, address=address
        )
    except EmptyCartError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty"
        ) from exc

    # `str(order.id)`: `orders.id` é UUID desde a fase 2 e JSON não tem tipo
    # UUID — o transporte (`edu_common/events.py`, `json.dumps(payload)`)
    # estoura `TypeError` com o valor cru. As CHAVES continuam em português:
    # renomeá-las dessincronizaria produtor e consumidor sem nenhum cliente
    # pedindo. Só o tipo do valor muda.
    await publish_event(
        "order.created",
        {
            "pedido_id": str(order.id),
            "aluno_id": str(order.user_id),
            "valor_total": float(order.total),
        },
    )
    return await _order_out(order, storage=storage, redis=redis)


@router.get("/{order_id}", response_model=OrderOut)
async def detalhe_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> OrderOut:
    """Não existe no legacy, não colide com nada, e fica — traduzida: devolve
    o MESMO `OrderOut` da listagem."""
    try:
        order = await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    return await _order_out(order, storage=storage, redis=redis)


@router.get("/{order_id}/tracking", response_model=list[PedidoStatusHistoricoOut])
async def rastreio_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Histórico de status do pedido — tabela sem cliente
    (`pedido_status_historico`), fica em português (ver
    `PedidoStatusHistoricoOut`).

    Esta rota não está no plano da task C6 (nem no legacy, que não tem
    conceito de histórico granulado assim) — é mantida sem mudança de
    contrato porque o Flutter de rastreio já a consome
    (`front-end-flutter/lib/features/order_tracking/data/order_service.dart:49`,
    `GET /orders/{id}/tracking`). Apagá-la quebraria a tela de rastreio sem
    nenhum pedido do brief para isso. O ownership passou a usar
    `services.buscar_pedido` — mesma técnica usada em `detalhe_pedido` e em
    `previsao_entrega_pedido` abaixo — em vez do `where` inline que a rota
    tinha antes desta task.

    Sem anotação de retorno de propósito (achado 7 da revisão da task C6):
    a função devolve `Sequence[PedidoStatusHistorico]` (linhas do ORM), não
    `list[PedidoStatusHistoricoOut]` — quem converte um no outro é o
    `response_model=` do decorator, não esta função. Mesmo padrão (sem
    anotação) de `previsao_entrega_pedido` logo abaixo, que também devolve
    um tipo diferente do que constrói inline.
    """
    try:
        await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    historico = await db.execute(
        select(PedidoStatusHistorico)
        .where(PedidoStatusHistorico.order_id == order_id)
        .order_by(PedidoStatusHistorico.criado_em.asc())
        .limit(limit)
        .offset(offset)
    )
    return historico.scalars().all()


@router.get("/{order_id}/delivery-estimate", response_model=PrevisaoEntregaOut)
async def previsao_entrega_pedido(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Estimativa de prazo de entrega — se o pedido já tem uma data definida
    (pela previsão automática ao confirmar coleta, ou por uma ocorrência de
    atraso que o aluno aceitou), devolve ela. Caso contrário calcula "a
    partir de agora" com base no histórico real, e é transparente sobre
    quantas entregas embasam o número (`amostras_historicas`) e se ele é
    confiável (`confiavel`, false com poucas amostras).
    """
    try:
        pedido = await services.buscar_pedido(db, uuid.UUID(user["sub"]), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    if pedido.estimated_delivery_at is not None:
        # Já existe data definida — não recalcula por cima.
        _estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
        return PrevisaoEntregaOut(
            data_estimada=pedido.estimated_delivery_at,
            amostras_historicas=amostras,
            confiavel=amostras >= MINIMO_AMOSTRAS,
        )

    estimativa, amostras = await estimar_prazo_entrega(db, datetime.now(UTC))
    return PrevisaoEntregaOut(
        data_estimada=estimativa,
        amostras_historicas=amostras,
        confiavel=amostras >= MINIMO_AMOSTRAS,
    )


@router.post("/{order_id}/rebuy", response_model=CartOut)
async def recomprar(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage = Depends(get_storage),
    redis: aioredis.Redis = Depends(get_redis),
) -> CartOut:
    """Repõe no carrinho os itens de um pedido passado.

    Costura de composição no router, não no serviço: `services/pedidos.py`
    fica desacoplado de escrita no carrinho.

    Produto que saiu do catálogo é PULADO, não derruba a recompra — um
    pedido de meses atrás quase sempre tem pelo menos um item descontinuado,
    e falhar por causa dele tornaria o botão inútil.

    NÃO É ATÔMICO, de propósito: `cart_services.adicionar_item` comita a
    cada item (`app/services/carrinho.py`), então uma recompra de N itens
    faz N commits — uma falha no meio deixa o carrinho parcialmente
    reposto. Mesma composição do legacy; a costura fica aqui, no router,
    para `services/pedidos.py` não ganhar dependência de escrita no
    carrinho (ver acima). `adicionar_item` levanta
    `CartProductNotFoundError` ANTES de qualquer escrita — o `select` do
    produto é a primeira coisa que ela faz —, então o `continue` abaixo não
    deixa a sessão em estado sujo.

    NÃO É IDEMPOTENTE (achado 4 do code review): chamar esta rota duas
    vezes para o MESMO pedido soma os itens duas vezes, não reconhece que
    já rodou — `adicionar_item` INCREMENTA a quantidade existente do item
    do carrinho (`item.quantity +=`), então duas recompras seguidas de um
    pedido de 149.00 fecham o carrinho em 298.00, não 149.00. É exatamente
    a resposta natural a uma recompra que falhou no meio (apertar de
    novo): em vez de completar o que faltou, DOBRA o que já tinha sido
    reposto. Mantido de propósito — mesma composição do legacy;
    idempotência aqui seria mudança de design, não porte. `POST /orders`
    se protege do duplo toque com o lock de linha do carrinho e esvaziando
    o carrinho ao final do checkout; esta rota não tem equivalente.

    Quantidade CLAMPADA em `QUANTIDADE_MAXIMA` antes de repassar ao
    carrinho (achado 2 do code review): `cart_services.adicionar_item` faz
    `item.quantity +=` sem clampar contra o teto de `CartItemIn` — bug
    herdado do monólito (raiz em `app/services/carrinho.py`, de quem
    possui a paridade do carrinho, não desta rota), que deixa um item de
    carrinho crescer além do que `CartItemIn` aceitaria numa chamada só
    (ex.: duas chamadas de `POST /cart/items` com quantidade 999 cada
    somam 1998). Sem o clamp abaixo, um pedido com item de quantidade
    acima do teto estourava `ValidationError` não tratada ao montar
    `CartItemIn`, com os itens já processados ficando pela metade no
    carrinho.
    """
    user_id = uuid.UUID(user["sub"])
    try:
        order = await services.buscar_pedido(db, user_id, order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    cart: CartOut | None = None
    for item in order.items:
        quantidade = min(item.quantity, QUANTIDADE_MAXIMA)
        try:
            cart = await cart_services.adicionar_item(
                db, user_id, CartItemIn(product_id=item.product_id, quantity=quantidade)
            )
        except CartProductNotFoundError:
            continue

    if cart is None:
        # Nenhum produto do pedido existe mais — devolve o carrinho atual.
        cart = await cart_services.obter_carrinho(db, user_id)

    return await presign_cart(cart, storage=storage, redis=redis)
