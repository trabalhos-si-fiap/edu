import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, uuid_do_usuario
from app.events.publisher import publish_event
from app.exceptions import (
    CarrinhoOrigemMistaError,
    CartProductNotFoundError,
    EmptyCartError,
    OrderNotFoundError,
)
from app.models.pedido import Order, PedidoStatusHistorico
from app.redis_client import get_redis
from app.routers.admin import confirmar_pagamento_do_pedido
from app.schemas.carrinho import QUANTIDADE_MAXIMA, CartItemIn, CartOut
from app.schemas.pedido import (
    OrderCreateIn,
    OrderOut,
    PagamentoConfirmadoOut,
    PedidoStatusHistoricoOut,
    PrevisaoEntregaOut,
)
from app.services import carrinho as cart_services
from app.services import pedidos as services
from app.services.auth_client import AuthServiceUnavailableError, get_address
from app.services.codigos_pagamento import gerar_codigo_pagamento
from app.services.media import presign_cart, presigned_image_url
from app.services.previsao_entrega import MINIMO_AMOSTRAS, estimar_prazo_entrega
from app.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/orders", tags=["orders"])


async def _order_out(order: Order, *, storage: ObjectStorage, redis: aioredis.Redis) -> OrderOut:
    out = OrderOut.de_order(order)
    for item in out.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return out


OBSERVACAO_CONFIRMACAO_AUTOMATICA = "Pagamento confirmado automaticamente"


async def _confirmar_pagamento_automaticamente(db: AsyncSession, order: Order) -> Order:
    """CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO, sem verificar pagamento
    nenhum (`settings.confirmar_pagamento_automatico`).

    Mesmo encadeamento do admin, não uma cópia dele: histórico, eventos e o
    guard de idempotência saem de `confirmar_pagamento_do_pedido`. Sem pessoa
    por trás, `user_id=None` — a convenção de `PedidoStatusHistorico`.

    `db.expunge(order)` antes: o `SELECT ... FOR UPDATE` de
    `transicionar_pedido` devolve a instância que já está no identity map SEM
    repopular os atributos (ver a docstring de `admin.py::confirmar_pagamento`).
    Soltá-la faz o funil validar contra a linha do banco, não contra o objeto
    que o checkout acabou de montar.

    NUNCA derruba o checkout. O pedido já foi gravado, o carrinho já foi
    esvaziado e `order.created` já saiu — um 500 aqui mostraria erro ao aluno
    por uma compra feita. Qualquer falha (broker fora no meio, corrida com o
    admin) vira log, e a resposta devolve o pedido como ele ficou no banco.
    Quem termina é o botão do admin, retentável por construção.
    """
    db.expunge(order)
    try:
        await confirmar_pagamento_do_pedido(
            db, order.id, None, observacao=OBSERVACAO_CONFIRMACAO_AUTOMATICA
        )
    except Exception as exc:
        # Descarta o que a transição deixou pela metade antes de reler. Sem
        # `str(exc)`: o detalhe de um broker ou banco fora do ar pode trazer
        # URL com credencial (regra 5 do CLAUDE.md).
        await db.rollback()
        logger.warning(
            "orders: confirmação automática do pedido {} falhou ({}); o pedido segue "
            "como ficou e o admin pode confirmar pelo painel",
            order.id,
            type(exc).__name__,
        )
    return await services.buscar_pedido(db, order.user_id, order.id)


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
    pedidos = await services.listar_pedidos(db, uuid_do_usuario(user), limit=limit, offset=offset)
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
            db, uuid_do_usuario(user), payment_method, address=address
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
    if settings.confirmar_pagamento_automatico:
        order = await _confirmar_pagamento_automaticamente(db, order)
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
        order = await services.buscar_pedido(db, uuid_do_usuario(user), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc
    return await _order_out(order, storage=storage, redis=redis)


@router.get("/{order_id}/status-history", response_model=list[PedidoStatusHistoricoOut])
async def historico_status(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Histórico completo dos NOVE estados internos — tabela sem cliente
    (`pedido_status_historico`), fica em português (ver
    `PedidoStatusHistoricoOut`).

    Morava em `GET /orders/{id}/tracking` (task C6, que a manteve sem
    mudança de contrato porque o Flutter de rastreio já a consumia dali).
    A task C8 muda o que `/tracking` devolve — o objeto que a tela de
    rastreio realmente renderiza (`rastreio_pedido`, em
    `app/routers/rastreio.py`) — e move este histórico para cá. Aqui o
    aluno vê a trilha real da operação: é a única superfície onde
    `CONFIRMADO` é observável, já que `PATCH
    /admin/orders/{id}/confirm-payment` (app/routers/admin.py) encadeia as
    duas transições até `AGUARDANDO_SEPARACAO` sem parar em `CONFIRMADO`
    (não há simulador de avanço de status na fase 2).

    Sem anotação de retorno de propósito (achado 7 da revisão da task C6):
    a função devolve `Sequence[PedidoStatusHistorico]` (linhas do ORM), não
    `list[PedidoStatusHistoricoOut]` — quem converte um no outro é o
    `response_model=` do decorator, não esta função. Mesmo padrão (sem
    anotação) de `previsao_entrega_pedido` logo abaixo, que também devolve
    um tipo diferente do que constrói inline.
    """
    # Garante que o pedido é do aluno antes de expor o histórico.
    try:
        await services.buscar_pedido(db, uuid_do_usuario(user), order_id)
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
        pedido = await services.buscar_pedido(db, uuid_do_usuario(user), order_id)
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
    e falhar por causa dele tornaria o botão inútil. Produto DESATIVADO
    (`products.active = false`) cai no mesmo caminho: `adicionar_item` o
    recusa com `CartProductNotFoundError`, e o `continue` abaixo devolve ao
    aluno o resto do pedido. É a mesma decisão pelo mesmo motivo — um item
    fora da prateleira não vale um erro na cara de quem só queria repetir a
    compra.

    NÃO É ATÔMICO, de propósito: `cart_services.adicionar_item` comita a
    cada item (`app/services/carrinho.py`), então uma recompra de N itens
    faz N commits — uma falha no meio deixa o carrinho parcialmente
    reposto. Mesma composição do legacy; a costura fica aqui, no router,
    para `services/pedidos.py` não ganhar dependência de escrita no
    carrinho (ver acima). `adicionar_item` levanta
    `CartProductNotFoundError` ANTES de qualquer escrita — o `select` do
    produto é a primeira coisa que ela faz —, então o `continue` abaixo não
    deixa a sessão em estado sujo.

    A OUTRA recusa de `adicionar_item` é `CarrinhoOrigemMistaError` (regra de
    origem única, spec B): o carrinho de hoje já tem item de um parceiro e a
    recompra traz item de outro. Ela NÃO é pulada como o produto fora de
    catálogo — pular deixaria a recompra "dar certo" repondo só parte do
    pedido, sem nada dizer por quê. Vira 409 com a mesma sentença de
    `POST /cart/items` (`app/routers/carrinho.py`), para o cliente exibir a
    mensagem do servidor em vez de inventar uma. `adicionar_item` também
    levanta esta ANTES de escrever o item recusado, mas a recompra não é
    atômica: os itens já repostos antes da recusa ficam no carrinho.

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
    user_id = uuid_do_usuario(user)
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
        except CarrinhoOrigemMistaError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=CarrinhoOrigemMistaError.MENSAGEM
            ) from exc

    if cart is None:
        # Nenhum produto do pedido existe mais — devolve o carrinho atual.
        cart = await cart_services.obter_carrinho(db, user_id)

    return await presign_cart(cart, storage=storage, redis=redis)


@router.post("/{order_id}/confirm-payment", response_model=PagamentoConfirmadoOut)
async def confirmar_pagamento(
    order_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PagamentoConfirmadoOut:
    """Devolve ao ALUNO o código copia-e-cola do pedido dele.

    NÃO confunda com `PATCH /admin/orders/{pedido_id}/confirm-payment`
    (`app/routers/admin.py`), que é do ADMIN (`requer_papel("admin")`) e faz
    `CRIADO -> CONFIRMADO -> AGUARDANDO_SEPARACAO`. A colisão é de nome, não
    de comportamento: esta rota não toca em status nenhum.

    Idempotente por construção — o código é derivado do `order_id`, então
    chamar duas vezes devolve a mesma coisa e nada é gravado.

    Sem `requer_papel(...)`: mesmo idioma de `listar_pedidos`,
    `detalhe_pedido` e `recomprar` acima, que também só pedem
    `Depends(get_current_user)`. O controle de acesso (regra 2 do CLAUDE.md)
    vem do FILTRO POR DONO em `services.buscar_pedido` — reaproveita
    `_buscar_com_itens`, o "único lugar que sabe filtrar pedido por dono" —
    não de um gate de papel: pedido de outro aluno cai no mesmo 404 que
    pedido inexistente, sem revelar qual dos dois é, e um staff/admin
    autenticado com o PRÓPRIO token não é dono do pedido de ninguém, então
    também cai em 404 ao tentar.
    """
    try:
        pedido = await services.buscar_pedido(db, uuid_do_usuario(user), order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    codigo = gerar_codigo_pagamento(pedido.id, pedido.payment_method)

    return PagamentoConfirmadoOut(
        order_id=pedido.id, payment_method=pedido.payment_method, payment_code=codigo
    )
