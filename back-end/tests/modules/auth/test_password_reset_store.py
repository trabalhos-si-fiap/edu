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
