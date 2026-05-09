import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_pk() -> uuid.UUID:
    return uuid.uuid4()


def json_type():
    return JSON().with_variant(JSONB, "postgresql")


class ConversationState(str, enum.Enum):
    idle = "idle"
    awaiting_recipient = "awaiting_recipient"
    awaiting_time = "awaiting_time"
    awaiting_confirmation = "awaiting_confirmation"


class MessageStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"


class ScheduledCallStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    whatsapp_address: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opted_in: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sessions: Mapped[list["ConversationSession"]] = relationship(back_populates="contact")


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), index=True)
    state: Mapped[ConversationState] = mapped_column(Enum(ConversationState), default=ConversationState.idle)
    data: Mapped[dict] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    contact: Mapped[Contact] = relationship(back_populates="sessions")


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    to_whatsapp: Mapped[str] = mapped_column(String(48), index=True)
    body: Mapped[str] = mapped_column(Text)
    twilio_sid: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.queued)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def to(self) -> str:
        return self.to_whatsapp


class ScheduledCall(Base):
    __tablename__ = "scheduled_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    to_phone_number: Mapped[str] = mapped_column(String(32), index=True)
    requested_by_whatsapp: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    audio_url: Mapped[str] = mapped_column(Text)
    twilio_call_sid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[ScheduledCallStatus] = mapped_column(
        Enum(ScheduledCallStatus), default=ScheduledCallStatus.pending, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TwilioEvent(Base):
    __tablename__ = "twilio_events"
    __table_args__ = (UniqueConstraint("event_key", name="uq_twilio_events_event_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    event_key: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
