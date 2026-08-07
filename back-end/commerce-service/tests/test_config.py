import uuid

from app.config import settings
from app.ids import new_uuid


def test_media_settings_have_the_legacy_defaults():
    """Os defaults têm que bater com `legacy/app/core/config.py` — o mesmo
    MinIO serve os dois enquanto o legacy estiver de pé, e a URL presignada
    é assinada contra o mesmo bucket."""
    assert settings.r2_bucket == "edu-media"
    assert settings.r2_region == "auto"
    assert settings.media_presign_ttl_seconds == 86400
    assert settings.media_presign_cache_ttl_seconds == 82800
    assert settings.media_max_upload_bytes == 5 * 1024 * 1024


def test_presign_cache_ttl_is_shorter_than_the_url_ttl():
    """Se o cache durasse mais que a assinatura, o Redis devolveria uma URL
    já expirada — imagem quebrada no app, sem erro em lugar nenhum."""
    assert settings.media_presign_cache_ttl_seconds < settings.media_presign_ttl_seconds


def test_new_uuid_is_time_ordered():
    """UUIDv7 preserva localidade de inserção no índice B-tree do Postgres.
    Dois ids gerados em sequência têm que sair ordenados."""
    primeiro = new_uuid()
    segundo = new_uuid()
    assert isinstance(primeiro, uuid.UUID)
    assert primeiro.bytes < segundo.bytes
