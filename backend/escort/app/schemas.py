import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

from app.models import EscortStatus

VALID_LANGUAGES = {"english", "chinese", "malay", "tamil"}


class EscortCreate(BaseModel):
    provider_id: uuid.UUID
    provider_name: str
    provider_address: str
    provider_phone: str
    provider_location: dict
    service_areas: Optional[List[str]] = []
    name: str
    phone: str
    languages: List[str]
    specialisations: Optional[List[str]] = []
    availability_windows: Optional[List[dict]] = []

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, v: List[str]) -> List[str]:
        invalid = set(v) - VALID_LANGUAGES
        if invalid:
            raise ValueError(f"Invalid languages: {invalid}. Allowed: {VALID_LANGUAGES}")
        return v


class EscortResponse(BaseModel):
    escort_id: uuid.UUID
    provider_id: uuid.UUID
    provider_name: str
    provider_address: str
    provider_phone: str
    provider_location: dict
    service_areas: Optional[List[str]] = None
    name: str
    phone: str
    languages: Optional[List[str]] = None
    specialisations: Optional[List[str]] = None
    availability_windows: Optional[List[dict]] = None
    status: EscortStatus
    past_trip_ids: Optional[List[uuid.UUID]] = None
    future_trip_ids: Optional[List[uuid.UUID]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EscortWithScore(EscortResponse):
    match_score: float


class StatusUpdate(BaseModel):
    status: EscortStatus


class TripUpdate(BaseModel):
    add_future_trip_id: Optional[uuid.UUID] = None
    add_past_trip_id: Optional[uuid.UUID] = None
    remove_future_trip_id: Optional[uuid.UUID] = None


class RejectBody(BaseModel):
    reason: Optional[str] = None
