import os
import pytest
from app.config import Settings, get_settings
from app.errors import ConfigurationError


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("ADB_PATH", "/usr/bin/adb")
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')
    monkeypatch.setenv("SIGNING_KEY_PATH", "/tmp/key.pem")
    monkeypatch.setenv("SERVER_PORT", "8000")
    s = get_settings()
    assert s.DATABASE_URL == "sqlite:///./test.db"
    assert s.ADB_PATH == "/usr/bin/adb"
    assert s.CORS_ORIGINS == ["*"]
    assert s.SIGNING_KEY_PATH == "/tmp/key.pem"
    assert s.SERVER_PORT == 8000


def test_settings_default_port(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("ADB_PATH", "/usr/bin/adb")
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')
    monkeypatch.setenv("SIGNING_KEY_PATH", "/tmp/key.pem")
    monkeypatch.delenv("SERVER_PORT", raising=False)
    s = get_settings()
    assert s.SERVER_PORT == 8000


def test_settings_missing_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ADB_PATH", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PATH", raising=False)
    monkeypatch.delenv("SERVER_PORT", raising=False)
    with pytest.raises(ConfigurationError, match="Missing required config"):
        get_settings()


def test_settings_missing_error_contains_key_name(monkeypatch):
    monkeypatch.setenv("ADB_PATH", "/usr/bin/adb")
    monkeypatch.setenv("CORS_ORIGINS", '["*"]')
    monkeypatch.setenv("SIGNING_KEY_PATH", "/tmp/key.pem")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SERVER_PORT", raising=False)
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        get_settings()
