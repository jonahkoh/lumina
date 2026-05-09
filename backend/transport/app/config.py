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
    REDIS_URL: str = "redis://localhost:6379/0"
    DRIVER_SERVICE_URL: str = "http://localhost:8001"
    ESCORT_SERVICE_URL: str = "http://localhost:8002"
    TRIP_AUDIT_SERVICE_URL: str = "http://localhost:8003"
    MET_ENGINE_URL: str = "http://localhost:8010"

    model_config = SettingsConfigDict(env_file=_find_env_file(), extra="ignore")


settings = Settings()
