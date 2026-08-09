from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.events.publisher import close_publisher, init_publisher
from app.routers import (
    admin,
    carrinho,
    entrega,
    ocorrencias,
    pagamento,
    pedidos,
    produtos,
    rastreio,
    separacao,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_publisher()
    yield
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
app.include_router(ocorrencias.router)


@app.get("/health")
def health():
    return {"status": "ok"}
