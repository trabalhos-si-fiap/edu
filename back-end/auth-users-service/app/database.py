from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
# `async_sessionmaker` é a fábrica tipada do SQLAlchemy 2.x. O
# `sessionmaker(..., class_=AsyncSession)` que estava aqui é a forma da 1.4:
# funciona em runtime, mas não sobrevive a checagem estática. O que foi de
# fato medido está no ledger (`progress.md:493-499`), com mypy 2.3.0 e
# pyright 1.1.411 contra o SQLAlchemy 2.0.51 deste worktree: os DOIS
# acusam erro de overload, e o pyright ainda resolve a chamada para
# `sessionmaker[Session]` — o tipo ERRADO (a sessão síncrona), não um tipo
# ausente. Os conftests já usavam a forma nova — só `app/database.py`
# ficou para trás.
#
# Ressalva, medida nesta rodada: nenhum type checker roda nesta repo
# (`grep -rn "mypy\|pyright" Makefile back-end/*/pyproject.toml
# back-end/packages/*/pyproject.toml` não devolve nada), então o ganho vale
# para IDE e para um CI futuro, não para a suíte de hoje.
async_session = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with async_session() as session:
        yield session
