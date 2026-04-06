from pydantic import BaseSettings, ValidationError
from typing import List, Optional
import os

class ConfigurationError(Exception):
    pass

class Settings(BaseSettings):
    DATABASE_URL: str
    ADB_PATH: str
    CORS_ORIGINS: List[str]
    SIGNING_KEY_PATH: str
    SERVER_PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as e:
        missing = [err['loc'][0] for err in e.errors() if err['type'] == 'value_error.missing']
        if missing:
            raise ConfigurationError(f"Missing required config: {', '.join(missing)}")
        raise
