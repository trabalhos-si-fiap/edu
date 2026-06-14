import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.auth.security import DUMMY_PASSWORD_HASH, verify_password


async def authenticate_admin(session: AsyncSession, email: str, password: str) -> User | None:
    """Valida credenciais de login no painel admin.

    Retorna o usuário apenas quando e-mail/senha conferem E o usuário é
    admin ativo. Quando o e-mail não existe ainda executa verify_password
    contra DUMMY_PASSWORD_HASH para manter o tempo de resposta constante
    (evita enumeração de usuários).
    """
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()

    expected_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_ok = verify_password(password, expected_hash)

    if user is None or not password_ok or not user.is_admin or not user.is_active:
        return None
    return user


async def load_admin(session: AsyncSession, user_id: str | None) -> User | None:
    """Recarrega o admin a partir do id guardado na sessão e revalida acesso.

    Chamado a cada request: se o usuário foi rebaixado/desativado depois do
    login, perde o acesso imediatamente.
    """
    if not isinstance(user_id, str):
        return None
    try:
        parsed = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None

    user = await session.get(User, parsed)
    if user is None or not user.is_admin or not user.is_active:
        return None
    return user
