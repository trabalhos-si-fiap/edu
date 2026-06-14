# Password Reset via E-mail (OTP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir recuperação de senha por código OTP de 6 dígitos enviado por e-mail, com uma camada de adapter que desacopla o núcleo do provedor (Resend).

**Architecture:** Ports & Adapters para e-mail (`app/core/email/`): o domínio depende da porta `EmailSender`; `ConsoleEmailAdapter` (dev/test) e `ResendEmailAdapter` (produção) são implementações trocáveis via `EMAIL_BACKEND`. O fluxo de reset estende o módulo `auth`: OTP gerado e guardado como hash no Redis (TTL + limite de tentativas), enviado por task Celery; verificação constant-time e troca de senha.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), Redis (`redis.asyncio`), Celery, httpx, pytest. Spec: `docs/superpowers/specs/2026-06-14-password-reset-email-design.md`.

**Convenções do projeto a respeitar:** TDD (red→green→refactor), commits por unidade lógica (Conventional Commits, em inglês, imperativo), `loguru` nunca `print()`, `compare_secret` para comparar segredos, secrets nunca no código. Rodar testes com `uv run pytest` a partir de `back-end/`.

---

## File Structure

**Criar:**
- `back-end/app/core/email/__init__.py` — exporta `EmailMessage`, `EmailSender`, `EmailDeliveryError`, `get_email_sender`
- `back-end/app/core/email/base.py` — porta + DTO + exceção
- `back-end/app/core/email/console.py` — `ConsoleEmailAdapter`
- `back-end/app/core/email/resend.py` — `ResendEmailAdapter`
- `back-end/app/core/email/factory.py` — `get_email_sender()`
- `back-end/app/modules/auth/password_reset.py` — geração/hash do OTP + store no Redis
- `back-end/tests/core/email/__init__.py` — (vazio)
- `back-end/tests/core/email/test_base.py`
- `back-end/tests/core/email/test_console.py`
- `back-end/tests/core/email/test_resend.py`
- `back-end/tests/core/email/test_factory.py`
- `back-end/tests/modules/auth/test_password_reset_store.py`
- `back-end/tests/modules/auth/test_password_reset_flow.py`

**Modificar:**
- `back-end/app/core/config.py` — novas settings
- `back-end/app/modules/auth/rate_limit.py` — extrair helper + adicionar `check_password_reset_rate_limit`
- `back-end/app/modules/auth/schemas.py` — `PasswordResetRequestIn`, `PasswordResetConfirmIn`
- `back-end/app/modules/auth/exceptions.py` — `InvalidResetCode`
- `back-end/app/modules/auth/services.py` — `request_password_reset`, `confirm_password_reset`
- `back-end/app/modules/auth/tasks.py` — criar arquivo com a task de e-mail
- `back-end/app/modules/auth/routes.py` — dois endpoints
- `back-end/tests/core/__init__.py` — garantir que existe (criar se faltar)

> Todos os comandos `pytest` abaixo rodam a partir de `back-end/`.

---

## Task 1: Config settings

**Files:**
- Modify: `back-end/app/core/config.py`
- Test: `back-end/tests/core/test_config_email.py` (criar)

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/core/test_config_email.py`:

```python
from app.core.config import settings


def test_email_defaults_are_safe() -> None:
    assert settings.EMAIL_BACKEND == "console"
    assert settings.RESEND_API_KEY is None
    assert settings.EMAIL_FROM


def test_password_reset_defaults() -> None:
    assert settings.PASSWORD_RESET_CODE_TTL_SECONDS == 600
    assert settings.PASSWORD_RESET_MAX_ATTEMPTS == 5
    assert settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS == 5
    assert settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS == 900
    assert settings.EMAIL_SEND_TIME_LIMIT == 30
    assert settings.EMAIL_SEND_SOFT_TIME_LIMIT == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_config_email.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'EMAIL_BACKEND'`

- [ ] **Step 3: Add the settings**

Em `back-end/app/core/config.py`, dentro da classe `Settings`, logo após o bloco de `LOGIN_RATE_LIMIT_*` (linha ~34):

```python
    # E-mail provider (Ports & Adapters). "console" loga e não envia nada real
    # (dev/test); "resend" usa a API da Resend via RESEND_API_KEY. Trocar de
    # provedor = novo adapter + esta variável, sem tocar no domínio.
    EMAIL_BACKEND: str = "console"  # "console" | "resend"
    RESEND_API_KEY: str | None = None
    EMAIL_FROM: str = "Edu <no-reply@edu.app>"

    # Password reset OTP. Código efêmero guardado (hasheado) no Redis.
    PASSWORD_RESET_CODE_TTL_SECONDS: int = 600
    PASSWORD_RESET_MAX_ATTEMPTS: int = 5
    PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS: int = 5
    PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS: int = 900
    EMAIL_SEND_TIME_LIMIT: int = 30
    EMAIL_SEND_SOFT_TIME_LIMIT: int = 25
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_config_email.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py tests/core/test_config_email.py
git commit -m "feat(config): add email provider and password reset settings"
```

---

## Task 2: Email port (base)

**Files:**
- Create: `back-end/app/core/email/base.py`
- Create: `back-end/tests/core/email/__init__.py` (vazio), `back-end/tests/core/__init__.py` (se não existir)
- Test: `back-end/tests/core/email/test_base.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/core/email/test_base.py`:

```python
import dataclasses

from app.core.email.base import EmailDeliveryError, EmailMessage


def test_email_message_is_frozen_dataclass() -> None:
    msg = EmailMessage(to="a@b.com", subject="Hi", html="<p>hi</p>", text="hi")
    assert msg.to == "a@b.com"
    assert msg.subject == "Hi"
    assert dataclasses.is_dataclass(msg)
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        msg.to = "other@b.com"  # type: ignore[misc]


def test_email_delivery_error_is_exception() -> None:
    assert issubclass(EmailDeliveryError, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/email/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.email'`

- [ ] **Step 3: Create the module**

Criar `back-end/app/core/email/base.py`:

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    """Provider-neutral email payload. No provider-specific fields leak here."""

    to: str
    subject: str
    html: str
    text: str


class EmailSender(Protocol):
    """The port the application core depends on. Adapters implement it."""

    async def send(self, message: EmailMessage) -> None: ...


class EmailDeliveryError(Exception):
    """Raised when a provider rejects or fails to accept a message."""
```

Criar arquivos vazios: `back-end/tests/core/email/__init__.py`. Verificar/criar `back-end/tests/core/__init__.py` se ainda não existir.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/email/test_base.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/core/email/base.py tests/core/email/__init__.py tests/core/email/test_base.py
git add tests/core/__init__.py 2>/dev/null || true
git commit -m "feat(email): add EmailSender port, EmailMessage and EmailDeliveryError"
```

---

## Task 3: Console adapter

**Files:**
- Create: `back-end/app/core/email/console.py`
- Test: `back-end/tests/core/email/test_console.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/core/email/test_console.py`:

```python
from app.core.email.base import EmailMessage
from app.core.email.console import ConsoleEmailAdapter


async def test_console_adapter_logs_and_does_no_network(caplog) -> None:
    from loguru import logger

    sink: list[str] = []
    handler_id = logger.add(lambda m: sink.append(str(m)), level="INFO")
    try:
        adapter = ConsoleEmailAdapter()
        await adapter.send(
            EmailMessage(to="user@example.com", subject="Code", html="<p>123456</p>", text="123456")
        )
    finally:
        logger.remove(handler_id)

    joined = "\n".join(sink)
    assert "user@example.com" in joined
    assert "123456" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/email/test_console.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.email.console'`

- [ ] **Step 3: Implement the adapter**

Criar `back-end/app/core/email/console.py`:

```python
from loguru import logger

from app.core.email.base import EmailMessage


class ConsoleEmailAdapter:
    """Dev/test adapter: logs the message, never touches the network."""

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email[console] to={} subject={!r}\n{}",
            message.to,
            message.subject,
            message.text,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/email/test_console.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add app/core/email/console.py tests/core/email/test_console.py
git commit -m "feat(email): implement ConsoleEmailAdapter"
```

---

## Task 4: Resend adapter

**Files:**
- Create: `back-end/app/core/email/resend.py`
- Test: `back-end/tests/core/email/test_resend.py`

Usa `httpx.MockTransport` (built-in) para interceptar a chamada — sem dependência nova.

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/core/email/test_resend.py`:

```python
import httpx
import pytest

from app.core.email.base import EmailDeliveryError, EmailMessage
from app.core.email.resend import ResendEmailAdapter

_MSG = EmailMessage(to="user@example.com", subject="Code", html="<p>123456</p>", text="123456")


async def test_resend_posts_expected_payload_and_headers() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "email_123"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ResendEmailAdapter(api_key="re_test_key", sender="Edu <no-reply@edu.app>", client=client)

    await adapter.send(_MSG)
    await client.aclose()

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["auth"] == "Bearer re_test_key"
    body = captured["body"]
    assert body["from"] == "Edu <no-reply@edu.app>"
    assert body["to"] == ["user@example.com"]
    assert body["subject"] == "Code"
    assert body["html"] == "<p>123456</p>"
    assert body["text"] == "123456"


async def test_resend_raises_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"message": "invalid"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ResendEmailAdapter(api_key="re_test_key", sender="Edu <no-reply@edu.app>", client=client)

    with pytest.raises(EmailDeliveryError):
        await adapter.send(_MSG)
    await client.aclose()


def test_resend_requires_api_key() -> None:
    with pytest.raises(ValueError):
        ResendEmailAdapter(api_key=None, sender="Edu <no-reply@edu.app>")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/email/test_resend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.email.resend'`

- [ ] **Step 3: Implement the adapter**

Criar `back-end/app/core/email/resend.py`:

```python
import httpx

from app.core.email.base import EmailDeliveryError, EmailMessage


class ResendEmailAdapter:
    """Adapter for the Resend HTTP API (https://resend.com/docs)."""

    _ENDPOINT = "https://api.resend.com/emails"

    def __init__(
        self,
        api_key: str | None,
        sender: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("RESEND_API_KEY is required for the resend email backend")
        self._api_key = api_key
        self._sender = sender
        # Injectable client for tests (httpx.MockTransport); None => own client.
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        payload = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.post(self._ENDPOINT, json=payload, headers=headers)
        finally:
            if self._client is None:
                await client.aclose()

        if response.status_code >= 400:
            raise EmailDeliveryError(
                f"resend returned {response.status_code}: {response.text}"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/email/test_resend.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/core/email/resend.py tests/core/email/test_resend.py
git commit -m "feat(email): implement ResendEmailAdapter"
```

---

## Task 5: Email factory + package exports

**Files:**
- Create: `back-end/app/core/email/factory.py`, `back-end/app/core/email/__init__.py`
- Test: `back-end/tests/core/email/test_factory.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/core/email/test_factory.py`:

```python
import pytest

from app.core.email.console import ConsoleEmailAdapter
from app.core.email.factory import get_email_sender
from app.core.email.resend import ResendEmailAdapter


def test_factory_returns_console_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "EMAIL_BACKEND", "console")
    assert isinstance(get_email_sender(), ConsoleEmailAdapter)


def test_factory_returns_resend_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "EMAIL_BACKEND", "resend")
    monkeypatch.setattr(config.settings, "RESEND_API_KEY", "re_test_key")
    assert isinstance(get_email_sender(), ResendEmailAdapter)


def test_package_reexports() -> None:
    from app.core.email import EmailMessage, EmailSender, get_email_sender  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/email/test_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.email.factory'`

- [ ] **Step 3: Implement factory and exports**

Criar `back-end/app/core/email/factory.py`:

```python
from app.core.config import settings
from app.core.email.base import EmailSender
from app.core.email.console import ConsoleEmailAdapter
from app.core.email.resend import ResendEmailAdapter


def get_email_sender() -> EmailSender:
    """Resolve the configured email adapter. Only place that reads settings."""
    if settings.EMAIL_BACKEND == "resend":
        return ResendEmailAdapter(api_key=settings.RESEND_API_KEY, sender=settings.EMAIL_FROM)
    return ConsoleEmailAdapter()
```

Criar `back-end/app/core/email/__init__.py`:

```python
from app.core.email.base import EmailDeliveryError, EmailMessage, EmailSender
from app.core.email.factory import get_email_sender

__all__ = [
    "EmailDeliveryError",
    "EmailMessage",
    "EmailSender",
    "get_email_sender",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/email/ -v`
Expected: PASS (todos os testes de email/ verdes)

- [ ] **Step 5: Commit**

```bash
git add app/core/email/factory.py app/core/email/__init__.py tests/core/email/test_factory.py
git commit -m "feat(email): add get_email_sender factory and package exports"
```

---

## Task 6: Password reset store (OTP gen/hash + Redis)

**Files:**
- Create: `back-end/app/modules/auth/password_reset.py`
- Test: `back-end/tests/modules/auth/test_password_reset_store.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/modules/auth/test_password_reset_store.py`:

```python
import uuid

import redis.asyncio as aioredis

from app.modules.auth import password_reset as pr


def test_generate_otp_is_six_digits() -> None:
    for _ in range(50):
        code = pr.generate_otp()
        assert len(code) == 6
        assert code.isdigit()


def test_hash_otp_is_deterministic_and_not_plaintext() -> None:
    h1 = pr.hash_otp("123456")
    h2 = pr.hash_otp("123456")
    assert h1 == h2
    assert h1 != "123456"


async def test_store_then_verify_succeeds(redis_client: aioredis.Redis) -> None:
    user_id = uuid.uuid4()
    await pr.store_reset_code(redis_client, user_id, "123456")
    assert await pr.verify_reset_code(redis_client, user_id, "123456") is True


async def test_verify_wrong_code_fails(redis_client: aioredis.Redis) -> None:
    user_id = uuid.uuid4()
    await pr.store_reset_code(redis_client, user_id, "123456")
    assert await pr.verify_reset_code(redis_client, user_id, "000000") is False


async def test_verify_without_stored_code_fails(redis_client: aioredis.Redis) -> None:
    assert await pr.verify_reset_code(redis_client, uuid.uuid4(), "123456") is False


async def test_locks_out_after_max_attempts(redis_client: aioredis.Redis) -> None:
    from app.core.config import settings

    user_id = uuid.uuid4()
    await pr.store_reset_code(redis_client, user_id, "123456")
    for _ in range(settings.PASSWORD_RESET_MAX_ATTEMPTS):
        assert await pr.verify_reset_code(redis_client, user_id, "999999") is False
    # Correct code is now rejected because attempts hit the cap.
    assert await pr.verify_reset_code(redis_client, user_id, "123456") is False


async def test_clear_removes_code_and_attempts(redis_client: aioredis.Redis) -> None:
    user_id = uuid.uuid4()
    await pr.store_reset_code(redis_client, user_id, "123456")
    await pr.clear_reset_code(redis_client, user_id)
    assert await pr.verify_reset_code(redis_client, user_id, "123456") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/modules/auth/test_password_reset_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.auth.password_reset'`

- [ ] **Step 3: Implement the store**

Criar `back-end/app/modules/auth/password_reset.py`:

```python
import hmac
import secrets
import uuid
from hashlib import sha256

import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.auth.security import compare_secret


def _code_key(user_id: uuid.UUID) -> str:
    return f"pwreset:code:{user_id}"


def _attempts_key(user_id: uuid.UUID) -> str:
    return f"pwreset:attempts:{user_id}"


def generate_otp() -> str:
    """Cryptographically-random 6-digit code, zero-padded (uniform 000000-999999)."""
    return f"{secrets.randbelow(10**6):06d}"


def hash_otp(code: str) -> str:
    """HMAC-SHA256 of the code under SECRET_KEY. The plaintext OTP is never stored."""
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), code.encode("utf-8"), sha256).hexdigest()


async def store_reset_code(redis: aioredis.Redis, user_id: uuid.UUID, code: str) -> None:
    """Store the hashed OTP with TTL and reset the attempt counter. One active code per user."""
    await redis.set(_code_key(user_id), hash_otp(code), ex=settings.PASSWORD_RESET_CODE_TTL_SECONDS)
    await redis.delete(_attempts_key(user_id))


async def _register_attempt(redis: aioredis.Redis, user_id: uuid.UUID) -> None:
    key = _attempts_key(user_id)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, settings.PASSWORD_RESET_CODE_TTL_SECONDS, nx=True)
        await pipe.execute()


async def verify_reset_code(redis: aioredis.Redis, user_id: uuid.UUID, code: str) -> bool:
    """Constant-time check of the OTP. Counts failed attempts and locks out after the cap.

    Does NOT consume the code on success — the caller clears it after the password
    is updated, so a failed downstream step doesn't burn the user's only code.
    """
    attempts = await redis.get(_attempts_key(user_id))
    if attempts is not None and int(attempts) >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
        return False

    stored = await redis.get(_code_key(user_id))
    if stored is None:
        await _register_attempt(redis, user_id)
        return False

    if not compare_secret(stored, hash_otp(code)):
        await _register_attempt(redis, user_id)
        return False

    return True


async def clear_reset_code(redis: aioredis.Redis, user_id: uuid.UUID) -> None:
    await redis.delete(_code_key(user_id), _attempts_key(user_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/modules/auth/test_password_reset_store.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add app/modules/auth/password_reset.py tests/modules/auth/test_password_reset_store.py
git commit -m "feat(auth): add password reset OTP store with hashing and attempt lockout"
```

---

## Task 7: Password reset request rate limit

**Files:**
- Modify: `back-end/app/modules/auth/rate_limit.py`
- Test: `back-end/tests/modules/auth/test_password_reset_rate_limit.py`

Extrai o corpo comum num helper privado e adiciona um segundo rate limit. As regras do login não mudam — `tests/modules/auth/test_rate_limit.py` deve continuar verde.

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/modules/auth/test_password_reset_rate_limit.py`:

```python
import pytest
import redis.asyncio as aioredis

from app.modules.auth.exceptions import RateLimitExceeded
from app.modules.auth.rate_limit import check_password_reset_rate_limit


async def test_under_limit_does_not_raise(redis_client: aioredis.Redis) -> None:
    for _ in range(5):
        await check_password_reset_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")


async def test_sixth_attempt_raises(redis_client: aioredis.Redis) -> None:
    for _ in range(5):
        await check_password_reset_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")
    with pytest.raises(RateLimitExceeded) as exc_info:
        await check_password_reset_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")
    assert exc_info.value.retry_after > 0


async def test_email_limit_triggers_across_ips(redis_client: aioredis.Redis) -> None:
    for i in range(5):
        await check_password_reset_rate_limit(redis_client, ip=f"10.0.0.{i}", email="t@b.com")
    with pytest.raises(RateLimitExceeded):
        await check_password_reset_rate_limit(redis_client, ip="10.0.0.99", email="t@b.com")


async def test_independent_from_login_keys(redis_client: aioredis.Redis) -> None:
    # Different key namespace: login attempts must not consume reset budget.
    from app.modules.auth.rate_limit import check_login_rate_limit

    for _ in range(5):
        await check_login_rate_limit(redis_client, ip="5.5.5.5", email="x@b.com")
    # Reset limit for the same ip/email is still fresh.
    await check_password_reset_rate_limit(redis_client, ip="5.5.5.5", email="x@b.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/modules/auth/test_password_reset_rate_limit.py -v`
Expected: FAIL — `ImportError: cannot import name 'check_password_reset_rate_limit'`

- [ ] **Step 3: Refactor rate_limit.py and add the new check**

Substituir o conteúdo de `back-end/app/modules/auth/rate_limit.py` por:

```python
from collections.abc import Iterable

import redis.asyncio as aioredis

from app.core.config import settings
from app.modules.auth.exceptions import RateLimitExceeded


async def _enforce(
    redis: aioredis.Redis,
    *,
    keys: Iterable[str],
    limit: int,
    window: int,
) -> None:
    """Atomic sliding-window check over one or more counters.

    Counts are incremented via a MULTI/EXEC pipeline; the first increment in a
    window sets the TTL via ``EXPIRE ... NX`` so later increments don't slide it.
    Raises :class:`RateLimitExceeded` (with ``retry_after``) past the threshold.
    """
    for key in keys:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window, nx=True)
            pipe.ttl(key)
            count, _expire_set, ttl = await pipe.execute()

        if count > limit:
            raise RateLimitExceeded(retry_after=max(int(ttl), 1))


async def check_login_rate_limit(redis: aioredis.Redis, *, ip: str, email: str) -> None:
    """Enforce the login rate limit for the given IP and email."""
    await _enforce(
        redis,
        keys=(f"login:ip:{ip}", f"login:email:{email.lower()}"),
        limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


async def check_password_reset_rate_limit(redis: aioredis.Redis, *, ip: str, email: str) -> None:
    """Enforce the password-reset request rate limit for the given IP and email."""
    await _enforce(
        redis,
        keys=(f"pwreset:req:ip:{ip}", f"pwreset:req:email:{email.lower()}"),
        limit=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS,
        window=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS,
    )
```

- [ ] **Step 4: Run tests to verify they pass (new + existing login)**

Run: `uv run pytest tests/modules/auth/test_password_reset_rate_limit.py tests/modules/auth/test_rate_limit.py -v`
Expected: PASS (todos verdes — comportamento do login inalterado)

- [ ] **Step 5: Commit**

```bash
git add app/modules/auth/rate_limit.py tests/modules/auth/test_password_reset_rate_limit.py
git commit -m "feat(auth): add password reset request rate limit"
```

---

## Task 8: Schemas

**Files:**
- Modify: `back-end/app/modules/auth/schemas.py`
- Test: `back-end/tests/modules/auth/test_password_reset_schemas.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/modules/auth/test_password_reset_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import PasswordResetConfirmIn, PasswordResetRequestIn


def test_request_lowercases_email() -> None:
    assert PasswordResetRequestIn(email="Foo@Example.COM").email == "foo@example.com"


def test_confirm_accepts_valid_payload() -> None:
    payload = PasswordResetConfirmIn(email="a@b.com", code="123456", new_password="Secret!1")
    assert payload.code == "123456"
    assert payload.email == "a@b.com"


@pytest.mark.parametrize("bad_code", ["12345", "1234567", "12a456", "abcdef"])
def test_confirm_rejects_non_six_digit_code(bad_code: str) -> None:
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(email="a@b.com", code=bad_code, new_password="Secret!1")


def test_confirm_rejects_password_without_special_char() -> None:
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(email="a@b.com", code="123456", new_password="Secret12")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/modules/auth/test_password_reset_schemas.py -v`
Expected: FAIL — `ImportError: cannot import name 'PasswordResetRequestIn'`

- [ ] **Step 3: Add the schemas**

Em `back-end/app/modules/auth/schemas.py`, adicionar a regex de OTP perto das outras (após linha 12) e os dois schemas ao fim do arquivo. A regex:

```python
_OTP_RE = re.compile(r"^\d{6}$")
```

Ao fim do arquivo:

```python
class PasswordResetRequestIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class PasswordResetConfirmIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=254)
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("code")
    @classmethod
    def _six_digits(cls, v: str) -> str:
        if not _OTP_RE.match(v):
            raise ValueError("code must be exactly 6 digits")
        return v

    @field_validator("new_password")
    @classmethod
    def _password_policy(cls, v: str) -> str:
        if not _SPECIAL_CHAR_RE.search(v):
            raise ValueError("password must contain at least one special character")
        return v
```

> `_SPECIAL_CHAR_RE` já existe no topo de `schemas.py` (linha 11) — reutilizar, não redefinir.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/modules/auth/test_password_reset_schemas.py -v`
Expected: PASS (todos verdes)

- [ ] **Step 5: Commit**

```bash
git add app/modules/auth/schemas.py tests/modules/auth/test_password_reset_schemas.py
git commit -m "feat(auth): add password reset request and confirm schemas"
```

---

## Task 9: Services (request + confirm) and exception

**Files:**
- Modify: `back-end/app/modules/auth/exceptions.py`, `back-end/app/modules/auth/services.py`
- Test: coberto pelo teste de fluxo na Task 11 (este passo entrega o código de serviço que a task de e-mail e as rotas usam)

> Este task adiciona `InvalidResetCode` e as duas funções de serviço. Como o serviço enfileira a task Celery (criada na Task 10) via import local, a verificação completa acontece no teste de fluxo (Task 11). Aqui garantimos que o módulo importa sem erro.

- [ ] **Step 1: Add the exception**

Em `back-end/app/modules/auth/exceptions.py`, ao fim:

```python
class InvalidResetCode(AuthError):
    """Password reset code was missing, expired, wrong, or attempts were exhausted."""
```

- [ ] **Step 2: Add the service functions**

Em `back-end/app/modules/auth/services.py`:

Adicionar aos imports do topo (`from app.modules.auth.exceptions import (...)`) o nome `InvalidResetCode`, e adicionar:

```python
import redis.asyncio as aioredis

from app.modules.auth import password_reset
```

> `select`, `User`, `hash_password`, `logger` já estão importados no arquivo.

Adicionar ao fim do arquivo:

```python
async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def request_password_reset(
    session: AsyncSession, redis: aioredis.Redis, email: str
) -> None:
    """Generate and dispatch a reset code. Silent no-op if the email is unknown
    (anti-enumeration: the route always responds 200 regardless)."""
    user = await _get_user_by_email(session, email)
    if user is None:
        logger.info("auth: password reset requested for unknown email (ignored)")
        return

    code = password_reset.generate_otp()
    await password_reset.store_reset_code(redis, user.id, code)

    # Local import keeps services <-> tasks decoupled at module load time.
    from app.modules.auth.tasks import send_password_reset_email_task

    send_password_reset_email_task.delay(user.email, code)
    logger.info("auth: password reset code dispatched user={}", user.id)


async def confirm_password_reset(
    session: AsyncSession,
    redis: aioredis.Redis,
    email: str,
    code: str,
    new_password: str,
) -> None:
    """Verify the OTP and set the new password. Raises InvalidResetCode on any
    failure with no detail that distinguishes the cause."""
    user = await _get_user_by_email(session, email)
    if user is None:
        raise InvalidResetCode()

    if not await password_reset.verify_reset_code(redis, user.id, code):
        raise InvalidResetCode()

    user.password_hash = hash_password(new_password)
    await session.commit()
    await password_reset.clear_reset_code(redis, user.id)
    logger.info("auth: password reset completed user={}", user.id)
```

- [ ] **Step 3: Verify the module imports**

Run: `uv run python -c "import app.modules.auth.services"`
Expected: sem saída / sem erro (a Task 10 cria a task referenciada; o import local só é avaliado em runtime, então este import de módulo já passa)

- [ ] **Step 4: Commit**

```bash
git add app/modules/auth/exceptions.py app/modules/auth/services.py
git commit -m "feat(auth): add password reset request and confirm services"
```

---

## Task 10: Celery task

**Files:**
- Create: `back-end/app/modules/auth/tasks.py`
- Test: `back-end/tests/modules/auth/test_password_reset_task.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/modules/auth/test_password_reset_task.py`:

```python
from app.core.email.base import EmailMessage
from app.modules.auth.tasks import _build_reset_message, _send_reset_email


def test_build_reset_message_contains_code_and_ttl() -> None:
    msg = _build_reset_message("user@example.com", "123456")
    assert isinstance(msg, EmailMessage)
    assert msg.to == "user@example.com"
    assert "123456" in msg.text
    assert "123456" in msg.html
    assert "10" in msg.text  # 600s == 10 minutes


async def test_send_reset_email_uses_injected_sender() -> None:
    sent: list[EmailMessage] = []

    class FakeSender:
        async def send(self, message: EmailMessage) -> None:
            sent.append(message)

    await _send_reset_email("user@example.com", "123456", sender=FakeSender())
    assert len(sent) == 1
    assert sent[0].to == "user@example.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/modules/auth/test_password_reset_task.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.auth.tasks'`

- [ ] **Step 3: Implement the task**

Criar `back-end/app/modules/auth/tasks.py`:

```python
import asyncio

from loguru import logger

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.email import EmailMessage, EmailSender, get_email_sender


def _build_reset_message(email: str, code: str) -> EmailMessage:
    minutes = settings.PASSWORD_RESET_CODE_TTL_SECONDS // 60
    subject = "Seu codigo de recuperacao de senha"
    text = (
        f"Seu codigo de recuperacao e {code}.\n"
        f"Ele expira em {minutes} minutos. Se voce nao pediu isso, ignore este e-mail."
    )
    html = (
        f"<p>Seu codigo de recuperacao e <strong>{code}</strong>.</p>"
        f"<p>Ele expira em {minutes} minutos. Se voce nao pediu isso, ignore este e-mail.</p>"
    )
    return EmailMessage(to=email, subject=subject, html=html, text=text)


async def _send_reset_email(email: str, code: str, *, sender: EmailSender | None = None) -> None:
    sender = sender or get_email_sender()
    await sender.send(_build_reset_message(email, code))


@celery_app.task(
    name="auth.send_password_reset_email",
    time_limit=settings.EMAIL_SEND_TIME_LIMIT,
    soft_time_limit=settings.EMAIL_SEND_SOFT_TIME_LIMIT,
)
def send_password_reset_email_task(email: str, code: str) -> None:
    """Send the OTP email. Idempotent: re-running re-delivers the same code."""
    asyncio.run(_send_reset_email(email, code))
    logger.info("auth: password reset email dispatched to={}", email)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/modules/auth/test_password_reset_task.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/modules/auth/tasks.py tests/modules/auth/test_password_reset_task.py
git commit -m "feat(auth): add Celery task to send password reset email"
```

---

## Task 11: Routes + end-to-end flow

**Files:**
- Modify: `back-end/app/modules/auth/routes.py`
- Test: `back-end/tests/modules/auth/test_password_reset_flow.py`

- [ ] **Step 1: Write the failing test**

Criar `back-end/tests/modules/auth/test_password_reset_flow.py`:

```python
import re

import pytest

from tests.modules.auth.conftest import make_register_payload


@pytest.fixture(autouse=True)
def captured_reset_emails(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Keep the reset flow offline and capture (email, code) the route would enqueue."""
    from app.modules.auth import tasks

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks.send_password_reset_email_task,
        "delay",
        lambda email, code: calls.append((email, code)),
    )
    return calls


async def _register(client) -> dict:
    payload = make_register_payload()
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201
    return payload


async def test_request_returns_200_for_existing_email_and_enqueues(
    client, captured_reset_emails
) -> None:
    payload = await _register(client)
    resp = await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    assert resp.status_code == 200
    assert len(captured_reset_emails) == 1
    assert captured_reset_emails[0][0] == payload["email"]


async def test_request_returns_200_for_unknown_email_without_enqueue(
    client, captured_reset_emails
) -> None:
    resp = await client.post(
        "/api/auth/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert resp.status_code == 200
    assert captured_reset_emails == []


async def test_full_reset_flow_changes_password(client, captured_reset_emails) -> None:
    payload = await _register(client)

    await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    _email, code = captured_reset_emails[0]
    assert re.fullmatch(r"\d{6}", code)

    new_password = "Brand!New9"
    confirm = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": code, "new_password": new_password},
    )
    assert confirm.status_code == 200

    # New password works.
    ok = await client.post(
        "/api/auth/login", json={"email": payload["email"], "password": new_password}
    )
    assert ok.status_code == 200
    # Old password no longer works.
    bad = await client.post(
        "/api/auth/login", json={"email": payload["email"], "password": payload["password"]}
    )
    assert bad.status_code == 401


async def test_confirm_with_wrong_code_is_400(client, captured_reset_emails) -> None:
    payload = await _register(client)
    await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": "000000", "new_password": "Brand!New9"},
    )
    assert resp.status_code == 400


async def test_confirm_with_unknown_email_is_400(client) -> None:
    resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": "nobody@example.com", "code": "123456", "new_password": "Brand!New9"},
    )
    assert resp.status_code == 400


async def test_code_is_single_use(client, captured_reset_emails) -> None:
    payload = await _register(client)
    await client.post("/api/auth/password-reset/request", json={"email": payload["email"]})
    _email, code = captured_reset_emails[0]

    first = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": code, "new_password": "Brand!New9"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/password-reset/confirm",
        json={"email": payload["email"], "code": code, "new_password": "Another!9"},
    )
    assert second.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/modules/auth/test_password_reset_flow.py -v`
Expected: FAIL — 404 nas rotas `/api/auth/password-reset/*` (ainda não existem)

- [ ] **Step 3: Add the routes**

Em `back-end/app/modules/auth/routes.py`:

Adicionar `aioredis`/`get_redis` já estão importados. Adicionar `InvalidResetCode` ao import de exceptions e os dois schemas ao import de schemas:

```python
from app.modules.auth.exceptions import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidResetCode,
    InvalidToken,
    RateLimitExceeded,
    UserInactive,
)
from app.modules.auth.rate_limit import (
    check_login_rate_limit,
    check_password_reset_rate_limit,
)
from app.modules.auth.schemas import (
    AuthResponse,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
    UserPatch,
)
```

Adicionar os endpoints ao fim do arquivo (antes ou depois de `logout`):

```python
@router.post("/password-reset/request")
async def password_reset_request(
    payload: PasswordResetRequestIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict[str, str]:
    ip = request.client.host if request.client else "unknown"
    try:
        await check_password_reset_rate_limit(redis, ip=ip, email=payload.email)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    await services.request_password_reset(session, redis, payload.email)
    # Always 200 — never reveal whether the email exists (anti-enumeration).
    return {"detail": "If the email exists, a reset code was sent."}


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    payload: PasswordResetConfirmIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> dict[str, str]:
    try:
        await services.confirm_password_reset(
            session, redis, payload.email, payload.code, payload.new_password
        )
    except InvalidResetCode as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired code",
        ) from exc
    return {"detail": "Password updated."}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/modules/auth/test_password_reset_flow.py -v`
Expected: PASS (todos verdes)

- [ ] **Step 5: Commit**

```bash
git add app/modules/auth/routes.py tests/modules/auth/test_password_reset_flow.py
git commit -m "feat(auth): add password reset request and confirm endpoints"
```

---

## Task 12: Full suite, lint, and docs

**Files:**
- Modify: `back-end/.env.example` (se existir; senão criar nota no README do back-end)

- [ ] **Step 1: Run the entire auth + email suite**

Run: `uv run pytest tests/modules/auth tests/core/email tests/core/test_config_email.py -v`
Expected: PASS (tudo verde)

- [ ] **Step 2: Run lint and format**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: sem erros. Se `ruff format --check` reclamar, rodar `uv run ruff format .` e revisar o diff.

- [ ] **Step 3: Run the full test suite (no regressions)**

Run: `uv run pytest -q`
Expected: toda a suíte verde (especialmente `tests/modules/auth/test_rate_limit.py`, que foi tocado indiretamente pelo refactor da Task 7).

- [ ] **Step 4: Document the env vars**

Se existir `back-end/.env.example`, adicionar:

```dotenv
# E-mail provider for password reset. "console" (default) only logs; "resend"
# sends via the Resend API. Get a key at https://resend.com.
EMAIL_BACKEND=console
RESEND_API_KEY=
EMAIL_FROM="Edu <no-reply@edu.app>"
```

Se não existir, adicionar a mesma seção ao final de `back-end/README.md` sob um cabeçalho "## E-mail (recuperação de senha)".

- [ ] **Step 5: Commit**

```bash
git add back-end/.env.example 2>/dev/null || git add back-end/README.md
git commit -m "docs(auth): document email provider env vars for password reset"
```

---

## Self-Review (preenchido)

**Spec coverage:**
- Camada de adapter (porta + console + resend + factory) → Tasks 2–5 ✅
- OTP gerado/hasheado, store no Redis com TTL + lockout → Task 6 ✅
- Anti-enumeração no `request` (sempre 200) → Tasks 9, 11 ✅
- Limite de tentativas de verificação → Tasks 6, 11 ✅
- Rate limit do request (IP+email) → Task 7 ✅
- Comparação constant-time (`compare_secret`) → Task 6 ✅
- Schemas explícitos com limites → Task 8 ✅
- Task Celery com `time_limit`/`soft_time_limit`, sem DB → Task 10 ✅
- Endpoints e fluxo ponta-a-ponta (nova senha loga, antiga não, código single-use) → Task 11 ✅
- Config nova → Task 1 ✅
- Fora de escopo (revogação de sessões, telas Flutter, retry da task) → mantido fora, documentado na spec ✅

**Placeholder scan:** nenhum TBD/TODO; todo passo de código mostra o código real.

**Type consistency:** `EmailMessage(to, subject, html, text)`, `EmailSender.send(message)`, `generate_otp()/hash_otp()/store_reset_code()/verify_reset_code()/clear_reset_code()`, `request_password_reset(session, redis, email)`, `confirm_password_reset(session, redis, email, code, new_password)`, `send_password_reset_email_task.delay(email, code)`, `check_password_reset_rate_limit(redis, *, ip, email)` — nomes consistentes entre tasks de definição e de uso.
