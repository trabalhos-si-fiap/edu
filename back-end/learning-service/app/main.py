import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.events.consumer import close_consumer, start_consumer
from app.events.publisher import close_publisher, init_publisher
from app.routers import diagnostico, materias, onboarding, perfil, recomendacao, revisao, roadmap
from app.scheduler import start_scheduler, stop_scheduler
from app.services.embeddings import precarregar_modelo


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_publisher()
    await start_consumer()
    start_scheduler()
    if settings.precarregar_embeddings:
        # Referência guardada em `app.state`: uma task sem referência pode ser
        # coletada pelo GC antes de terminar.
        app.state.precarga_embeddings = asyncio.create_task(precarregar_modelo())
    yield
    stop_scheduler()
    await close_consumer()
    await close_publisher()


app = FastAPI(title="Learning Service", lifespan=lifespan)

app.include_router(materias.router)
app.include_router(diagnostico.router)
app.include_router(recomendacao.router)
app.include_router(revisao.router)
app.include_router(onboarding.router)
app.include_router(roadmap.router)
app.include_router(perfil.router)


@app.get("/health")
def health():
    return {"status": "ok"}
