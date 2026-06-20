import uuid
from datetime import datetime

from app.schemas import TripRequest, MatchResult, Location


def test_trip_request_schema():
    """TripRequest parses correctly with optional fields defaulting to empty."""
    req = TripRequest(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        pickup_location=Location(lat=1.35, lng=103.82),
        dropoff_location=Location(lat=1.30, lng=103.85),
        appointment_datetime=datetime(2026, 6, 1, 10, 0),
    )
    assert req.mobility_flags == []
    assert req.elderly_needs == []
    assert req.preferred_languages == []
    assert req.preferred_ngo_id is None
    assert req.max_price is None


def test_match_result_no_match():
    """MatchResult with success=False carries a reason and no driver/escort ids."""
    result = MatchResult(success=False, reason="no_available_driver")
    assert result.success is False
    assert result.reason == "no_available_driver"
    assert result.driver_id is None
    assert result.escort_id is None
    assert result.estimated_price is None
