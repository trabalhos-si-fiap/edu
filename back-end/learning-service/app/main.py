from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.events.consumer import close_consumer, start_consumer
from app.events.publisher import close_publisher, init_publisher
from app.routers import diagnostico, materias, recomendacao, revisao
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_publisher()
    await start_consumer()
    start_scheduler()
    yield
    stop_scheduler()
    await close_consumer()
    await close_publisher()


app = FastAPI(title="Learning Service", lifespan=lifespan)

app.include_router(materias.router)
app.include_router(diagnostico.router)
app.include_router(recomendacao.router)
app.include_router(revisao.router)


@app.get("/health")
def health():
    return {"status": "ok"}
