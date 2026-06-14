# Presigned Image Host on Physical Devices — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make presigned product-image URLs reachable from physical devices by deriving the MinIO host from the same auto-detected `HOST_IP` as the API URL, and make the Redis presign cache self-heal when that host changes.

**Architecture:** (1) Scope the presign cache key to the signing endpoint so an endpoint change yields fresh URLs. (2) Have docker-compose build `R2_PUBLIC_ENDPOINT_URL` from `${HOST_IP}` (overriding `env_file`), and have `make back-up` export the existing auto-detected `HOST_IP`. No frontend change.

**Tech Stack:** Python 3.12, pytest (async, real Redis via `redis_client` fixture), Docker Compose, Make. Backend tests run in-container via `make back-test`.

---

## File Structure

- **Modify:** `back-end/app/core/media.py` — add `_endpoint_fingerprint()`, scope the cache key by it.
- **Modify:** `back-end/tests/core/test_media.py` — update the cache-key assertion, add an endpoint-scoping test.
- **Modify:** `back-end/docker-compose.yml` — add `R2_PUBLIC_ENDPOINT_URL` to the `api` and `worker` `environment:` blocks.
- **Modify:** `Makefile` — `back-up` exports `HOST_IP` into the compose process.
- **Modify:** `back-end/.env.example` — update the `R2_PUBLIC_ENDPOINT_URL` comment.

All backend commands run from `back-end/`.

---

### Task 1: Self-healing presign cache key (TDD)

**Files:**
- Modify: `back-end/app/core/media.py`
- Modify: `back-end/tests/core/test_media.py`

Context: `presigned_image_url` currently memoizes under `presign:{key}`. Because the key ignores the endpoint, a changed `R2_PUBLIC_ENDPOINT_URL` (e.g. a new host LAN IP) keeps serving stale URLs until TTL. Scoping the cache key to the signing endpoint fixes this. `ObjectStorage._client(public=True)` signs against `R2_PUBLIC_ENDPOINT_URL or R2_ENDPOINT_URL`; the fingerprint must mirror that resolution. The `redis_client` fixture (`tests/conftest.py:64`) provides a real Redis with `decode_responses=True` and flushes around each test. `ObjectStorage().generate_presigned_get` signs locally (no network needed).

- [ ] **Step 1: Update the existing test and add the endpoint-scoping test (RED)**

In `back-end/tests/core/test_media.py`, add the import and replace `test_presigned_image_url_is_cached`, then add a new test. Add to the existing imports at the top:

```python
from app.core.config import settings
from app.core.media import (
    ImageValidationError,
    _endpoint_fingerprint,
    presigned_image_url,
    validate_image_bytes,
)
```

(Remove the now-duplicated `presigned_image_url`/`validate_image_bytes`/`ImageValidationError` names from the old import line so they are imported exactly once.)

Replace the existing `test_presigned_image_url_is_cached` with:

```python
async def test_presigned_image_url_is_cached(redis_client: aioredis.Redis) -> None:
    storage = ObjectStorage()
    key = "products/cache-me.png"
    first = await presigned_image_url(key, storage=storage, redis=redis_client)
    cached = await redis_client.get(f"presign:{_endpoint_fingerprint()}:{key}")
    assert cached == first
    second = await presigned_image_url(key, storage=storage, redis=redis_client)
    assert second == first
```

Add this new test:

```python
async def test_presign_cache_is_scoped_to_endpoint(
    redis_client: aioredis.Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Changing the public endpoint (e.g. a new host LAN IP) must use a fresh
    # cache key, so a stale URL signed for the old host is never reused.
    storage = ObjectStorage()
    key = "products/scoped.png"

    monkeypatch.setattr(settings, "R2_PUBLIC_ENDPOINT_URL", "http://10.0.2.2:9000")
    first = await presigned_image_url(key, storage=storage, redis=redis_client)
    first_cache_key = f"presign:{_endpoint_fingerprint()}:{key}"

    monkeypatch.setattr(settings, "R2_PUBLIC_ENDPOINT_URL", "http://192.168.1.50:9000")
    second_cache_key = f"presign:{_endpoint_fingerprint()}:{key}"
    second = await presigned_image_url(key, storage=storage, redis=redis_client)

    assert first_cache_key != second_cache_key
    assert await redis_client.get(first_cache_key) == first
    assert await redis_client.get(second_cache_key) == second
```

- [ ] **Step 2: Run the tests to verify they fail (RED)**

Run: `make back-test` (or, if running focused on the host with the dev Redis available: `uv run pytest tests/core/test_media.py -v`)
Expected: FAIL — `_endpoint_fingerprint` does not exist yet (ImportError), so the module fails to import / collect.

- [ ] **Step 3: Implement the cache-key change (GREEN)**

In `back-end/app/core/media.py`, add the `hashlib` import at the top with the other imports:

```python
import hashlib
```

Add the helper near the top of the module (after the imports / `_ALLOWED`), referencing the already-imported `settings`:

```python
def _endpoint_fingerprint() -> str:
    """Short, stable hash of the public endpoint the URL is signed against, so a
    changed endpoint (e.g. a new host LAN IP) yields a fresh cache key instead of
    serving a stale URL."""
    endpoint = settings.R2_PUBLIC_ENDPOINT_URL or settings.R2_ENDPOINT_URL
    return hashlib.sha256(endpoint.encode()).hexdigest()[:12]
```

In `presigned_image_url`, change the cache-key line from:

```python
    cache_key = f"presign:{key}"
```

to:

```python
    cache_key = f"presign:{_endpoint_fingerprint()}:{key}"
```

Leave the empty-key short-circuit, the `redis.get`/`redis.set`, and the TTL exactly as they are.

- [ ] **Step 4: Run the tests to verify they pass (GREEN)**

Run: `make back-test` (or focused: `uv run pytest tests/core/test_media.py -v`)
Expected: PASS — all `test_media.py` tests green, including the updated and new cases.

- [ ] **Step 5: Lint**

Run: `cd back-end && uv run ruff check app/core/media.py tests/core/test_media.py`
Expected: clean (no warnings).

- [ ] **Step 6: Commit (test, then implementation)**

```bash
git add back-end/tests/core/test_media.py
git commit -m "test(media): pin presign cache key to the signing endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"

git add back-end/app/core/media.py
git commit -m "fix(media): scope the presign cache key to the public endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

(The test commit references `_endpoint_fingerprint`, which only exists after the implementation commit. That is acceptable: the two commits land together and the working tree is only verified green at Step 4. If you prefer a bisect-clean history, stage both files and make a single `fix(media): ...` commit instead.)

---

### Task 2: Derive the presigned image host from `HOST_IP` (tooling)

**Files:**
- Modify: `back-end/docker-compose.yml`
- Modify: `Makefile`
- Modify: `back-end/.env.example`

Config-only; no unit test. Verified by rendering the compose config with and without `HOST_IP`.

- [ ] **Step 1: Add `R2_PUBLIC_ENDPOINT_URL` to the `api` service**

In `back-end/docker-compose.yml`, the `api` service's `environment:` block currently contains only `FIREBASE_CREDENTIALS_PATH: ...`. Add the line so the block reads:

```yaml
    environment:
      FIREBASE_CREDENTIALS_PATH: /app/secrets/edu-ia-29080-firebase-adminsdk-fbsvc-4b9cc9075d.json
      # Sign presigned image URLs against the host LAN IP so physical devices can
      # reach MinIO. Built from HOST_IP (exported by `make back-up`); falls back
      # to the Android-emulator alias when HOST_IP is unset.
      R2_PUBLIC_ENDPOINT_URL: "http://${HOST_IP:-10.0.2.2}:9000"
```

- [ ] **Step 2: Add the same line to the `worker` service**

The `worker` service's `environment:` block likewise contains only `FIREBASE_CREDENTIALS_PATH`. Add the identical `R2_PUBLIC_ENDPOINT_URL` line (with the same comment) to it, keeping `api` and `worker` consistent.

- [ ] **Step 3: Export `HOST_IP` from `back-up` in the Makefile**

In `Makefile`, change the `back-up` recipe from:

```make
back-up: ## Start backend stack (postgres, redis, rabbitmq, api, worker)
	cd $(BACK_DIR) && $(COMPOSE) up -d
```

to:

```make
back-up: ## Start backend stack (postgres, redis, rabbitmq, api, worker)
	cd $(BACK_DIR) && HOST_IP=$(HOST_IP) $(COMPOSE) up -d
```

`HOST_IP` is the existing auto-detected variable (defined near the top of the Makefile, shared with `make front`). No new detection logic.

- [ ] **Step 4: Update the `.env.example` comment**

In `back-end/.env.example`, the block around the commented `R2_PUBLIC_ENDPOINT_URL=http://10.0.2.2:9000` (lines ~41-46) currently instructs the developer to set it by hand. Replace that guidance to explain it is now derived automatically. Set the comment block to:

```
# Endpoint usado para montar a presigned URL acessível pelo app/device.
# Em dev você NÃO precisa setar isto: `make back-up` deriva o host da LAN
# automaticamente (mesmo HOST_IP do `make front`) e injeta via docker-compose,
# então as imagens carregam no emulador, no simulador e em devices físicos.
# Em prod, defina explicitamente (normalmente o mesmo host do R2_ENDPOINT_URL).
# R2_PUBLIC_ENDPOINT_URL=http://10.0.2.2:9000
```

- [ ] **Step 5: Verify compose interpolation both ways**

Run:
```bash
cd back-end
HOST_IP=192.168.1.50 docker compose config | grep R2_PUBLIC_ENDPOINT_URL
docker compose config | grep R2_PUBLIC_ENDPOINT_URL
```
Expected:
- With `HOST_IP` set: every occurrence shows `R2_PUBLIC_ENDPOINT_URL: http://192.168.1.50:9000` (for both `api` and `worker`).
- Without `HOST_IP` (and with no `R2_PUBLIC_ENDPOINT_URL` exported in the shell): shows the fallback `http://10.0.2.2:9000`.

Note: `docker compose config` also merges values from `env_file` (`.env`). If the developer's `.env` already sets `R2_PUBLIC_ENDPOINT_URL`, the `environment:` entry still wins at runtime; the `config` render confirms the `environment:` value is the interpolated one. If `grep` shows the `.env` literal instead of the interpolated value, confirm the `environment:` key was added to the correct service blocks.

- [ ] **Step 6: Commit**

```bash
git add back-end/docker-compose.yml Makefile back-end/.env.example
git commit -m "fix(tooling): derive the presigned image host from the host LAN IP

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Manual confirmation (after both tasks)

Not a plan step (requires a device), for the human to run:
```bash
make back-down && make back-up
# reload the app on the physical device — product images render (no spinner)
```
Because of Task 1, no manual `presign:*` flush is required.

---

## Self-Review

**Spec coverage:**
- Self-healing cache key (`_endpoint_fingerprint`, scoped cache key) → Task 1 Steps 3-4. ✓
- Tests: update existing cache test + add endpoint-scoping test → Task 1 Steps 1-2. ✓
- compose builds host from `${HOST_IP:-10.0.2.2}` on api AND worker → Task 2 Steps 1-2. ✓
- Makefile `back-up` exports `HOST_IP` → Task 2 Step 3. ✓
- `.env.example` doc touch-up → Task 2 Step 4. ✓
- Verification (backend tests; compose config render) → Task 1 Step 4, Task 2 Step 5. ✓
- Out of scope (frontend, prod R2, MinIO port var) → not touched. ✓

**Placeholder scan:** none — all code, commands, and expected outputs are concrete.

**Type/name consistency:** `_endpoint_fingerprint()` defined in media.py (Task 1 Step 3) and imported/used identically in the tests (Task 1 Step 1) and the cache key. `R2_PUBLIC_ENDPOINT_URL` / `R2_ENDPOINT_URL` match `app/core/config.py`. `HOST_IP` matches the existing Makefile variable. Cache-key format `presign:{_endpoint_fingerprint()}:{key}` is identical in production and tests. ✓
