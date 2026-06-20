from unittest.mock import MagicMock, patch
import uuid


def test_complete_publishes_driver_topic():
    """complete endpoint must publish to trip.completed.driver, not trip.completed."""
    import app.router as router_module
    import inspect
    src = inspect.getsource(router_module.complete_trip)
    assert "trip.completed.driver" in src
    assert '"trip.completed"' not in src


def test_complete_payload_fields():
    """trip.completed.driver payload contains all required fields."""
    from app.schemas import CompleteBody
    body = CompleteBody(photo_url="https://example.com/p.jpg", dropoff_confirmed=True)
    trip_id = uuid.uuid4()
    driver_id = uuid.uuid4()

    published = {}

    def fake_publish(producer, topic, payload):
        published["topic"] = topic
        published["payload"] = payload

    with patch("app.router._publish", side_effect=fake_publish), \
         patch("app.router._get_producer", return_value=MagicMock()):
        from datetime import datetime, timezone
        import app.router as r
        import asyncio

        async def run():
            mock_db = MagicMock()
            mock_driver = MagicMock()
            mock_driver.future_trip_ids = [trip_id]
            mock_driver.past_trip_ids = []
            mock_driver.status = None
            mock_db.get = asyncio.coroutine(lambda *a: mock_driver) if False else None
            mock_db.get = MagicMock(return_value=mock_driver)

            async def fake_get(*a, **kw):
                return mock_driver
            async def fake_commit():
                pass

            mock_db.get = fake_get
            mock_db.commit = fake_commit

            await r.complete_trip(driver_id, trip_id, body, mock_db)

        asyncio.run(run())

    assert published.get("topic") == "trip.completed.driver"
    assert "driver_id" in published["payload"]
    assert "photo_url" in published["payload"]
    assert "dropoff_confirmed" in published["payload"]
