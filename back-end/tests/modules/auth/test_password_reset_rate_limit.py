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
