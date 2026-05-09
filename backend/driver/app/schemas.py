import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models import DriverStatus, VehicleType


class DriverCreate(BaseModel):
    provider_id: uuid.UUID
    provider_name: str
    provider_address: str
    provider_phone: str
    provider_location: dict
    service_areas: Optional[List[str]] = []
    name: str
    phone: str
    vehicle_type: VehicleType
    capability_flags: Optional[List[str]] = []
    availability_windows: Optional[List[dict]] = []


class DriverResponse(BaseModel):
    driver_id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str
    provider_address: str
    provider_phone: str
    provider_location: dict
    service_areas: Optional[List[str]] = None
    name: str
    phone: str
    vehicle_type: VehicleType
    capability_flags: Optional[List[str]] = None
    availability_windows: Optional[List[dict]] = None
    status: DriverStatus
    past_trip_ids: Optional[List[uuid.UUID]] = None
    future_trip_ids: Optional[List[uuid.UUID]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DriverWithScore(DriverResponse):
    match_score: float


class StatusUpdate(BaseModel):
    status: DriverStatus


class TripUpdate(BaseModel):
    add_future_trip_id: Optional[uuid.UUID] = None
    add_past_trip_id: Optional[uuid.UUID] = None
    remove_future_trip_id: Optional[uuid.UUID] = None
