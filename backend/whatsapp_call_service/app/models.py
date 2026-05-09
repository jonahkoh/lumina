import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from sqlalchemy.types import JSON

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_pk() -> uuid.UUID:
    return uuid.uuid4()


def json_type():
    return JSON()


class ConversationState(str, enum.Enum):
    idle = "idle"
    awaiting_role = "awaiting_role"
    awaiting_caregiver_name = "awaiting_caregiver_name"
    awaiting_caregiver_language = "awaiting_caregiver_language"
    awaiting_relationship = "awaiting_relationship"
    awaiting_elderly_name = "awaiting_elderly_name"
    awaiting_elderly_phone = "awaiting_elderly_phone"
    awaiting_pickup_address = "awaiting_pickup_address"
    awaiting_postal_code = "awaiting_postal_code"
    awaiting_elderly_language = "awaiting_elderly_language"
    awaiting_mobility = "awaiting_mobility"
    awaiting_notes = "awaiting_notes"
    awaiting_profile_confirmation = "awaiting_profile_confirmation"
    awaiting_elderly_selection = "awaiting_elderly_selection"
    awaiting_recipient = "awaiting_recipient"
    awaiting_time = "awaiting_time"
    awaiting_appointment_location = "awaiting_appointment_location"
    awaiting_confirmation = "awaiting_confirmation"
    awaiting_ocr_confirmation = "awaiting_ocr_confirmation"


class ContactRole(str, enum.Enum):
    caregiver = "caregiver"
    elderly = "elderly"


class MobilityLevel(str, enum.Enum):
    need_transport = "need_transport"
    need_escort = "need_escort"
    need_both = "need_both"
    independent = "independent"
    walking_aid = "walking_aid"
    wheelchair = "wheelchair"
    escort_support = "escort_support"


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
    role: Mapped[ContactRole | None] = mapped_column(Enum(ContactRole), nullable=True, index=True)
    language_preference: Mapped[str] = mapped_column(String(64), default="english")
    opted_in: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sessions: Mapped[list["ConversationSession"]] = orm_relationship(back_populates="contact")
    caregiver_profile: Mapped["CaregiverProfile | None"] = orm_relationship(back_populates="contact")
    elderly_profile: Mapped["ElderlyProfile | None"] = orm_relationship(
        back_populates="contact", foreign_keys="ElderlyProfile.contact_id"
    )


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), index=True)
    state: Mapped[ConversationState] = mapped_column(Enum(ConversationState), default=ConversationState.idle)
    data: Mapped[dict] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    contact: Mapped[Contact] = orm_relationship(back_populates="sessions")


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


class CaregiverProfile(Base):
    __tablename__ = "caregiver_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(32), index=True)
    preferred_language: Mapped[str] = mapped_column(String(64), default="english")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    contact: Mapped[Contact] = orm_relationship(back_populates="caregiver_profile")
    elderly_links: Mapped[list["CaregiverElderlyLink"]] = orm_relationship(
        back_populates="caregiver", cascade="all, delete-orphan"
    )


class ElderlyProfile(Base):
    __tablename__ = "elderly_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"), unique=True, nullable=True, index=True)
    created_by_contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(32), index=True)
    pickup_address: Mapped[str] = mapped_column(Text)
    postal_code: Mapped[str] = mapped_column(String(16), index=True)
    preferred_language: Mapped[str] = mapped_column(String(64), default="english")
    mobility_level: Mapped[MobilityLevel] = mapped_column(Enum(MobilityLevel), default=MobilityLevel.need_transport)
    citizenship: Mapped[str | None] = mapped_column(String(128), nullable=True)
    income_level: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dialects: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport_mode_preference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    appointment_time_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    contact: Mapped[Contact | None] = orm_relationship(back_populates="elderly_profile", foreign_keys=[contact_id])
    created_by_contact: Mapped[Contact | None] = orm_relationship(foreign_keys=[created_by_contact_id])
    caregiver_links: Mapped[list["CaregiverElderlyLink"]] = orm_relationship(
        back_populates="elderly", cascade="all, delete-orphan"
    )


class CaregiverElderlyLink(Base):
    __tablename__ = "caregiver_elderly_links"
    __table_args__ = (
        UniqueConstraint("caregiver_profile_id", "elderly_profile_id", name="uq_caregiver_elderly_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    caregiver_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caregiver_profiles.id"), index=True)
    elderly_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("elderly_profiles.id"), index=True)
    relationship: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    caregiver: Mapped[CaregiverProfile] = orm_relationship(back_populates="elderly_links")
    elderly: Mapped[ElderlyProfile] = orm_relationship(back_populates="caregiver_links")


class ScheduledCall(Base):
    __tablename__ = "scheduled_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_pk)
    to_phone_number: Mapped[str] = mapped_column(String(32), index=True)
    requested_by_whatsapp: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    audio_url: Mapped[str] = mapped_column(Text)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    appointment_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(64), default="english")
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
