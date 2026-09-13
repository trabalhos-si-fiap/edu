import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.events.publisher import close_publisher, init_publisher
from app.routers import (
    admin,
    carregamentos,
    carrinho,
    entrega,
    ocorrencias,
    pagamento,
    parceiros,
    pedidos,
    produtos,
    rastreio,
    separacao,
    transportadoras,
)
from app.scheduler import start_scheduler, stop_scheduler
from app.services.embeddings import precarregar_modelo


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_publisher()
    start_scheduler()
    if settings.precarregar_embeddings:
        # Referência guardada em `app.state`: uma task sem referência pode ser
        # coletada pelo GC antes de terminar.
        app.state.precarga_embeddings = asyncio.create_task(precarregar_modelo())
    yield
    stop_scheduler()
    await close_publisher()


app = FastAPI(title="Commerce Service", lifespan=lifespan)

app.include_router(produtos.router)
app.include_router(carrinho.router)
app.include_router(pagamento.router)
app.include_router(pedidos.router)
app.include_router(rastreio.router)
app.include_router(separacao.router)
app.include_router(entrega.router)
app.include_router(admin.router)
app.include_router(parceiros.router)
app.include_router(ocorrencias.router)
app.include_router(transportadoras.router)
app.include_router(carregamentos.router)


@app.get("/health")
def health():
    return {"status": "ok"}
