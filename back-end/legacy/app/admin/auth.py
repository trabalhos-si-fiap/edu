import uuid

from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from app.core.database import SessionLocal
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


class AdminAuth(AuthenticationBackend):
    """Backend de autenticação do SQLAdmin sobre auth_users + is_admin.

    session_factory é injetável para testes; em produção usa o SessionLocal
    padrão da aplicação.
    """

    def __init__(
        self,
        secret_key: str,
        session_factory: async_sessionmaker | None = None,
    ) -> None:
        super().__init__(secret_key)
        self._session_factory = session_factory or SessionLocal

    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = str(form.get("username", ""))
        password = str(form.get("password", ""))

        async with self._session_factory() as session:
            user = await authenticate_admin(session, email, password)

        if user is None:
            return False
        request.session["user_id"] = str(user.id)
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        async with self._session_factory() as session:
            user = await load_admin(session, user_id)
        if user is None:
            request.session.clear()
            return False
        return True
