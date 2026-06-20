import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.router import cancel_trip


def test_cancel_publishes_with_driver_and_escort_ids():
    """trip.cancelled payload includes driver_id and escort_id when assignment exists."""
    trip_id = uuid.uuid4()
    driver_id = str(uuid.uuid4())
    escort_id = str(uuid.uuid4())

    published = {}

    async def fake_get_assignment(_):
        return {"driver_id": driver_id, "escort_id": escort_id}

    async def fake_cleanup(_):
        pass

    def fake_publish(topic, payload):
        published["topic"] = topic
        published["payload"] = payload

    class FakeResponse:
        def raise_for_status(self): pass

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def patch(self, *a, **kw): return FakeResponse()

    with patch("app.router.get_trip_assignment", side_effect=fake_get_assignment), \
         patch("app.router.cleanup_trip_redis", side_effect=fake_cleanup), \
         patch("app.router.publish", side_effect=fake_publish), \
         patch("app.router.httpx.AsyncClient", return_value=FakeClient()):
        asyncio.run(cancel_trip(trip_id))

    assert published["topic"] == "trip.cancelled"
    assert published["payload"]["driver_id"] == driver_id
    assert published["payload"]["escort_id"] == escort_id
    assert "cancelled_at" in published["payload"]


def test_cancel_no_assignment_still_publishes():
    """cancel proceeds and publishes even when no assignment exists (trip never matched)."""
    trip_id = uuid.uuid4()
    published = {}

    async def fake_get_assignment(_):
        return None

    async def fake_cleanup(_):
        pass

    def fake_publish(topic, payload):
        published["topic"] = topic
        published["payload"] = payload

    with patch("app.router.get_trip_assignment", side_effect=fake_get_assignment), \
         patch("app.router.cleanup_trip_redis", side_effect=fake_cleanup), \
         patch("app.router.publish", side_effect=fake_publish):
        asyncio.run(cancel_trip(trip_id))

    assert published["topic"] == "trip.cancelled"
    assert published["payload"]["driver_id"] is None
    assert published["payload"]["escort_id"] is None
