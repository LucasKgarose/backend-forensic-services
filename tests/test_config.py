import os
import pytest
from app.config import Settings, ConfigurationError


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("ADB_PATH", "/usr/bin/adb")
    monkeypatch.setenv("CORS_ORIGINS", "[\"*"]")
    monkeypatch.setenv("SIGNING_KEY_PATH", "/tmp/key.pem")
    monkeypatch.setenv("SERVER_PORT", "8000")
    s = Settings()
    assert s.DATABASE_URL == "sqlite:///./test.db"
    assert s.ADB_PATH == "/usr/bin/adb"
    assert s.CORS_ORIGINS == ["*"]
    assert s.SIGNING_KEY_PATH == "/tmp/key.pem"
    assert s.SERVER_PORT == 8000


def test_settings_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ADB_PATH", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PATH", raising=False)
    with pytest.raises(ConfigurationError):
        Settings()
