from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    """Keep local/dev databases compatible until proper Alembic migrations exist."""
    inspector = inspect(engine)
    if "contacts" not in inspector.get_table_names():
        return

    contact_columns = {column["name"] for column in inspector.get_columns("contacts")}
    scheduled_call_columns = (
        {column["name"] for column in inspector.get_columns("scheduled_calls")}
        if "scheduled_calls" in inspector.get_table_names()
        else set()
    )
    with engine.begin() as connection:
        if "role" not in contact_columns:
            connection.execute(text("ALTER TABLE contacts ADD COLUMN role VARCHAR(32)"))
        if "message_text" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN message_text TEXT"))
        if "appointment_location" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN appointment_location TEXT"))
        if "language" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN language VARCHAR(64) DEFAULT 'english'"))
