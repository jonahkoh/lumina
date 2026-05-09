import uuid
from datetime import datetime

from app.models import TripType
from app.schemas import TripAuditCreate, AuditOutcome


def test_trip_type_enum_values():
    """TripType must have exactly DRIVER_ONLY, ESCORT_ONLY, COMBINED."""
    values = {t.value for t in TripType}
    assert values == {"DRIVER_ONLY", "ESCORT_ONLY", "COMBINED"}


def test_completed_audit_accepts_trip_type():
    """A COMPLETED audit can store trip_type; NO_MATCH audit leaves it null."""
    completed = TripAuditCreate(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        outcome=AuditOutcome.COMPLETED,
        trip_type=TripType.COMBINED,
        driver_id=uuid.uuid4(),
        escort_id=uuid.uuid4(),
        completed_at=datetime(2026, 6, 1, 11, 30),
    )
    assert completed.trip_type == TripType.COMBINED

    no_match = TripAuditCreate(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        outcome=AuditOutcome.NO_MATCH,
        reason="no_available_driver",
    )
    assert no_match.trip_type is None
