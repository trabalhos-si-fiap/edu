from fastapi import FastAPI

from app.bff.router import router as bff_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.APP_NAME)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Module routers go here. Each app.modules.<name> owns its routes/models/tasks
# and MUST NOT import from other modules — this is what keeps extraction into
# a standalone microservice cheap.
app.include_router(bff_router)
