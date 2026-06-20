import uuid
from app.schemas import TripAuditCreate, AuditOutcome


def test_cancelled_audit_stores_driver_and_escort():
    """CANCELLED audit can store driver_id and escort_id for accountability."""
    driver_id = uuid.uuid4()
    escort_id = uuid.uuid4()
    record = TripAuditCreate(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        outcome=AuditOutcome.CANCELLED,
        driver_id=driver_id,
        escort_id=escort_id,
        reason="caregiver_cancelled",
    )
    assert record.driver_id == driver_id
    assert record.escort_id == escort_id
    assert record.trip_type is None
    assert record.completed_at is None
    assert record.photo_url is None


def test_cancelled_audit_allows_null_driver_escort():
    """CANCELLED audit is valid even when no driver or escort was ever assigned."""
    record = TripAuditCreate(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        outcome=AuditOutcome.CANCELLED,
    )
    assert record.driver_id is None
    assert record.escort_id is None
