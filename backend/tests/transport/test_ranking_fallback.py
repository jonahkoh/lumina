"""
Tests for driver/escort rejection fallback (ranking feature).

Covers:
- Re-offer to next driver when first driver rejects
- Re-offer to next escort when first escort rejects
- trip.no_match + AIC hotline when all drivers exhausted
- trip.no_match + AIC hotline when all escorts exhausted
- trip context stored and cleaned up on match_trip
- update_trip_assignment patches only the specified field
"""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.matching import (
    cleanup_trip_redis,
    get_trip_context,
    store_trip_context,
    update_trip_assignment,
)
from app.main import (
    AIC_HOTLINE,
    _handle_trip_rejected_driver,
    _handle_trip_rejected_escort,
)
from app.schemas import Location, TripRequest


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_trip_request(**overrides) -> TripRequest:
    defaults = dict(
        trip_id=uuid.uuid4(),
        elderly_id=uuid.uuid4(),
        caregiver_id=uuid.uuid4(),
        pickup_location=Location(lat=1.3, lng=103.8),
        dropoff_location=Location(lat=1.35, lng=103.85),
        appointment_datetime=__import__("datetime").datetime(2026, 6, 1, 9, 0),
        mobility_flags=[],
        elderly_needs=[],
        preferred_languages=[],
    )
    defaults.update(overrides)
    return TripRequest(**defaults)


# ── store_trip_context ────────────────────────────────────────────────────────

def test_store_trip_context_writes_all_fields():
    trip = _make_trip_request(mobility_flags=["wheelchair"])
    stored = {}

    class FakeRedis:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def set(self, key, val): stored[key] = json.loads(val)
        async def expire(self, *a): pass

    with patch("app.matching._redis", return_value=FakeRedis()):
        asyncio.run(store_trip_context(trip.trip_id, trip))

    ctx = stored[f"trip:context:{trip.trip_id}"]
    assert ctx["vehicle_type"] == "WHEELCHAIR_VAN"
    assert ctx["pickup_location"] == {"lat": 1.3, "lng": 103.8}
    assert ctx["elderly_id"] == str(trip.elderly_id)
    assert ctx["caregiver_id"] == str(trip.caregiver_id)
    assert ctx["estimated_price"] == 35.0


# ── update_trip_assignment ────────────────────────────────────────────────────

def test_update_trip_assignment_patches_driver_id():
    trip_id = uuid.uuid4()
    old_driver = str(uuid.uuid4())
    new_driver = str(uuid.uuid4())
    escort_id = str(uuid.uuid4())

    original = json.dumps({"driver_id": old_driver, "escort_id": escort_id,
                           "elderly_id": None, "caregiver_id": None})
    stored = {}

    class FakeRedis:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, key): return original
        async def set(self, key, val): stored[key] = json.loads(val)
        async def expire(self, *a): pass

    with patch("app.matching._redis", return_value=FakeRedis()):
        asyncio.run(update_trip_assignment(trip_id, driver_id=new_driver))

    result = stored[f"trip:assignment:{trip_id}"]
    assert result["driver_id"] == new_driver
    assert result["escort_id"] == escort_id  # unchanged


# ── cleanup_trip_redis ────────────────────────────────────────────────────────

def test_cleanup_deletes_context_key():
    trip_id = uuid.uuid4()
    deleted = []

    class FakeRedis:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def delete(self, *keys): deleted.extend(keys)

    with patch("app.matching._redis", return_value=FakeRedis()):
        asyncio.run(cleanup_trip_redis(trip_id))

    assert f"trip:context:{trip_id}" in deleted


# ── _handle_trip_rejected_driver ──────────────────────────────────────────────

def test_rejected_driver_reoffers_to_next():
    trip_id = uuid.uuid4()
    next_driver = str(uuid.uuid4())
    escort_id = str(uuid.uuid4())
    assignment = {"driver_id": str(uuid.uuid4()), "escort_id": escort_id,
                  "elderly_id": str(uuid.uuid4()), "caregiver_id": str(uuid.uuid4())}
    context = {
        "vehicle_type": "STANDARD",
        "pickup_location": {"lat": 1.3, "lng": 103.8},
        "dropoff_location": {"lat": 1.35, "lng": 103.85},
        "appointment_datetime": "2026-06-01T09:00:00",
        "elderly_needs": [],
        "estimated_price": 20.0,
    }
    published = []

    with (
        patch("app.main.pop_next_driver", return_value=next_driver),
        patch("app.main.get_trip_context", return_value=context),
        patch("app.main.get_trip_assignment", return_value=assignment),
        patch("app.main.update_trip_assignment", new_callable=AsyncMock),
        patch("app.main.publish", side_effect=lambda topic, data: published.append((topic, data))),
    ):
        asyncio.run(_handle_trip_rejected_driver({"trip_id": str(trip_id)}))

    assert len(published) == 1
    topic, msg = published[0]
    assert topic == "trip.offered.driver"
    assert msg["driver_id"] == next_driver
    assert msg["escort_id"] == escort_id
    assert msg["pickup_location"] == context["pickup_location"]


def test_rejected_driver_no_match_with_aic_hotline():
    trip_id = uuid.uuid4()
    elderly_id = str(uuid.uuid4())
    caregiver_id = str(uuid.uuid4())
    assignment = {"driver_id": None, "escort_id": None,
                  "elderly_id": elderly_id, "caregiver_id": caregiver_id}
    published = []

    with (
        patch("app.main.pop_next_driver", return_value=None),
        patch("app.main.get_trip_assignment", return_value=assignment),
        patch("app.main.cleanup_trip_redis", new_callable=AsyncMock),
        patch("app.main.publish", side_effect=lambda topic, data: published.append((topic, data))),
    ):
        asyncio.run(_handle_trip_rejected_driver({"trip_id": str(trip_id)}))

    assert len(published) == 1
    topic, msg = published[0]
    assert topic == "trip.no_match"
    assert msg["reason"] == "no_available_driver"
    assert msg["elderly_id"] == elderly_id
    assert msg["caregiver_id"] == caregiver_id
    assert msg["aic_hotline"] == AIC_HOTLINE


# ── _handle_trip_rejected_escort ──────────────────────────────────────────────

def test_rejected_escort_reoffers_to_next():
    trip_id = uuid.uuid4()
    next_escort = str(uuid.uuid4())
    driver_id = str(uuid.uuid4())
    assignment = {"driver_id": driver_id, "escort_id": str(uuid.uuid4()),
                  "elderly_id": str(uuid.uuid4()), "caregiver_id": str(uuid.uuid4())}
    context = {
        "pickup_location": {"lat": 1.3, "lng": 103.8},
        "dropoff_location": {"lat": 1.35, "lng": 103.85},
        "appointment_datetime": "2026-06-01T09:00:00",
        "elderly_needs": [],
    }
    published = []

    with (
        patch("app.main.pop_next_escort", return_value=next_escort),
        patch("app.main.get_trip_context", return_value=context),
        patch("app.main.get_trip_assignment", return_value=assignment),
        patch("app.main.update_trip_assignment", new_callable=AsyncMock),
        patch("app.main.publish", side_effect=lambda topic, data: published.append((topic, data))),
    ):
        asyncio.run(_handle_trip_rejected_escort({"trip_id": str(trip_id)}))

    assert len(published) == 1
    topic, msg = published[0]
    assert topic == "trip.offered.escort"
    assert msg["escort_id"] == next_escort
    assert msg["driver_id"] == driver_id
    assert msg["pickup_location"] == context["pickup_location"]


def test_rejected_escort_no_match_with_aic_hotline():
    trip_id = uuid.uuid4()
    elderly_id = str(uuid.uuid4())
    caregiver_id = str(uuid.uuid4())
    assignment = {"driver_id": None, "escort_id": None,
                  "elderly_id": elderly_id, "caregiver_id": caregiver_id}
    published = []

    with (
        patch("app.main.pop_next_escort", return_value=None),
        patch("app.main.get_trip_assignment", return_value=assignment),
        patch("app.main.cleanup_trip_redis", new_callable=AsyncMock),
        patch("app.main.publish", side_effect=lambda topic, data: published.append((topic, data))),
    ):
        asyncio.run(_handle_trip_rejected_escort({"trip_id": str(trip_id)}))

    assert len(published) == 1
    topic, msg = published[0]
    assert topic == "trip.no_match"
    assert msg["reason"] == "no_available_escort"
    assert msg["elderly_id"] == elderly_id
    assert msg["caregiver_id"] == caregiver_id
    assert msg["aic_hotline"] == AIC_HOTLINE
