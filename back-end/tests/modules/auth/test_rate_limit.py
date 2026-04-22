import pytest
import redis.asyncio as aioredis

from app.modules.auth.exceptions import RateLimitExceeded
from app.modules.auth.rate_limit import check_login_rate_limit


async def test_under_limit_does_not_raise(redis_client: aioredis.Redis) -> None:
    for _ in range(4):
        await check_login_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")


async def test_fifth_attempt_is_still_allowed(redis_client: aioredis.Redis) -> None:
    for _ in range(5):
        await check_login_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")


async def test_sixth_attempt_raises(redis_client: aioredis.Redis) -> None:
    for _ in range(5):
        await check_login_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")
    with pytest.raises(RateLimitExceeded) as exc_info:
        await check_login_rate_limit(redis_client, ip="1.2.3.4", email="a@b.com")
    assert exc_info.value.retry_after > 0


async def test_different_ip_and_email_are_independent(
    redis_client: aioredis.Redis,
) -> None:
    for _ in range(5):
        await check_login_rate_limit(redis_client, ip="1.1.1.1", email="x@b.com")
    await check_login_rate_limit(redis_client, ip="2.2.2.2", email="y@b.com")


async def test_email_limit_triggers_across_different_ips(
    redis_client: aioredis.Redis,
) -> None:
    for i in range(5):
        await check_login_rate_limit(redis_client, ip=f"10.0.0.{i}", email="target@b.com")
    with pytest.raises(RateLimitExceeded):
        await check_login_rate_limit(redis_client, ip="10.0.0.200", email="target@b.com")


async def test_email_is_normalized_lowercase(redis_client: aioredis.Redis) -> None:
    for _ in range(5):
        await check_login_rate_limit(redis_client, ip="1.1.1.1", email="Foo@EXAMPLE.com")
    with pytest.raises(RateLimitExceeded):
        await check_login_rate_limit(redis_client, ip="9.9.9.9", email="foo@example.com")
