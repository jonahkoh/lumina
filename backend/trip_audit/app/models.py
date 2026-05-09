import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.database import Base


class AuditOutcome(str, enum.Enum):
    COMPLETED = "COMPLETED"
    NO_MATCH = "NO_MATCH"
    CANCELLED = "CANCELLED"


class TripType(str, enum.Enum):
    DRIVER_ONLY = "DRIVER_ONLY"
    ESCORT_ONLY = "ESCORT_ONLY"
    COMBINED = "COMBINED"


class TripAudit(Base):
    __tablename__ = "trip_audits"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    elderly_id = Column(UUID(as_uuid=True), nullable=False)
    caregiver_id = Column(UUID(as_uuid=True), nullable=False)
    outcome = Column(SAEnum(AuditOutcome, name="auditoutcome"), nullable=False)

    driver_id = Column(UUID(as_uuid=True), nullable=True)
    escort_id = Column(UUID(as_uuid=True), nullable=True)
    provider_id = Column(UUID(as_uuid=True), nullable=True)
    provider_name = Column(String, nullable=True)

    pickup_location = Column(JSONB, nullable=True)
    dropoff_location = Column(JSONB, nullable=True)
    appointment_datetime = Column(DateTime(timezone=True), nullable=True)

    photo_url = Column(String, nullable=True)
    dropoff_confirmed = Column(Boolean, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    trip_type = Column(SAEnum(TripType, name="triptype"), nullable=True)
    reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
