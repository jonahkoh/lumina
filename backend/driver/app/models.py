import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func, text

from app.database import Base


class VehicleType(str, enum.Enum):
    STANDARD = "STANDARD"
    WHEELCHAIR_VAN = "WHEELCHAIR_VAN"
    STRETCHER = "STRETCHER"


class DriverStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class Driver(Base):
    __tablename__ = "drivers"

    driver_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), nullable=False)
    provider_name = Column(String, nullable=False)
    provider_address = Column(String, nullable=False)
    provider_phone = Column(String, nullable=False)
    provider_location = Column(JSONB, nullable=False)
    service_areas = Column(ARRAY(String))

    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    vehicle_type = Column(SAEnum(VehicleType, name="vehicletype"), nullable=False)
    capability_flags = Column(ARRAY(String))
    availability_windows = Column(JSONB)

    status = Column(
        SAEnum(DriverStatus, name="driverstatus"),
        nullable=False,
        default=DriverStatus.AVAILABLE,
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
