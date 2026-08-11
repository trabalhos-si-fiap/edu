from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import Base, async_session, get_db  # noqa: F401 -- prova que o símbolo existe


def test_the_session_factory_is_the_modern_one():
    """`async_sessionmaker`, não `sessionmaker(..., class_=AsyncSession)`.

    Os cinco serviços que nasceram antes usam a forma legada da 1.4 (o bloco
    A os converteu). Este nasce já na forma da 2.x — não vale reintroduzir
    a dívida que acabou de ser paga.
    """
    assert isinstance(async_session, async_sessionmaker)


def test_base_is_declarative():
    assert hasattr(Base, "metadata")


async def test_get_db_yields_a_working_session(db_session: AsyncSession):
    resultado = await db_session.execute(text("SELECT 1"))
    assert resultado.scalar_one() == 1
