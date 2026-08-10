from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
# `async_sessionmaker`, a fábrica tipada da 2.x — não o
# `sessionmaker(..., class_=AsyncSession)` da 1.4 que os cinco serviços
# anteriores carregavam e que a fase 2A converteu.
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        yield session
