from fastapi import FastAPI

from app.bff.router import router as bff_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.modules.addresses.routes import router as addresses_router
from app.modules.auth.routes import router as auth_router
from app.modules.cart.routes import router as cart_router
from app.modules.notifications.routes import router as notifications_router
from app.modules.orders.routes import router as orders_router
from app.modules.payment_methods.routes import router as payment_methods_router
from app.modules.products.routes import router as products_router
from app.modules.support.routes import router as support_router
from app.modules.tracking.routes import router as tracking_router

configure_logging()

app = FastAPI(title=settings.APP_NAME)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Module routers go here. Each app.modules.<name> owns its routes/models/tasks
# and MUST NOT import from other modules — this is what keeps extraction into
# a standalone microservice cheap.
#
# Everything is mounted under /api to stay faithful to the original client
# contract (the Kotlin app used base `/api/`). `/health` stays at the root so
# infra probes don't depend on the API surface.
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(addresses_router, prefix=settings.API_PREFIX)
app.include_router(products_router, prefix=settings.API_PREFIX)
app.include_router(cart_router, prefix=settings.API_PREFIX)
app.include_router(orders_router, prefix=settings.API_PREFIX)
app.include_router(tracking_router, prefix=settings.API_PREFIX)
app.include_router(payment_methods_router, prefix=settings.API_PREFIX)
app.include_router(notifications_router, prefix=settings.API_PREFIX)
app.include_router(support_router, prefix=settings.API_PREFIX)
app.include_router(bff_router, prefix=settings.API_PREFIX)
