import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.matching import (
    compute_price,
    get_trip_composition,
    is_trip_complete,
    update_trip_composition,
    _store_composition_and_assignment,
)
from app.schemas import DriverMatch, EscortMatch


def test_is_trip_complete_logic():
    """is_trip_complete returns correct value for each trip_type using mocked Redis."""

    async def run():
        base = {
            "requires_driver": True, "requires_escort": True,
            "driver_confirmed": False, "escort_confirmed": False,
        }

        async def mock_get(trip_id):
            return comp

        comp = {**base, "trip_type": "DRIVER_ONLY", "driver_confirmed": True}
        with patch("app.matching.get_trip_composition", side_effect=mock_get):
            assert await is_trip_complete(uuid.uuid4()) is True

        comp = {**base, "trip_type": "ESCORT_ONLY", "escort_confirmed": True}
        with patch("app.matching.get_trip_composition", side_effect=mock_get):
            assert await is_trip_complete(uuid.uuid4()) is True

        comp = {**base, "trip_type": "COMBINED", "driver_confirmed": True, "escort_confirmed": False}
        with patch("app.matching.get_trip_composition", side_effect=mock_get):
            assert await is_trip_complete(uuid.uuid4()) is False

        comp = {**base, "trip_type": "COMBINED", "driver_confirmed": True, "escort_confirmed": True}
        with patch("app.matching.get_trip_composition", side_effect=mock_get):
            assert await is_trip_complete(uuid.uuid4()) is True

    asyncio.run(run())


def test_store_composition_sets_correct_trip_type():
    """_store_composition_and_assignment writes correct trip_type and all IDs to Redis."""
    trip_id = uuid.uuid4()
    elderly_id = uuid.uuid4()
    caregiver_id = uuid.uuid4()
    driver = DriverMatch(driver_id=uuid.uuid4(), vehicle_type="STANDARD", match_score=0.9)
    escort = EscortMatch(escort_id=uuid.uuid4(), match_score=0.8)

    stored = {}

    class FakeRedis:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def set(self, key, val): stored[key] = json.loads(val)
        async def expire(self, key, ttl): pass

    with patch("app.matching._redis", return_value=FakeRedis()):
        asyncio.run(_store_composition_and_assignment(
            trip_id, driver, escort,
            elderly_id=elderly_id, caregiver_id=caregiver_id,
        ))

    comp = stored[f"trip:composition:{trip_id}"]
    assert comp["trip_type"] == "COMBINED"
    assert comp["driver_confirmed"] is False
    assert comp["escort_confirmed"] is False

    assign = stored[f"trip:assignment:{trip_id}"]
    assert assign["driver_id"] == str(driver.driver_id)
    assert assign["escort_id"] == str(escort.escort_id)
    assert assign["elderly_id"] == str(elderly_id)
    assert assign["caregiver_id"] == str(caregiver_id)
