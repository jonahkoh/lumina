import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func, text

from app.database import Base


class EscortStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class Escort(Base):
    __tablename__ = "escorts"

    escort_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), nullable=False)
    provider_name = Column(String, nullable=False)
    provider_address = Column(String, nullable=False)
    provider_phone = Column(String, nullable=False)
    provider_location = Column(JSONB, nullable=False)
    service_areas = Column(ARRAY(String))

    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    languages = Column(ARRAY(String))
    specialisations = Column(ARRAY(String))
    availability_windows = Column(JSONB)

    status = Column(
        SAEnum(EscortStatus, name="escortstatus"),
        nullable=False,
        default=EscortStatus.AVAILABLE,
    )
    past_trip_ids = Column(
        ARRAY(UUID(as_uuid=True)),
        server_default=text("'{}'::uuid[]"),
        default=list,
    )
    future_trip_ids = Column(
        ARRAY(UUID(as_uuid=True)),
        server_default=text("'{}'::uuid[]"),
        default=list,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
