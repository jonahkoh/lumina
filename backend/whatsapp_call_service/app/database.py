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
    elderly_columns = (
        {column["name"] for column in inspector.get_columns("elderly_profiles")}
        if "elderly_profiles" in inspector.get_table_names()
        else set()
    )
    transport_trip_columns = (
        {column["name"] for column in inspector.get_columns("transport_trips")}
        if "transport_trips" in inspector.get_table_names()
        else set()
    )
    with engine.begin() as connection:
        if "role" not in contact_columns:
            connection.execute(text("ALTER TABLE contacts ADD COLUMN role VARCHAR(32)"))
        if "language_preference" not in contact_columns:
            connection.execute(text("ALTER TABLE contacts ADD COLUMN language_preference VARCHAR(64) DEFAULT 'english'"))
        if "message_text" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN message_text TEXT"))
        if "caregiver_message_text" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN caregiver_message_text TEXT"))
        if "appointment_location" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN appointment_location TEXT"))
        if "language" not in scheduled_call_columns:
            connection.execute(text("ALTER TABLE scheduled_calls ADD COLUMN language VARCHAR(64) DEFAULT 'english'"))
        if "citizenship" not in elderly_columns:
            connection.execute(text("ALTER TABLE elderly_profiles ADD COLUMN citizenship VARCHAR(128)"))
        if "income_level" not in elderly_columns:
            connection.execute(text("ALTER TABLE elderly_profiles ADD COLUMN income_level VARCHAR(128)"))
        if "dialects" not in elderly_columns:
            connection.execute(text("ALTER TABLE elderly_profiles ADD COLUMN dialects TEXT"))
        if "transport_mode_preference" not in elderly_columns:
            connection.execute(text("ALTER TABLE elderly_profiles ADD COLUMN transport_mode_preference VARCHAR(128)"))
        if "appointment_time_text" not in elderly_columns:
            connection.execute(text("ALTER TABLE elderly_profiles ADD COLUMN appointment_time_text TEXT"))
        if transport_trip_columns and "status_updated_at" not in transport_trip_columns:
            connection.execute(text("ALTER TABLE transport_trips ADD COLUMN status_updated_at DATETIME"))
