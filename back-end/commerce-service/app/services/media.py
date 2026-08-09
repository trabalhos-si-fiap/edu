import redis.asyncio as aioredis

from app.config import settings
from app.schemas.carrinho import CartOut
from app.storage import ObjectStorage


def _public_endpoint() -> str:
    """Endpoint contra o qual a URL é assinada. Entra na chave de cache para
    que um endpoint trocado (novo IP LAN do host, por exemplo) produza chave
    nova em vez de servir URL velha apontando para um host inalcançável."""
    return settings.r2_public_endpoint_url or settings.r2_endpoint_url


async def presigned_image_url(
    key: str,
    *,
    storage: ObjectStorage,
    redis: aioredis.Redis,
) -> str:
    """Transforma uma chave de objeto numa URL GET presignada, memoizada no
    Redis para que a mesma chave devolva a MESMA URL dentro da janela.

    A memoização não é otimização de custo de assinatura — é o que mantém o
    cache de imagem do app funcionando. Sem ela, cada listagem devolveria uma
    URL diferente para a mesma foto, e o Flutter rebaixaria o próprio cache a
    cada scroll.

    Chave vazia devolve string vazia: produto sem imagem não vira URL.
    """
    if not key:
        return ""
    cache_key = f"presign:{_public_endpoint()}:{key}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return cached
    url = await storage.generate_presigned_get(key, expires_in=settings.media_presign_ttl_seconds)
    await redis.set(cache_key, url, ex=settings.media_presign_cache_ttl_seconds)
    return url


async def presign_cart(cart: CartOut, *, storage: ObjectStorage, redis: aioredis.Redis) -> CartOut:
    """Presina a `image_url` de cada item do carrinho.

    Movido de `app/routers/carrinho.py::_presign_cart` (task C7): a task C6
    já tinha escrito o mesmo loop pela segunda vez em
    `app/routers/pedidos.py::_order_out` (que opera sobre `OrderOut`, forma
    diferente — não mexido, unificar os dois seria abstração prematura de
    verdade). A rota de recompra desta task escreveria o loop pela
    TERCEIRA vez; em vez disso, `carrinho.py` e `pedidos.py` importam esta
    função pública."""
    for item in cart.items:
        item.image_url = await presigned_image_url(item.image_url, storage=storage, redis=redis)
    return cart
