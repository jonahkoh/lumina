from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    p = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = p / ".env"
        if candidate.exists():
            return str(candidate)
        parent = p.parent
        if parent == p:
            break
        p = parent
    return ".env"


class Settings(BaseSettings):
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_API_KEY: str = ""
    KAFKA_API_SECRET: str = ""
    TRANSPORT_SERVICE_URL: str = "http://localhost:8000"
    BOT_SERVICE_URL: str = "http://localhost:8004"

    model_config = SettingsConfigDict(env_file=_find_env_file(), extra="ignore")


settings = Settings()
