# Design — Durable fix for product images not loading on physical devices

**Date:** 2026-06-14
**Type:** Bug fix (backend config/tooling + small backend code change). No frontend change.

## Problem

On a physical device, product images in the marketplace stay in an infinite
loading spinner. The product cards, prices, ratings, and "+ Carrinho" all
render (the API works), but the image area never resolves.

### Root cause

- `ProductImage` (`front-end-flutter/.../widgets/product_image.dart`) renders a
  `CachedNetworkImage` whose `placeholder` is a spinner shown until the request
  completes **or** errors. The spinner never clears because the request
  **hangs** (a fast DNS failure would instead fall back to the type icon via
  `errorWidget`).
- Product `image_url`s are **presigned MinIO GET URLs**. The URL host is
  `R2_PUBLIC_ENDPOINT_URL` (`back-end/app/core/storage.py`,
  `generate_presigned_get`), set in `back-end/.env` to `http://10.0.2.2:9000`.
- `10.0.2.2` is the **Android-emulator** alias for the host loopback. On a
  physical device it is not routable, so the TCP connect to `10.0.2.2:9000`
  hangs → infinite spinner.
- The **API** base URL does not have this problem: commit `dba3eaa` auto-detects
  the host LAN IP (`HOST_IP`) in the `Makefile` and injects it via
  `--dart-define=API_BASE_URL`. The **image** host never got the same treatment
  — it is still a static `.env` value, so the two drift.
- MinIO is published on `0.0.0.0:9000`, so the device *can* reach
  `http://<host-LAN-IP>:9000`. Only the URL host is wrong.

### Aggravating factor — presign cache

`presigned_image_url` (`back-end/app/core/media.py`) memoizes the signed URL in
Redis under `presign:{key}` for `MEDIA_PRESIGN_CACHE_TTL_SECONDS` (~23h).
Changing the endpoint config alone is not enough: stale `10.0.2.2` URLs keep
being served from cache until they expire.

## Goal

Make the presigned image host environment-agnostic and self-healing, mirroring
how the API URL already works: derived from the same auto-detected `HOST_IP`,
with no manual Redis flush ever required.

## Design

Three components plus a doc touch-up.

### 1. `back-end/app/core/media.py` — self-healing presign cache

Include a fingerprint of the resolved public endpoint in the cache key so that
when the endpoint (host/IP) changes, a *new* cache key is used and stale entries
are simply bypassed (they expire on their own TTL). No manual flush, ever.

```python
import hashlib

from app.core.config import settings


def _endpoint_fingerprint() -> str:
    """Short, stable hash of the public endpoint the URL is signed against, so a
    changed endpoint (e.g. a new host LAN IP) yields a fresh cache key instead of
    serving a stale URL."""
    endpoint = settings.R2_PUBLIC_ENDPOINT_URL or settings.R2_ENDPOINT_URL
    return hashlib.sha256(endpoint.encode()).hexdigest()[:12]
```

In `presigned_image_url`, change the cache key:

```python
cache_key = f"presign:{_endpoint_fingerprint()}:{key}"
```

The endpoint resolution (`R2_PUBLIC_ENDPOINT_URL or R2_ENDPOINT_URL`) mirrors the
public-endpoint resolution in `ObjectStorage._client(public=True)`, keeping the
fingerprint aligned with the host actually baked into the signed URL.

Everything else in `presigned_image_url` (empty-key short-circuit, TTL,
memoization) is unchanged.

### 2. `back-end/tests/core/test_media.py` — tests

- **Update** `test_presigned_image_url_is_cached`: it currently asserts the
  cached value lives at `f"presign:{key}"`. With the new key it must read from
  `f"presign:{_endpoint_fingerprint()}:{key}"`. Import `_endpoint_fingerprint`
  (or recompute the same hash inline) so the test tracks the production key.
- **Add** a test proving the cache is endpoint-scoped: signing the same object
  key under two different `R2_PUBLIC_ENDPOINT_URL` settings (via
  `monkeypatch.setattr(settings, "R2_PUBLIC_ENDPOINT_URL", ...)`) writes to two
  different `presign:*` cache keys — so changing the endpoint does not reuse a
  stale URL. Follow the existing file's style (real `redis_client` fixture, real
  `ObjectStorage()`; presigning is local signing and needs no network).

### 3. `back-end/docker-compose.yml` — build the host from `HOST_IP`

The `api` and `worker` services use `env_file: .env` and already have an
`environment:` block (for `FIREBASE_CREDENTIALS_PATH`). A compose `environment:`
entry overrides `env_file`, so add to **both** the `api` and `worker`
`environment:` blocks:

```yaml
R2_PUBLIC_ENDPOINT_URL: "http://${HOST_IP:-10.0.2.2}:9000"
```

`${HOST_IP:-10.0.2.2}` falls back to the current emulator alias when `HOST_IP`
is unset, so emulator/desktop users are unaffected. Set on both services for
consistency (only the API route presigns today, but keeping them aligned avoids
surprises if the worker ever signs URLs). The MinIO host port stays `9000`,
matching the published `9000:9000` mapping.

### 4. `Makefile` — `back-up` exports the detected `HOST_IP`

`back-up` currently runs `cd $(BACK_DIR) && $(COMPOSE) up -d`. Pass the existing
auto-detected `HOST_IP` (the same variable `make front` uses) into the compose
process so the interpolation above resolves to the LAN IP:

```make
back-up: ## Start backend stack (postgres, redis, rabbitmq, api, worker)
	cd $(BACK_DIR) && HOST_IP=$(HOST_IP) $(COMPOSE) up -d
```

When detection fails, `HOST_IP` is empty and compose uses the `10.0.2.2`
fallback — same as today. No new variable or detection logic is introduced; the
existing `HOST_IP` block is the single source of truth shared with `make front`.

### 5. `back-end/.env.example` — doc touch-up

Update the `R2_PUBLIC_ENDPOINT_URL` comment (currently suggests hand-setting it
to `http://10.0.2.2:9000`) to explain that for local dev it is now derived
automatically from the host LAN IP by `make back-up`, and is only set explicitly
in production (the real R2 endpoint).

## Verification

- **Automated:** `make back-test` (runs pytest in-container; the media tests need
  Redis, which the container stack provides). All tests green, including the
  updated and new `test_media.py` cases.
- **Manual (final confirmation):** `make back-down && make back-up`, then reload
  the app on the physical device — product images render instead of spinning.
  Because of component 1, no manual `presign:*` flush is needed.

## Out of scope

- **Frontend:** no Flutter change. `ProductImage` behavior is correct.
- **Production R2:** prod sets `R2_PUBLIC_ENDPOINT_URL` to the real R2 host
  explicitly and has no `HOST_IP`; the compose fallback path is unused there.
- **MinIO port parameterization:** keep the literal `9000`; not worth a new var.

## Expected commits

1. `test(media): pin presign cache key to the signing endpoint`
2. `fix(media): scope the presign cache key to the public endpoint`
3. `fix(tooling): derive the presigned image host from the host LAN IP`
   (docker-compose + Makefile + .env.example)

(TDD order: failing/updated test first, then the media.py change; the tooling
commit is config-only. The implementation plan may refine this split.)
