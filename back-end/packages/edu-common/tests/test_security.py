from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from edu_common.security import (
    DEFAULT_BCRYPT_ROUNDS,
    DUMMY_PASSWORD_HASH,
    MAX_PASSWORD_BYTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-not-a-real-key"


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


@pytest.mark.parametrize("days", [1, 7])
def test_refresh_token_expiry_respects_argument_in_days(days: int):
    """Regression: a `timedelta(minutes=...)` slip in create_refresh_token
    would satisfy the old refresh-type test but fail this one."""
    token = create_refresh_token("u", "student", SECRET, expires_days=days)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    delta = payload["exp"] - payload["iat"]
    assert abs(delta - days * 86400) <= 2


def test_decode_token_returns_none_when_type_does_not_match_expected():
    refresh_token = create_refresh_token("user-1", "student", SECRET)
    assert decode_token(refresh_token, SECRET, expected_type="access") is None


def test_decode_token_returns_payload_when_type_matches_expected():
    access_token = create_access_token("user-1", "student", SECRET)
    payload = decode_token(access_token, SECRET, expected_type="access")
    assert payload is not None
    assert payload["type"] == "access"


def test_decode_token_returns_none_for_tampered_payload():
    token = create_access_token("user-1", "student", SECRET)
    header, payload, signature = token.split(".")
    flipped = "A" if payload[-1] != "A" else "B"
    tampered = f"{header}.{payload[:-1]}{flipped}.{signature}"
    assert decode_token(tampered, SECRET) is None


def test_decode_token_returns_none_for_none_secret():
    """A misconfigured (missing) JWT_SECRET must fail closed, not raise JWKError."""
    token = create_access_token("user-1", "student", SECRET)
    assert decode_token(token, None) is None  # type: ignore[arg-type]


def test_decode_token_returns_none_for_pem_shaped_secret():
    """An asymmetric-looking secret must fail closed, not raise JWKError."""
    token = create_access_token("user-1", "student", SECRET)
    pem = "-----BEGIN PUBLIC KEY-----\nnotarealkey\n-----END PUBLIC KEY-----"
    assert decode_token(token, pem) is None


def test_hash_password_raises_for_password_over_max_bytes():
    too_long = "a" * (MAX_PASSWORD_BYTES + 1)
    with pytest.raises(ValueError, match=str(MAX_PASSWORD_BYTES)):
        hash_password(too_long)


def test_verify_password_returns_false_for_password_over_max_bytes():
    """Asymmetric with hash_password by design: an over-long password can
    never match a stored hash, so this is a mismatch, not an error."""
    hashed = hash_password("Senha@123")
    too_long = "a" * (MAX_PASSWORD_BYTES + 1)
    assert verify_password(too_long, hashed) is False


def test_hash_password_respects_custom_rounds():
    hashed = hash_password("Senha@123", rounds=4)
    assert hashed.split("$")[2] == "04"
    assert verify_password("Senha@123", hashed) is True


def test_dummy_password_hash_uses_default_bcrypt_rounds():
    assert DUMMY_PASSWORD_HASH.split("$")[2] == f"{DEFAULT_BCRYPT_ROUNDS:02d}"


def test_dummy_password_hash_is_not_a_known_plaintext():
    """Regression: DUMMY_PASSWORD_HASH must not be derived from a plaintext
    that is public in the repo's history, which would let a trusting caller
    treat a known string as a valid credential."""
    assert verify_password("dummy-password-for-timing-defense", DUMMY_PASSWORD_HASH) is False
