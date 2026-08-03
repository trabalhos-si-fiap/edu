from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.events.publisher import close_publisher, init_publisher
from app.routers import addresses, auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_publisher()
    yield
    await close_publisher()


app = FastAPI(title="Auth + Users Service", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(addresses.router)


@app.get("/health")
def health():
    return {"status": "ok"}
