import pytest
from pydantic import ValidationError

from app.modules.notifications.schemas import (
    DevicePlatform,
    DeviceTokenIn,
    DeviceTokenOut,
)


class TestDeviceTokenIn:
    def test_platform_defaults_to_android(self) -> None:
        payload = DeviceTokenIn(token="abc123")
        assert payload.platform is DevicePlatform.ANDROID

    def test_empty_token_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DeviceTokenIn(token="")

    def test_token_over_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DeviceTokenIn(token="x" * 256)

    def test_unknown_platform_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DeviceTokenIn(token="abc123", platform="symbian")

    def test_whitespace_is_stripped(self) -> None:
        payload = DeviceTokenIn(token="  abc123  ")
        assert payload.token == "abc123"


class TestDeviceTokenOut:
    def test_does_not_expose_token_value(self) -> None:
        # The raw FCM token must never leave the server (CLAUDE.md rule 6/5).
        assert "token" not in DeviceTokenOut.model_fields
