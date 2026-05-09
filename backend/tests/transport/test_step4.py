import uuid
from datetime import datetime

from pydantic import ValidationError
import pytest

from app.schemas import ReachingBody, TripRequest, Location


def test_reaching_body_valid_actor_types():
    """ReachingBody accepts driver and escort as actor_type."""
    body_driver = ReachingBody(actor_id=uuid.uuid4(), actor_type="driver")
    body_escort = ReachingBody(actor_id=uuid.uuid4(), actor_type="escort")
    assert body_driver.actor_type == "driver"
    assert body_escort.actor_type == "escort"


def test_trip_request_serialises_to_json():
    """TripRequest.model_dump(mode='json') produces JSON-safe dict for Kafka publish."""
    trip_id = uuid.uuid4()
    req = TripRequest(
        trip_id=trip_id,
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        pickup_location=Location(lat=1.35, lng=103.82),
        dropoff_location=Location(lat=1.30, lng=103.85),
        appointment_datetime=datetime(2026, 6, 1, 10, 0),
        mobility_flags=["wheelchair"],
    )
    data = req.model_dump(mode="json")
    assert data["trip_id"] == str(trip_id)
    assert data["pickup_location"] == {"lat": 1.35, "lng": 103.82}
    assert isinstance(data["appointment_datetime"], str)
