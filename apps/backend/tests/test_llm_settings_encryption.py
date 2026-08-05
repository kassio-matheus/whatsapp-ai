import pytest

from app.core.config import settings
from app.modules.ai.llm_settings import (
    _decryption_secrets,
    _encryption_secret,
    decrypt_value,
    encrypt_value,
)


@pytest.fixture(autouse=True)
def _restore_settings():
    original = {
        "SECRET_KEY": settings.SECRET_KEY,
        "AI_SETTINGS_ENCRYPTION_KEY": settings.AI_SETTINGS_ENCRYPTION_KEY,
        "AI_SETTINGS_ENCRYPTION_KEYS": list(
            settings.AI_SETTINGS_ENCRYPTION_KEYS),
    }
    yield
    for name, value in original.items():
        setattr(settings, name, value)


def test_encrypt_decrypt_roundtrip():
    ciphertext = encrypt_value("sk-secret")
    assert ciphertext != "sk-secret"
    assert decrypt_value(ciphertext) == "sk-secret"


def test_decrypt_none_or_empty_returns_none():
    assert decrypt_value(None) is None
    assert decrypt_value("") is None


def test_different_secrets_do_not_decrypt():
    settings.AI_SETTINGS_ENCRYPTION_KEY = "a" * 44
    settings.AI_SETTINGS_ENCRYPTION_KEYS = []
    ciphertext = encrypt_value("sk-secret")
    settings.AI_SETTINGS_ENCRYPTION_KEY = "b" * 44
    assert decrypt_value(ciphertext) is None


def test_dedicated_key_survives_secret_key_rotation():
    settings.AI_SETTINGS_ENCRYPTION_KEY = "a" * 44
    ciphertext = encrypt_value("sk-secret")
    settings.SECRET_KEY = "x" * 44
    assert _encryption_secret() == "a" * 44
    assert decrypt_value(ciphertext) == "sk-secret"


def test_legacy_encryption_keys_are_tried_for_decryption():
    legacy = "a" * 44
    settings.AI_SETTINGS_ENCRYPTION_KEY = legacy
    ciphertext = encrypt_value("sk-secret")
    settings.AI_SETTINGS_ENCRYPTION_KEY = "b" * 44
    settings.AI_SETTINGS_ENCRYPTION_KEYS = [legacy]
    assert decrypt_value(ciphertext) == "sk-secret"


def test_keys_encrypted_with_plain_secret_key_still_decrypt():
    settings.AI_SETTINGS_ENCRYPTION_KEY = ""
    settings.AI_SETTINGS_ENCRYPTION_KEYS = []
    ciphertext = encrypt_value("sk-secret")
    settings.AI_SETTINGS_ENCRYPTION_KEY = "c" * 44
    settings.AI_SETTINGS_ENCRYPTION_KEYS = []
    assert decrypt_value(ciphertext) == "sk-secret"
    assert settings.SECRET_KEY in _decryption_secrets()
