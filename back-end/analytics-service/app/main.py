from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.events.consumer import close_consumer, start_consumer
from app.routers import analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_consumer()
    yield
    await close_consumer()


app = FastAPI(title="Analytics Service", lifespan=lifespan)

app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
