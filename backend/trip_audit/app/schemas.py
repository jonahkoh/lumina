import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import AuditOutcome, TripType


class TripAuditCreate(BaseModel):
    trip_id: uuid.UUID
    elderly_id: uuid.UUID
    caregiver_id: uuid.UUID
    outcome: AuditOutcome

    driver_id: Optional[uuid.UUID] = None
    escort_id: Optional[uuid.UUID] = None
    provider_id: Optional[uuid.UUID] = None
    provider_name: Optional[str] = None

    pickup_location: Optional[dict] = None
    dropoff_location: Optional[dict] = None
    appointment_datetime: Optional[datetime] = None

    photo_url: Optional[str] = None
    dropoff_confirmed: Optional[bool] = None
    completed_at: Optional[datetime] = None

    trip_type: Optional[TripType] = None
    reason: Optional[str] = None


class TripAuditResponse(BaseModel):
    audit_id: uuid.UUID
    trip_id: uuid.UUID
    elderly_id: uuid.UUID
    caregiver_id: uuid.UUID
    outcome: AuditOutcome

    driver_id: Optional[uuid.UUID] = None
    escort_id: Optional[uuid.UUID] = None
    provider_id: Optional[uuid.UUID] = None
    provider_name: Optional[str] = None

    pickup_location: Optional[dict] = None
    dropoff_location: Optional[dict] = None
    appointment_datetime: Optional[datetime] = None

    photo_url: Optional[str] = None
    dropoff_confirmed: Optional[bool] = None
    completed_at: Optional[datetime] = None

    trip_type: Optional[TripType] = None
    reason: Optional[str] = None

    created_at: datetime

    model_config = {"from_attributes": True}
