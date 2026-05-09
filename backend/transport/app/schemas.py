import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class Location(BaseModel):
    lat: float
    lng: float


class TripRequest(BaseModel):
    trip_id: uuid.UUID
    elderly_id: uuid.UUID
    caregiver_id: uuid.UUID
    pickup_location: Location
    dropoff_location: Location
    appointment_datetime: datetime
    mobility_flags: list[str] = []
    elderly_needs: list[str] = []
    preferred_languages: list[str] = []
    preferred_ngo_id: Optional[uuid.UUID] = None
    max_price: Optional[float] = None
    service_area: Optional[str] = None


class TripNeeds(BaseModel):
    trip_id: uuid.UUID
    pickup_location: Location
    dropoff_location: Location
    appointment_datetime: datetime
    mobility_flags: list[str] = []
    elderly_needs: list[str] = []
    preferred_languages: list[str] = []
    service_area: Optional[str] = None


class DriverMatch(BaseModel):
    driver_id: uuid.UUID
    vehicle_type: str
    match_score: float


class EscortMatch(BaseModel):
    escort_id: uuid.UUID
    match_score: float


class MatchResult(BaseModel):
    success: bool
    driver_id: Optional[uuid.UUID] = None
    escort_id: Optional[uuid.UUID] = None
    vehicle_type: Optional[str] = None
    estimated_price: Optional[float] = None
    reason: Optional[str] = None


class TripStatusResponse(BaseModel):
    trip_id: uuid.UUID
    has_candidates: bool
    confirmed: bool


class ReachingBody(BaseModel):
    actor_id: uuid.UUID
    actor_type: str  # "driver" | "escort"


class CancelResponse(BaseModel):
    trip_id: uuid.UUID
    cancelled_at: datetime


class TripAcceptedResponse(BaseModel):
    trip_id: uuid.UUID
    status: str
