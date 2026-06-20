from unittest.mock import MagicMock, patch
import uuid
import asyncio


def test_complete_endpoint_exists():
    """Escort router must have a complete_trip route publishing trip.completed.escort."""
    import app.router as router_module
    import inspect
    src = inspect.getsource(router_module.complete_trip)
    assert "trip.completed.escort" in src
    assert "AVAILABLE" in src


def test_complete_escort_payload():
    """trip.completed.escort payload contains trip_id, escort_id, completed_at."""
    import app.router as r

    trip_id = uuid.uuid4()
    escort_id = uuid.uuid4()
    published = {}

    def fake_publish(producer, topic, payload):
        published["topic"] = topic
        published["payload"] = payload

    async def run():
        mock_db = MagicMock()
        mock_escort = MagicMock()
        mock_escort.future_trip_ids = [trip_id]
        mock_escort.past_trip_ids = []
        mock_escort.status = None

        async def fake_get(*a, **kw):
            return mock_escort
        async def fake_commit():
            pass

        mock_db.get = fake_get
        mock_db.commit = fake_commit

        with patch("app.router._publish", side_effect=fake_publish), \
             patch("app.router._get_producer", return_value=MagicMock()):
            await r.complete_trip(escort_id, trip_id, mock_db)

    asyncio.run(run())

    assert published.get("topic") == "trip.completed.escort"
    assert published["payload"]["escort_id"] == str(escort_id)
    assert published["payload"]["trip_id"] == str(trip_id)
    assert "completed_at" in published["payload"]
