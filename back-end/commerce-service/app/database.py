from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
# `async_sessionmaker` é a fábrica tipada do SQLAlchemy 2.x. O
# `sessionmaker(..., class_=AsyncSession)` que estava aqui é a forma da 1.4:
# funciona, mas devolve `sessionmaker` sem parâmetro de tipo, então nada
# checa que `async_session()` produz uma `AsyncSession`. Os conftests já
# usavam a forma nova — só `app/database.py` ficou para trás.
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        yield session
