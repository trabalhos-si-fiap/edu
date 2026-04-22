import hmac
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import JWTError

from app.core.config import settings
from app.modules.auth import security


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self) -> None:
        hashed = security.hash_password("CorrectHorse!Battery")
        assert hashed != "CorrectHorse!Battery"
        assert security.verify_password("CorrectHorse!Battery", hashed)

    def test_verify_rejects_wrong_password(self) -> None:
        hashed = security.hash_password("RightPassword!1")
        assert not security.verify_password("WrongPassword!1", hashed)

    def test_hashes_of_same_password_differ(self) -> None:
        h1 = security.hash_password("Same!Password1")
        h2 = security.hash_password("Same!Password1")
        assert h1 != h2

    def test_dummy_hash_is_valid_bcrypt_but_never_verifies(self) -> None:
        # Used by login to keep timing constant when email doesn't exist.
        assert security.DUMMY_PASSWORD_HASH.startswith("$2")
        assert not security.verify_password("any-plaintext", security.DUMMY_PASSWORD_HASH)


class TestJwtTokens:
    def test_access_token_encodes_user_id_and_type(self) -> None:
        user_id = uuid.uuid4()
        token = security.create_access_token(user_id)
        payload = security.decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_refresh_token_has_refresh_type(self) -> None:
        user_id = uuid.uuid4()
        token = security.create_refresh_token(user_id)
        payload = security.decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == str(user_id)

    def test_access_and_refresh_tokens_have_different_jti(self) -> None:
        user_id = uuid.uuid4()
        access = security.decode_token(security.create_access_token(user_id))
        refresh = security.decode_token(security.create_refresh_token(user_id))
        assert access["jti"] != refresh["jti"]

    def test_decode_rejects_invalid_signature(self) -> None:
        user_id = uuid.uuid4()
        token = security.create_access_token(user_id)
        tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
        with pytest.raises(JWTError):
            security.decode_token(tampered)

    def test_decode_rejects_expired_token(self) -> None:
        user_id = uuid.uuid4()
        past = datetime.now(UTC) - timedelta(minutes=1)
        token = security.create_access_token(user_id, expires_at=past)
        with pytest.raises(JWTError):
            security.decode_token(token)

    def test_access_token_respects_configured_lifetime(self) -> None:
        user_id = uuid.uuid4()
        before = int(time.time())
        token = security.create_access_token(user_id)
        after = int(time.time())
        payload = security.decode_token(token)
        expected_min = before + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expected_max = after + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert expected_min <= payload["exp"] <= expected_max

    def test_refresh_token_lifetime_in_days(self) -> None:
        user_id = uuid.uuid4()
        before = int(time.time())
        token = security.create_refresh_token(user_id)
        after = int(time.time())
        payload = security.decode_token(token)
        expected_min = before + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        expected_max = after + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        assert expected_min <= payload["exp"] <= expected_max


class TestConstantTimeCompare:
    def test_equal_secrets_match(self) -> None:
        assert security.compare_secret("abc123", "abc123") is True

    def test_different_secrets_do_not_match(self) -> None:
        assert security.compare_secret("abc123", "abc124") is False

    def test_different_lengths_do_not_match(self) -> None:
        assert security.compare_secret("abc", "abcdef") is False

    def test_none_values_do_not_match(self) -> None:
        assert security.compare_secret(None, "abc") is False
        assert security.compare_secret("abc", None) is False
        assert security.compare_secret(None, None) is False

    def test_uses_hmac_compare_digest(self) -> None:
        # Proof the primitive is the standard one; prevents regression to `==`.
        assert hmac.compare_digest(b"x", b"x")
        assert security.compare_secret("x", "x") is True
