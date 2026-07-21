import importlib
import sys
from unittest.mock import patch

import pytest


def _reload_config(monkeypatch, **values):
    for key in ["ENVIRONMENT", "BOT_TOKEN", "ADMIN_IDS", "DATABASE_URL", "REDIS_URL", "DB_POOL_SIZE", "DB_MAX_OVERFLOW"]:
        monkeypatch.delenv(key, raising=False)

    for key, value in values.items():
        monkeypatch.setenv(key, value)

    sys.modules.pop("config", None)
    # Prevent dotenv.load_dotenv from reading .env files during config import
    with patch("dotenv.load_dotenv", lambda *args, **kwargs: None):
        return importlib.import_module("config")


def test_admin_ids_falls_back_to_empty_list(monkeypatch):
    config = _reload_config(
        monkeypatch,
        ENVIRONMENT="development",
        BOT_TOKEN="123456:TESTTOKEN",
    )

    assert config.ADMIN_IDS == []
    assert isinstance(config.ADMIN_IDS, list)


def test_missing_bot_token_fails_fast(monkeypatch):
    with pytest.raises(ValueError, match="BOT_TOKEN is not set"):
        _reload_config(
            monkeypatch,
            ENVIRONMENT="development",
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/schoolbridge",
        )