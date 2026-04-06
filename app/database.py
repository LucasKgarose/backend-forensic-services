from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator

Base = declarative_base()

_engine = None
_SessionLocal = None


def get_engine():
    """Lazily create and cache the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()
        _engine = create_engine(settings.DATABASE_URL, future=True, echo=True)
    return _engine


def get_session_factory():
    """Lazily create and cache the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine(), future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
