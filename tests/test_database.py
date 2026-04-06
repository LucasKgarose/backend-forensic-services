import os
import pytest
from unittest.mock import patch
from app.database import Base, get_engine, get_session_factory, get_db, _engine, _SessionLocal
import app.database as db_module


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset cached engine and session factory between tests."""
    db_module._engine = None
    db_module._SessionLocal = None
    yield
    db_module._engine = None
    db_module._SessionLocal = None


def test_base_is_available_at_module_level():
    """Base should be importable without triggering settings loading."""
    assert Base is not None
    assert hasattr(Base, "metadata")


def test_get_engine_creates_engine():
    """get_engine should lazily create an engine using settings."""
    env = {
        "DATABASE_URL": "sqlite:///./test_lazy.db",
        "ADB_PATH": "/usr/bin/adb",
        "CORS_ORIGINS": '["http://localhost:3000"]',
        "SIGNING_KEY_PATH": "/tmp/key.pem",
    }
    with patch.dict(os.environ, env, clear=False):
        engine = get_engine()
        assert engine is not None
        assert str(engine.url) == "sqlite:///./test_lazy.db"
        # Second call returns the same cached engine
        assert get_engine() is engine


def test_get_session_factory_creates_sessionmaker():
    """get_session_factory should return a cached sessionmaker."""
    env = {
        "DATABASE_URL": "sqlite:///:memory:",
        "ADB_PATH": "/usr/bin/adb",
        "CORS_ORIGINS": '["http://localhost:3000"]',
        "SIGNING_KEY_PATH": "/tmp/key.pem",
    }
    with patch.dict(os.environ, env, clear=False):
        factory = get_session_factory()
        assert factory is not None
        assert get_session_factory() is factory


def test_get_db_yields_session_and_closes():
    """get_db should yield a usable session and close it after."""
    env = {
        "DATABASE_URL": "sqlite:///:memory:",
        "ADB_PATH": "/usr/bin/adb",
        "CORS_ORIGINS": '["http://localhost:3000"]',
        "SIGNING_KEY_PATH": "/tmp/key.pem",
    }
    with patch.dict(os.environ, env, clear=False):
        gen = get_db()
        session = next(gen)
        assert session is not None
        # Closing the generator should not raise
        try:
            next(gen)
        except StopIteration:
            pass
