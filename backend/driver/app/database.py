from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Walk up from this file's location to find the nearest .env (project root)."""
    p = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = p / ".env"
        if candidate.exists():
            return str(candidate)
        parent = p.parent
        if parent == p:
            break
        p = parent
    return ".env"  # fallback: pydantic-settings silently skips if missing


class Settings(BaseSettings):
    POSTGRES_USER: str = "admin"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_API_KEY: str = ""
    KAFKA_API_SECRET: str = ""

    model_config = SettingsConfigDict(env_file=_find_env_file(), extra="ignore")


settings = Settings()

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/driver-db"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
