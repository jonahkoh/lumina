import uuid

import pytest
from pydantic import ValidationError

from app.schemas import TripAuditCreate, TripAuditResponse, AuditOutcome


def test_audit_outcome_values():
    """AuditOutcome must have exactly COMPLETED, NO_MATCH, CANCELLED."""
    values = {o.value for o in AuditOutcome}
    assert values == {"COMPLETED", "NO_MATCH", "CANCELLED"}


def test_no_match_record_all_nulls_allowed():
    """A NO_MATCH audit can be created with all optional fields left null."""
    record = TripAuditCreate(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        outcome=AuditOutcome.NO_MATCH,
        reason="no_available_driver",
    )
    assert record.driver_id is None
    assert record.escort_id is None
    assert record.photo_url is None
    assert record.completed_at is None
