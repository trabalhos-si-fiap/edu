import uuid

from app.config import Settings, settings
from app.ids import new_uuid


def _campos_obrigatorios() -> dict[str, str]:
    """Os três campos de `Settings` sem default (`database_url`,
    `rabbitmq_url`, `jwt_secret`) — o mínimo para instanciar `Settings()`
    isolado do `.env` do desenvolvedor, para testar um default (como
    `avanco_automatico_segundos == 0`) sem depender do que está gravado ali."""
    return {
        "database_url": "postgresql+asyncpg://edu:edu@localhost:5433/commerce_test",
        "rabbitmq_url": "amqp://edu:edu@localhost:5673/",
        "jwt_secret": "test-secret",
    }


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


def test_the_automatic_advance_is_off_unless_configured():
    """`AVANCO_AUTOMATICO_SEGUNDOS` ausente ⇒ `0` ⇒ desligado. Critério de
    pronto 6 da spec C."""
    assert Settings(**_campos_obrigatorios()).avanco_automatico_segundos == 0
