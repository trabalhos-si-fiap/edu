from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.events.consumer import close_consumer, start_consumer
from app.routers import notificacoes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_consumer()
    yield
    await close_consumer()


app = FastAPI(title="Notification Service", lifespan=lifespan)

app.include_router(notificacoes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
