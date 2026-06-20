import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas import TripAuditCreate, AuditOutcome


def test_completed_record_has_all_fields():
    """A COMPLETED audit carries all completion fields."""
    record = TripAuditCreate(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        outcome=AuditOutcome.COMPLETED,
        driver_id=uuid.uuid4(),
        escort_id=uuid.uuid4(),
        provider_id=uuid.uuid4(),
        provider_name="SunCare",
        pickup_location={"lat": 1.35, "lng": 103.82},
        dropoff_location={"lat": 1.30, "lng": 103.85},
        appointment_datetime=datetime(2026, 5, 12, 10, 0),
        photo_url="https://example.com/photo.jpg",
        dropoff_confirmed=True,
        completed_at=datetime(2026, 5, 12, 11, 30),
    )
    assert record.outcome == AuditOutcome.COMPLETED
    assert record.dropoff_confirmed is True
    assert record.reason is None


def test_invalid_outcome_rejected():
    """Outcome must be one of the three valid values."""
    with pytest.raises(ValidationError):
        TripAuditCreate(
            trip_id=uuid.uuid4(),
            elderly_id=uuid.uuid4(),
            caregiver_id=uuid.uuid4(),
            outcome="PENDING",  # not a valid AuditOutcome
        )
