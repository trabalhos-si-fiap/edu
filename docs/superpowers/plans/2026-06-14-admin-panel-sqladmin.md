# Painel Admin Web (SQLAdmin) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um painel administrativo web (estilo Django admin) ao backend FastAPI para gerenciar (CRUD completo) e visualizar todos os modelos da aplicação, protegido por login que reusa `auth_users` + `is_admin`.

**Architecture:** Novo pacote de agregação `app/admin/` (mesmo status do `bff/`, pode importar models de todos os módulos). Usa a biblioteca **SQLAdmin** montada no app FastAPI existente em `/admin`, reaproveitando o `AsyncEngine` de `app/core/database.py`. A lógica de autenticação sensível vive em funções puras testáveis (`authenticate_admin`, `load_admin`); a classe `AdminAuth` é só o adaptador para o `AuthenticationBackend` do SQLAdmin.

**Tech Stack:** Python 3.12, FastAPI/Starlette, SQLAlchemy 2.0 async, SQLAdmin 0.27.2, WTForms, bcrypt, pytest (asyncio).

**Spec:** `docs/superpowers/specs/2026-06-14-admin-panel-sqladmin-design.md`

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `back-end/app/admin/__init__.py` | Marca o pacote. Vazio. |
| `back-end/app/admin/auth.py` | Lógica de auth: `authenticate_admin`, `load_admin` (puras) + `AdminAuth(AuthenticationBackend)`. |
| `back-end/app/admin/views.py` | Uma `ModelView` por modelo (~12), com colunas/busca/ordenação explícitas e o hook de senha do `UserAdmin`. |
| `back-end/app/admin/setup.py` | `setup_admin(app, ...)`: cria o `Admin`, registra todas as views. |
| `back-end/app/main.py` | (Modificar) chamar `setup_admin(app)`. |
| `back-end/tests/admin/__init__.py` | Pacote de testes. |
| `back-end/tests/admin/conftest.py` | Fixtures: usuário admin, usuário comum, factory de `Request` fake. |
| `back-end/tests/admin/test_auth_core.py` | Testes de `authenticate_admin` / `load_admin`. |
| `back-end/tests/admin/test_admin_backend.py` | Testes da classe `AdminAuth`. |
| `back-end/tests/admin/test_views.py` | Testes de configuração das views (campos sensíveis ocultos, hook de senha). |
| `back-end/tests/admin/test_setup.py` | Views registradas + redirect de login. |

> Todos os comandos `pytest`/`uv` rodam a partir de `back-end/`. Caminhos de arquivo no plano são relativos à raiz do repositório.

---

## Task 1: Adicionar dependência sqladmin

**Files:**
- Modify: `back-end/pyproject.toml`
- Modify: `back-end/uv.lock`

- [ ] **Step 1: Adicionar a dependência**

Run (a partir de `back-end/`):
```bash
uv add sqladmin
```
Isso adiciona `sqladmin>=0.27.2` em `[project].dependencies` e atualiza o lock (puxa `jinja2` e `wtforms` como transitivas). Se já estiver presente, o comando é idempotente.

- [ ] **Step 2: Confirmar import**

Run:
```bash
uv run python -c "import sqladmin; print(sqladmin.__version__)"
```
Expected: imprime `0.27.2` (ou superior), sem erro.

- [ ] **Step 3: Commit**

```bash
git add back-end/pyproject.toml back-end/uv.lock
git commit -m "feat(admin): add sqladmin dependency"
```

---

## Task 2: Pacote admin + lógica de autenticação pura

Funções sem dependência de SQLAdmin, fáceis de testar com `db_session`. `authenticate_admin` valida credenciais no login; `load_admin` revalida o usuário a cada request.

**Files:**
- Create: `back-end/app/admin/__init__.py`
- Create: `back-end/app/admin/auth.py`
- Create: `back-end/tests/admin/__init__.py`
- Create: `back-end/tests/admin/conftest.py`
- Test: `back-end/tests/admin/test_auth_core.py`

- [ ] **Step 1: Criar os pacotes vazios**

Criar `back-end/app/admin/__init__.py` vazio e `back-end/tests/admin/__init__.py` vazio.

- [ ] **Step 2: Criar fixtures de teste**

Criar `back-end/tests/admin/conftest.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.auth.security import hash_password


async def _make_user(
    session: AsyncSession,
    *,
    email: str,
    is_admin: bool,
    is_active: bool = True,
    password: str = "Secret!1",
) -> User:
    user = User(
        name="Admin User",
        email=email,
        phone="11999998888",
        birth_date=__import__("datetime").date(1995, 6, 15),
        education_level="Vestibulando",
        password_hash=hash_password(password),
        is_active=is_active,
        is_verified=True,
        is_admin=is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="admin@example.com", is_admin=True)


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    return await _make_user(db_session, email="user@example.com", is_admin=False)


@pytest.fixture
async def inactive_admin(db_session: AsyncSession) -> User:
    return await _make_user(
        db_session, email="ghost@example.com", is_admin=True, is_active=False
    )
```

- [ ] **Step 3: Escrever os testes que falham**

Criar `back-end/tests/admin/test_auth_core.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth import authenticate_admin, load_admin
from app.modules.auth.models import User


async def test_authenticate_admin_success(db_session: AsyncSession, admin_user: User):
    result = await authenticate_admin(db_session, "admin@example.com", "Secret!1")
    assert result is not None
    assert result.id == admin_user.id


async def test_authenticate_admin_wrong_password(db_session: AsyncSession, admin_user: User):
    assert await authenticate_admin(db_session, "admin@example.com", "nope") is None


async def test_authenticate_admin_non_admin_rejected(
    db_session: AsyncSession, regular_user: User
):
    assert await authenticate_admin(db_session, "user@example.com", "Secret!1") is None


async def test_authenticate_admin_inactive_rejected(
    db_session: AsyncSession, inactive_admin: User
):
    assert await authenticate_admin(db_session, "ghost@example.com", "Secret!1") is None


async def test_authenticate_admin_unknown_email(db_session: AsyncSession):
    # Caminho do DUMMY_PASSWORD_HASH — não deve levantar exceção, retorna None.
    assert await authenticate_admin(db_session, "missing@example.com", "Secret!1") is None


async def test_load_admin_returns_active_admin(db_session: AsyncSession, admin_user: User):
    result = await load_admin(db_session, str(admin_user.id))
    assert result is not None
    assert result.id == admin_user.id


async def test_load_admin_rejects_non_admin(db_session: AsyncSession, regular_user: User):
    assert await load_admin(db_session, str(regular_user.id)) is None


async def test_load_admin_rejects_inactive(db_session: AsyncSession, inactive_admin: User):
    assert await load_admin(db_session, str(inactive_admin.id)) is None


async def test_load_admin_rejects_garbage_id(db_session: AsyncSession):
    assert await load_admin(db_session, "not-a-uuid") is None
    assert await load_admin(db_session, None) is None
```

- [ ] **Step 4: Rodar os testes e confirmar que falham**

Run:
```bash
uv run pytest tests/admin/test_auth_core.py -v
```
Expected: FAIL com `ModuleNotFoundError: No module named 'app.admin.auth'` (ou ImportError de `authenticate_admin`).

- [ ] **Step 5: Implementar a lógica de auth**

Criar `back-end/app/admin/auth.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.auth.security import DUMMY_PASSWORD_HASH, verify_password


async def authenticate_admin(
    session: AsyncSession, email: str, password: str
) -> User | None:
    """Valida credenciais de login no painel admin.

    Retorna o usuário apenas quando e-mail/senha conferem E o usuário é
    admin ativo. Quando o e-mail não existe ainda executa verify_password
    contra DUMMY_PASSWORD_HASH para manter o tempo de resposta constante
    (evita enumeração de usuários).
    """
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()

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
```

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run:
```bash
uv run pytest tests/admin/test_auth_core.py -v
```
Expected: PASS (9 testes).

- [ ] **Step 7: Commit**

```bash
git add back-end/app/admin/__init__.py back-end/app/admin/auth.py \
        back-end/tests/admin/__init__.py back-end/tests/admin/conftest.py \
        back-end/tests/admin/test_auth_core.py
git commit -m "feat(admin): add admin authentication core logic"
```

---

## Task 3: AdminAuth backend (adaptador SQLAdmin)

Adaptador fino que liga o `AuthenticationBackend` do SQLAdmin às funções puras da Task 2. Recebe um `session_factory` injetável para testes.

**Files:**
- Modify: `back-end/app/admin/auth.py`
- Test: `back-end/tests/admin/test_admin_backend.py`

- [ ] **Step 1: Adicionar factory de Request fake ao conftest**

Adicionar ao final de `back-end/tests/admin/conftest.py`:

```python
from urllib.parse import urlencode

from starlette.requests import Request


def make_request(*, form: dict | None = None, session: dict | None = None) -> Request:
    """Constrói um starlette.Request mínimo para testar o AdminAuth.

    `form` vira corpo application/x-www-form-urlencoded; `session` é o dict de
    sessão que o SessionMiddleware normalmente injeta.
    """
    scope = {
        "type": "http",
        "method": "POST" if form is not None else "GET",
        "headers": [],
        "session": session if session is not None else {},
    }
    if form is None:
        return Request(scope)

    body = urlencode(form).encode("utf-8")
    scope["headers"] = [(b"content-type", b"application/x-www-form-urlencoded")]

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `back-end/tests/admin/test_admin_backend.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.admin.auth import AdminAuth
from app.modules.auth.models import User
from tests.admin.conftest import make_request


def _backend(test_session_factory: async_sessionmaker[AsyncSession]) -> AdminAuth:
    return AdminAuth(secret_key="test-secret", session_factory=test_session_factory)


async def test_login_success_sets_session(
    test_session_factory: async_sessionmaker[AsyncSession], admin_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(form={"username": "admin@example.com", "password": "Secret!1"})

    assert await backend.login(request) is True
    assert request.session["user_id"] == str(admin_user.id)


async def test_login_wrong_password_returns_false(
    test_session_factory: async_sessionmaker[AsyncSession], admin_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(form={"username": "admin@example.com", "password": "wrong"})

    assert await backend.login(request) is False
    assert "user_id" not in request.session


async def test_login_non_admin_returns_false(
    test_session_factory: async_sessionmaker[AsyncSession], regular_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(form={"username": "user@example.com", "password": "Secret!1"})

    assert await backend.login(request) is False


async def test_logout_clears_session(
    test_session_factory: async_sessionmaker[AsyncSession],
):
    backend = _backend(test_session_factory)
    request = make_request(session={"user_id": "abc"})

    assert await backend.logout(request) is True
    assert "user_id" not in request.session


async def test_authenticate_valid_admin(
    test_session_factory: async_sessionmaker[AsyncSession], admin_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(session={"user_id": str(admin_user.id)})

    assert await backend.authenticate(request) is True


async def test_authenticate_no_session_returns_false(
    test_session_factory: async_sessionmaker[AsyncSession],
):
    backend = _backend(test_session_factory)
    request = make_request(session={})

    assert await backend.authenticate(request) is False


async def test_authenticate_demoted_user_clears_session(
    test_session_factory: async_sessionmaker[AsyncSession], regular_user: User
):
    backend = _backend(test_session_factory)
    request = make_request(session={"user_id": str(regular_user.id)})

    assert await backend.authenticate(request) is False
    assert "user_id" not in request.session
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run:
```bash
uv run pytest tests/admin/test_admin_backend.py -v
```
Expected: FAIL com `ImportError: cannot import name 'AdminAuth'`.

- [ ] **Step 4: Implementar a classe AdminAuth**

Adicionar ao topo de `back-end/app/admin/auth.py` (imports) e ao final (classe):

No bloco de imports, adicionar:
```python
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request

from app.core.database import SessionLocal
```

Ao final do arquivo, adicionar:
```python
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
```

> Nota: o formulário de login do SQLAdmin envia os campos como `username` e `password`. Aqui `username` carrega o e-mail.

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run:
```bash
uv run pytest tests/admin/test_admin_backend.py -v
```
Expected: PASS (7 testes).

- [ ] **Step 6: Commit**

```bash
git add back-end/app/admin/auth.py back-end/tests/admin/conftest.py \
        back-end/tests/admin/test_admin_backend.py
git commit -m "feat(admin): add AdminAuth authentication backend"
```

---

## Task 4: ModelViews dos modelos

Uma `ModelView` por modelo. Campos sensíveis nunca aparecem. O `UserAdmin` adiciona um campo virtual `password` e hasheia via `on_model_change`.

**Files:**
- Create: `back-end/app/admin/views.py`
- Test: `back-end/tests/admin/test_views.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `back-end/tests/admin/test_views.py`:

```python
import pytest

from app.admin import views
from app.modules.auth.models import User


def test_user_admin_hides_password_hash():
    assert "password_hash" not in views.UserAdmin.column_list
    assert "password_hash" in views.UserAdmin.form_excluded_columns


def test_device_token_admin_hides_token_value():
    assert "token" not in views.DeviceTokenAdmin.column_list


async def test_user_form_has_virtual_password_field():
    form_type = await views.UserAdmin().scaffold_form()
    assert "password" in form_type()._fields


async def test_on_model_change_hashes_password_on_create():
    data = {"email": "new@example.com", "password": "PlainPass!1"}
    await views.UserAdmin().on_model_change(data, User(), is_created=True, request=None)
    assert "password" not in data
    assert data["password_hash"] != "PlainPass!1"
    assert data["password_hash"].startswith("$2")  # bcrypt prefix


async def test_on_model_change_blank_password_on_edit_keeps_hash():
    data = {"email": "x@example.com", "password": ""}
    await views.UserAdmin().on_model_change(data, User(), is_created=False, request=None)
    assert "password" not in data
    assert "password_hash" not in data


async def test_on_model_change_blank_password_on_create_raises():
    data = {"email": "x@example.com", "password": ""}
    with pytest.raises(ValueError):
        await views.UserAdmin().on_model_change(
            data, User(), is_created=True, request=None
        )
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run:
```bash
uv run pytest tests/admin/test_views.py -v
```
Expected: FAIL com `ImportError`/`AttributeError` (sem `views.UserAdmin`).

- [ ] **Step 3: Implementar as views**

Criar `back-end/app/admin/views.py`:

```python
import wtforms
from sqladmin import ModelView

from app.modules.addresses.models import Address
from app.modules.auth.models import User
from app.modules.auth.security import hash_password
from app.modules.cart.models import Cart, CartItem
from app.modules.notifications.models import DeviceToken, Notification
from app.modules.orders.models import Order, OrderItem
from app.modules.payment_methods.models import PaymentMethod
from app.modules.products.models import Product, Review
from app.modules.support.models import SupportMessage


class UserAdmin(ModelView, model=User):
    name = "Usuário"
    name_plural = "Usuários"
    icon = "fa-solid fa-user"
    column_list = [
        "id", "name", "email", "phone", "education_level",
        "is_active", "is_verified", "is_admin", "created_at",
    ]
    column_searchable_list = ["name", "email"]
    column_sortable_list = ["name", "email", "created_at"]
    # password_hash NUNCA é renderizado nem editável diretamente.
    form_excluded_columns = ["password_hash", "created_at", "updated_at"]

    async def scaffold_form(self, rules=None):
        form_class = await super().scaffold_form(rules)
        form_class.password = wtforms.PasswordField(
            "Senha (em branco mantém a atual na edição)"
        )
        return form_class

    async def on_model_change(self, data, model, is_created, request) -> None:
        password = (data.pop("password", "") or "").strip()
        if password:
            data["password_hash"] = hash_password(password)
        elif is_created:
            raise ValueError("Senha é obrigatória ao criar um usuário.")


class AddressAdmin(ModelView, model=Address):
    name = "Endereço"
    name_plural = "Endereços"
    column_list = [
        "id", "user_id", "label", "city", "state", "zip_code", "is_favorite",
    ]
    column_searchable_list = ["city", "zip_code"]
    column_sortable_list = ["city", "state", "created_at"]


class ProductAdmin(ModelView, model=Product):
    name = "Produto"
    name_plural = "Produtos"
    column_list = [
        "id", "name", "type", "subtype", "price",
        "rating_avg", "rating_count", "created_at",
    ]
    column_searchable_list = ["name", "type"]
    column_sortable_list = ["name", "price", "rating_avg", "created_at"]


class ReviewAdmin(ModelView, model=Review):
    name = "Avaliação"
    name_plural = "Avaliações"
    column_list = ["id", "product_id", "author", "rating", "created_at"]
    column_searchable_list = ["author"]
    column_sortable_list = ["rating", "created_at"]


class OrderAdmin(ModelView, model=Order):
    name = "Pedido"
    name_plural = "Pedidos"
    column_list = ["id", "user_id", "total", "status", "payment_method", "created_at"]
    column_searchable_list = ["status"]
    column_sortable_list = ["total", "status", "created_at"]


class OrderItemAdmin(ModelView, model=OrderItem):
    name = "Item de pedido"
    name_plural = "Itens de pedido"
    column_list = ["id", "order_id", "product_name", "unit_price", "quantity"]
    column_sortable_list = ["unit_price", "quantity"]


class CartAdmin(ModelView, model=Cart):
    name = "Carrinho"
    name_plural = "Carrinhos"
    column_list = ["id", "user_id", "created_at", "updated_at"]
    column_sortable_list = ["created_at", "updated_at"]


class CartItemAdmin(ModelView, model=CartItem):
    name = "Item de carrinho"
    name_plural = "Itens de carrinho"
    column_list = ["id", "cart_id", "product_id", "quantity", "created_at"]
    column_sortable_list = ["quantity", "created_at"]


class PaymentMethodAdmin(ModelView, model=PaymentMethod):
    name = "Forma de pagamento"
    name_plural = "Formas de pagamento"
    column_list = [
        "id", "user_id", "type", "is_default",
        "card_brand", "card_last4", "created_at",
    ]
    column_sortable_list = ["type", "created_at"]


class DeviceTokenAdmin(ModelView, model=DeviceToken):
    name = "Token de dispositivo"
    name_plural = "Tokens de dispositivo"
    # O valor do token é sensível — exibimos só metadados, nunca o token.
    column_list = ["id", "user_id", "platform", "created_at", "updated_at"]
    column_sortable_list = ["platform", "created_at"]


class NotificationAdmin(ModelView, model=Notification):
    name = "Notificação"
    name_plural = "Notificações"
    column_list = ["id", "user_id", "title", "read_at", "created_at"]
    column_searchable_list = ["title"]
    column_sortable_list = ["created_at", "read_at"]


class SupportMessageAdmin(ModelView, model=SupportMessage):
    name = "Mensagem de suporte"
    name_plural = "Mensagens de suporte"
    column_list = ["id", "user_id", "sender", "body", "created_at"]
    column_searchable_list = ["body"]
    column_sortable_list = ["created_at"]


ALL_VIEWS = [
    UserAdmin,
    AddressAdmin,
    ProductAdmin,
    ReviewAdmin,
    OrderAdmin,
    OrderItemAdmin,
    CartAdmin,
    CartItemAdmin,
    PaymentMethodAdmin,
    DeviceTokenAdmin,
    NotificationAdmin,
    SupportMessageAdmin,
]
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run:
```bash
uv run pytest tests/admin/test_views.py -v
```
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add back-end/app/admin/views.py back-end/tests/admin/test_views.py
git commit -m "feat(admin): add model views for all domain models"
```

---

## Task 5: Setup do Admin + montagem no app

Junta tudo: `setup_admin` cria o `Admin` com o `AdminAuth` e registra as views; `main.py` chama na inicialização.

**Files:**
- Create: `back-end/app/admin/setup.py`
- Modify: `back-end/app/main.py`
- Test: `back-end/tests/admin/test_setup.py`

- [ ] **Step 1: Escrever os testes que falham**

Criar `back-end/tests/admin/test_setup.py`:

```python
from starlette.applications import Starlette

from app.admin.setup import setup_admin
from app.admin.views import ALL_VIEWS


def test_setup_registers_all_views():
    app = Starlette()
    admin = setup_admin(app)
    registered = {type(view).model for view in admin.views}
    expected = {v.model for v in ALL_VIEWS}
    assert registered == expected
    assert len(admin.views) == len(ALL_VIEWS)


async def test_admin_redirects_to_login_when_unauthenticated(client):
    # client é o AsyncClient da app real (tests/conftest.py), com admin montado.
    response = await client.get("/admin/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/admin/login" in response.headers["location"]
```

> O fixture `client` vem de `back-end/tests/conftest.py` e expõe a app real via `ASGITransport`. Como `main.py` chama `setup_admin(app)` no import, o painel já está montado.

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run:
```bash
uv run pytest tests/admin/test_setup.py -v
```
Expected: FAIL com `ModuleNotFoundError: No module named 'app.admin.setup'`.

- [ ] **Step 3: Implementar setup_admin**

Criar `back-end/app/admin/setup.py`:

```python
from sqladmin import Admin
from starlette.applications import Starlette

from app.admin.auth import AdminAuth
from app.admin.views import ALL_VIEWS
from app.core.config import settings
from app.core.database import engine


def setup_admin(app: Starlette) -> Admin:
    """Monta o painel SQLAdmin em /admin e registra todas as ModelViews."""
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(
        app,
        engine,
        title=f"{settings.APP_NAME} Admin",
        authentication_backend=authentication_backend,
    )
    for view in ALL_VIEWS:
        admin.add_view(view)
    return admin
```

- [ ] **Step 4: Montar no main.py**

Em `back-end/app/main.py`, após a criação do `app` e do endpoint `/health` (antes ou depois dos `include_router`), adicionar o import no topo junto aos demais:
```python
from app.admin.setup import setup_admin
```
E após a última linha `app.include_router(bff_router, prefix=settings.API_PREFIX)` adicionar:
```python

# Painel administrativo web (SQLAdmin) montado em /admin. Camada de agregação —
# pode importar models de todos os módulos, igual ao BFF.
setup_admin(app)
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run:
```bash
uv run pytest tests/admin/test_setup.py -v
```
Expected: PASS (2 testes).

- [ ] **Step 6: Rodar a suíte completa de admin + lint**

Run:
```bash
uv run pytest tests/admin -v
uv run ruff check app/admin tests/admin
uv run ruff format app/admin tests/admin
```
Expected: todos os testes PASS; ruff sem erros (rodar format se reportar).

- [ ] **Step 7: Commit**

```bash
git add back-end/app/admin/setup.py back-end/app/main.py back-end/tests/admin/test_setup.py
git commit -m "feat(admin): mount SQLAdmin panel at /admin"
```

---

## Task 6: Verificação manual e documentação

**Files:**
- Modify: `CLAUDE.md` (tabela de documentação) — opcional, ver Step 3
- Create: `docs/back-end/admin-panel.md`

- [ ] **Step 1: Subir o app e verificar o login**

Pré-requisito: ter um usuário com `is_admin=True` no banco (promover via `psql`/seed:
`UPDATE auth_users SET is_admin = true WHERE email = '<seu-email>';`).

Run:
```bash
docker compose up -d
```
Acessar `http://localhost:8000/admin` no navegador. Esperado: redireciona para a tela de login do SQLAdmin. Logar com e-mail/senha do admin → ver a lista de modelos no menu lateral. Confirmar que a view de Usuários **não** mostra a coluna de senha e que o form tem o campo "Senha".

- [ ] **Step 2: Confirmar que a suíte inteira do backend continua verde**

Run:
```bash
uv run pytest
```
Expected: todos os testes PASS (admin + módulos existentes).

- [ ] **Step 3: Documentar o módulo**

Criar `docs/back-end/admin-panel.md` com: o que é, URL `/admin`, como criar um admin (`UPDATE auth_users SET is_admin = true ...`), quais modelos são gerenciáveis e a nota de segurança (senha hasheada via hook, token de device oculto). Adicionar uma linha na tabela de documentação do `CLAUDE.md` apontando para esse arquivo (linha do Backend).

- [ ] **Step 4: Commit**

```bash
git add docs/back-end/admin-panel.md CLAUDE.md
git commit -m "docs(admin): document the web admin panel"
```

---

## Self-Review notes

- **Cobertura do spec:** auth reusando `auth_users`+`is_admin` (Tasks 2–3), CRUD de todos os ~12 modelos (Task 4), `password_hash`/token nunca renderizados (Task 4), revalidação por request via `load_admin` (Task 2–3), montagem em `/admin` com `SECRET_KEY` (Task 5), testes em `tests/admin/` (Tasks 2–5). Todos cobertos.
- **Sem placeholders:** todo código está completo; nenhum "TODO"/"similar a".
- **Consistência de tipos:** `authenticate_admin`/`load_admin` definidas na Task 2 e usadas na Task 3 com as mesmas assinaturas; `ALL_VIEWS` definido na Task 4 e consumido nas Tasks 5. `AdminAuth(secret_key, session_factory)` consistente entre teste e implementação. Form do SQLAdmin usa campos `username`/`password` (documentado na Task 3).
- **Decisão de senha:** campo virtual `password` adicionado via `scaffold_form` (async, confirmado na lib 0.27.2) e hasheado em `on_model_change`; `password_hash` real fica em `form_excluded_columns`.
