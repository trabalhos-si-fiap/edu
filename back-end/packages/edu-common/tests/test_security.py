from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from edu_common.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-not-a-real-key"  # noqa: S105 -- test fixture, not a real secret


def test_hash_password_produces_bcrypt_hash():
    hashed = hash_password("Senha@123")
    assert hashed.startswith("$2b$")
    assert hashed != "Senha@123"


def test_verify_password_accepts_correct_password():
    assert verify_password("Senha@123", hash_password("Senha@123")) is True


def test_verify_password_rejects_wrong_password():
    assert verify_password("errada", hash_password("Senha@123")) is False


def test_verify_password_returns_false_on_malformed_hash():
    assert verify_password("Senha@123", "nao-e-um-hash") is False


def test_dummy_password_hash_is_usable_for_timing_defense():
    assert DUMMY_PASSWORD_HASH.startswith("$2b$")
    assert verify_password("qualquer-coisa", DUMMY_PASSWORD_HASH) is False


def test_access_token_carries_sub_role_and_type():
    token = create_access_token("user-1", "student", SECRET)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert payload["sub"] == "user-1"
    assert payload["role"] == "student"
    assert payload["type"] == "access"


def test_access_token_carries_jti_and_iat():
    payload = jwt.decode(
        create_access_token("user-1", "student", SECRET), SECRET, algorithms=["HS256"]
    )
    assert payload["jti"]
    assert payload["iat"] <= int(datetime.now(UTC).timestamp())


def test_two_access_tokens_have_distinct_jti():
    a = jwt.decode(create_access_token("u", "student", SECRET), SECRET, algorithms=["HS256"])
    b = jwt.decode(create_access_token("u", "student", SECRET), SECRET, algorithms=["HS256"])
    assert a["jti"] != b["jti"]


def test_refresh_token_has_refresh_type():
    payload = jwt.decode(
        create_refresh_token("user-1", "admin", SECRET), SECRET, algorithms=["HS256"]
    )
    assert payload["type"] == "refresh"
    assert payload["role"] == "admin"


def test_decode_token_returns_payload_for_valid_token():
    payload = decode_token(create_access_token("user-1", "student", SECRET), SECRET)
    assert payload is not None
    assert payload["sub"] == "user-1"


def test_decode_token_returns_none_for_wrong_secret():
    assert decode_token(create_access_token("user-1", "student", SECRET), "outro-secret") is None


def test_decode_token_returns_none_for_garbage():
    assert decode_token("nao.e.um.jwt", SECRET) is None


def test_decode_token_returns_none_for_expired_token():
    expired = jwt.encode(
        {
            "sub": "user-1",
            "role": "student",
            "type": "access",
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        SECRET,
        algorithm="HS256",
    )
    assert decode_token(expired, SECRET) is None


@pytest.mark.parametrize("minutes", [1, 60])
def test_access_token_expiry_respects_argument(minutes: int):
    token = create_access_token("u", "student", SECRET, expires_minutes=minutes)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    delta = payload["exp"] - payload["iat"]
    assert abs(delta - minutes * 60) <= 2
