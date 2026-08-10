"""Orquestração da rota no mapa e da previsão de ETA.

`app/services/directions.py` é a fronteira HTTP (só fala com a Google) e
`app/services/rastreio_routing.py` é matemática pura (Haversine, sem I/O).
Este módulo é quem carrega o pedido e orquestra os dois: `rota_do_pedido`
busca o pedido, valida o snapshot de endereço, memoiza no Redis e chama
`directions`; `prever_eta` valida ownership e chama `rastreio_routing`.

Porte de `legacy/app/modules/tracking/services.py::get_order_route` e
`::predict_eta` (task C9). Duas divergências deliberadas do legacy:

1. `order_id` chega aqui já como `uuid.UUID` (o tipo do path param do
   FastAPI), não como `str` — o `try: uuid.UUID(order_id) except ValueError`
   do legacy sai, porque um id malformado nunca chega até este módulo: o
   FastAPI devolve 422 antes. Ver `test_get_order_route_malformed_id_raises`
   em `tests/test_tracking_services.py`.
2. `prever_eta` ganha checagem de ownership (`buscar_pedido` antes de
   calcular) — decisão do usuário de 2026-08-08, não uma réplica do
   legacy. Ver o docstring de `prever_eta` abaixo.
"""

import uuid

import httpx
import redis.asyncio as aioredis
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import RouteUnavailableError
from app.models.pedido import Order
from app.schemas.rastreio import (
    CourierLocationIn,
    ETAPredictionOut,
    GeoPoint,
    RouteOut,
    RoutePoint,
)
from app.services import directions
from app.services.pedidos import buscar_pedido
from app.services.rastreio_routing import predict_route

# Destino usado SÓ pelo predict-eta, que ainda não tem consumidor no app (é
# para um futuro app de entregador) e precisa de coordenadas para a
# matemática de Haversine. A rota real do pedido (rota_do_pedido) deriva o
# destino do snapshot de endereço do pedido. Remover quando predict-eta
# ganhar uma fonte de endereço de verdade.
_MOCK_DESTINATION = GeoPoint(latitude=-23.561414, longitude=-46.655881)

# Centro de distribuição mockado (origem da rota) — Cajamar/SP. Emparelhado
# com _MOCK_DESTINATION até a integração de pedidos/endereços fornecer
# coordenadas reais.
_MOCK_ORIGIN = GeoPoint(latitude=-23.3558, longitude=-46.8769)
_ORIGIN_LABEL = "Centro de Distribuição"
_DESTINATION_LABEL = "Endereço de entrega"

# Prefixo de chave no Redis para as rotas de pedido em cache.
_ROUTE_CACHE_PREFIX = "tracking:route:"


def _destination_query(order: Order) -> str:
    """Monta uma string de endereço geocodificável pela Google a partir do
    snapshot do pedido."""
    parts = [
        order.ship_street,
        order.ship_number,
        order.ship_neighborhood,
        f"{order.ship_city} - {order.ship_state}" if order.ship_city else None,
        order.ship_zip_code,
        "Brazil",
    ]
    return ", ".join(p for p in parts if p)


async def rota_do_pedido(
    db: AsyncSession,
    redis: aioredis.Redis,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
) -> RouteOut:
    """Devolve a rota de rua do centro de distribuição até o endereço do pedido.

    Carrega o pedido (ownership imposto na query — regra 2 do CLAUDE.md),
    monta o destino a partir do snapshot de endereço de entrega e só chama a
    Google Directions API em caso de cache miss (origem/destino são fixos
    por pedido, então a rota fica em cache no Redis para evitar chamadas
    pagas repetidas).
    """
    order = await buscar_pedido(db, user_id, order_id)
    if not order.ship_street:
        # Pedido sem snapshot de endereço de entrega (checkout anterior à
        # migration, ou sem endereço); não há para onde rotear.
        raise RouteUnavailableError("order has no delivery address")

    # A chave carrega o DONO, não só o pedido, mesmo com o ownership check já
    # feito acima em `buscar_pedido`. Defesa em profundidade (regra 2 do
    # CLAUDE.md): se esta função ou uma futura reescrita algum dia inverter a
    # ordem entre o cache lookup e o ownership check, uma chave sem o dono
    # devolveria a rota (com `ship_label` e as coordenadas do destino) do
    # dono para qualquer estranho autenticado que pedisse o mesmo
    # `order_id` — achado Important 2 da rodada de correção 1, medido pelo
    # revisor sob exatamente essa reordenação. Não há cache vivo em produção
    # para esta feature (ela nasce nesta branch), então não há entrada órfã
    # sob o prefixo antigo a migrar.
    cache_key = f"{_ROUTE_CACHE_PREFIX}{user_id}:{order_id}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return RouteOut.model_validate_json(cached)

    api_key = settings.google_maps_api_key
    if not api_key:
        logger.error("tracking: google_maps_api_key is not configured")
        raise RouteUnavailableError("maps api key not configured")

    async with httpx.AsyncClient() as client:
        result = await directions.fetch_directions(
            client,
            origin=(_MOCK_ORIGIN.latitude, _MOCK_ORIGIN.longitude),
            destination=_destination_query(order),
            api_key=api_key,
        )

    route = RouteOut(
        origin=RoutePoint(
            label=_ORIGIN_LABEL,
            latitude=_MOCK_ORIGIN.latitude,
            longitude=_MOCK_ORIGIN.longitude,
        ),
        destination=RoutePoint(
            label=order.ship_label or _DESTINATION_LABEL,
            latitude=result.destination_latitude,
            longitude=result.destination_longitude,
        ),
        polyline=result.polyline,
        distance_text=result.distance_text,
        distance_km=result.distance_km,
        duration_text=result.duration_text,
        duration_minutes=result.duration_minutes,
    )

    await redis.set(
        cache_key,
        route.model_dump_json(),
        ex=settings.tracking_route_cache_ttl_seconds,
    )
    logger.info("tracking: route computed order={} user={}", order_id, user_id)
    return route


async def prever_eta(
    db: AsyncSession,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    courier: CourierLocationIn,
) -> ETAPredictionOut:
    """Estima o tempo restante de entrega a partir da posição atual do entregador.

    Divergência deliberada nº 6 (decisão do usuário, 2026-08-08 — não
    relitigar): o legacy (`app/modules/tracking/services.py:78`) nunca
    carrega o pedido aqui — `order_id` só entra no log, e o destino é
    sempre `_MOCK_DESTINATION`. Ou seja, qualquer aluno autenticado podia
    pedir a ETA de qualquer `order_id`, inclusive um que não existe ou
    pertence a outro aluno. `buscar_pedido` abaixo fecha esse buraco: filtra
    por `user_id` (regra 2 do CLAUDE.md) e levanta `OrderNotFoundError`
    para um pedido inexistente ou alheio, antes de calcular qualquer coisa.
    O resultado do pedido não é usado no cálculo — o destino continua sendo
    `_MOCK_DESTINATION`, pelas mesmas razões do legacy.

    Delega a geometria/matemática da ETA para
    :func:`rastreio_routing.predict_route` e mapeia o resultado no schema
    de resposta público.
    """
    await buscar_pedido(db, user_id, order_id)

    destination = _MOCK_DESTINATION

    prediction = predict_route(
        (courier.latitude, courier.longitude),
        (destination.latitude, destination.longitude),
        average_speed_kmh=settings.tracking_average_speed_kmh,
        urban_route_factor=settings.tracking_urban_route_factor,
    )

    logger.info(
        "tracking: eta computed order={} user={} distance_km={} eta_min={} traffic={}",
        order_id,
        user_id,
        prediction.distance_km,
        prediction.eta_minutes,
        prediction.traffic_level,
    )

    return ETAPredictionOut(
        eta_minutes=prediction.eta_minutes,
        eta_text=prediction.eta_text,
        distance_km=prediction.distance_km,
        straight_line_distance_km=prediction.straight_line_distance_km,
        average_speed_kmh=prediction.effective_speed_kmh,
        traffic_level=prediction.traffic_level,
        route_status=prediction.route_status,
        courier_location=GeoPoint(latitude=courier.latitude, longitude=courier.longitude),
        destination_location=destination,
    )
