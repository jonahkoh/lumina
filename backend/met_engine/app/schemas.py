"""
MET Engine — Pydantic schemas.

All field names use snake_case and match the transport source of truth exactly:
  - trip_id, elderly_id, caregiver_id, driver_id, escort_id
  - provider_id, provider_name  (not ngo_id / ngo_name)
  - pickup_location / dropoff_location as {lat, lng} dicts
  - Kafka topics: trip.offered.driver, trip.offered.escort, trip.confirmed,
                  trip.no_match, trip.completed, trip.accepted.escort,
                  payment.initiated, payment.completed
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import TripType


# ── Kafka payloads consumed by MET Engine ────────────────────────────────────
# Source of truth: transport/app/main.py publish calls

class TripOfferedDriverPayload(BaseModel):
    """Received on topic: trip.offered.driver"""
    trip_id: uuid.UUID
    driver_id: uuid.UUID
    escort_id: Optional[uuid.UUID] = None
    vehicle_type: Optional[str] = None
    pickup_location: Optional[dict] = None
    dropoff_location: Optional[dict] = None
    appointment_datetime: Optional[str] = None
    elderly_needs: list[str] = []
    estimated_price: Optional[float] = None


class TripOfferedEscortPayload(BaseModel):
    """Received on topic: trip.offered.escort"""
    trip_id: uuid.UUID
    escort_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    pickup_location: Optional[dict] = None
    dropoff_location: Optional[dict] = None
    appointment_datetime: Optional[str] = None
    elderly_needs: list[str] = []


class TripAcceptedEscortPayload(BaseModel):
    """Received on topic: trip.accepted.escort"""
    trip_id: uuid.UUID
    escort_id: uuid.UUID
    accepted_at: Optional[str] = None


class TripConfirmedPayload(BaseModel):
    """Received on topic: trip.confirmed"""
    trip_id: uuid.UUID
    driver_id: uuid.UUID
    accepted_at: Optional[str] = None
    confirmed_at: str


class TripNoMatchPayload(BaseModel):
    """Received on topic: trip.no_match"""
    trip_id: uuid.UUID
    elderly_id: uuid.UUID
    caregiver_id: uuid.UUID
    reason: Optional[str] = None
    aic_hotline: Optional[str] = None
    attempted_at: str


class TripCompletedPayload(BaseModel):
    """Received on topic: trip.completed"""
    trip_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    escort_id: Optional[uuid.UUID] = None
    elderly_id: Optional[uuid.UUID] = None
    caregiver_id: Optional[uuid.UUID] = None
    trip_type: Optional[TripType] = None
    completed_at: str
    photo_url: Optional[str] = None
    dropoff_confirmed: Optional[bool] = None


class TripCancelledPayload(BaseModel):
    """Received on topic: trip.cancelled"""
    trip_id: uuid.UUID
    driver_id: Optional[uuid.UUID] = None
    escort_id: Optional[uuid.UUID] = None
    cancelled_at: str


class PaymentInitiatedPayload(BaseModel):
    """Received on topic: payment.initiated"""
    trip_id: uuid.UUID
    amount: float
    currency: str = "SGD"
    initiated_at: str


class PaymentCompletedPayload(BaseModel):
    """Received on topic: payment.completed"""
    trip_id: uuid.UUID
    amount: float
    currency: str = "SGD"
    completed_at: str


# ── Internal REST callbacks (Transport → MET Engine) ─────────────────────────
# Source of truth: transport/app/main.py _notify_met() call sites

class ConfirmedNotificationBody(BaseModel):
    driver_id: uuid.UUID
    confirmed_at: str


class ReachingNotificationBody(BaseModel):
    driver_id: Optional[uuid.UUID] = None
    escort_id: Optional[uuid.UUID] = None
    triggered_at: str
    type: str  # "driver" | "escort"


class CompletedNotificationBody(BaseModel):
    trip_id: uuid.UUID
    completed_at: str


# ── Bot → MET Engine (booking intake) ────────────────────────────────────────

class BookingRequest(BaseModel):
    """Bot submits a fully-resolved booking. MET Engine forwards to Transport."""
    trip_id: uuid.UUID
    elderly_id: uuid.UUID
    caregiver_id: uuid.UUID
    pickup_location: dict          # {lat: float, lng: float}
    dropoff_location: dict         # {lat: float, lng: float}
    appointment_datetime: str      # ISO 8601
    mobility_flags: list[str] = []
    elderly_needs: list[str] = []
    preferred_languages: list[str] = []
    service_area: Optional[str] = None
    provider_id: Optional[uuid.UUID] = None
    provider_name: Optional[str] = None
    max_price: Optional[float] = None


class BookingResponse(BaseModel):
    trip_id: uuid.UUID
    status: str


class CancelRequest(BaseModel):
    trip_id: uuid.UUID


class AckResponse(BaseModel):
    ok: bool = True
