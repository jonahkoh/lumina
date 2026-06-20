import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.matching import _vehicle_type_from_flags, compute_price, match_trip
from app.schemas import Location, TripRequest


def test_vehicle_type_from_flags():
    """Mobility flags map to the correct vehicle type."""
    assert _vehicle_type_from_flags([]) == "STANDARD"
    assert _vehicle_type_from_flags(["wheelchair"]) == "WHEELCHAIR_VAN"
    assert _vehicle_type_from_flags(["stretcher"]) == "STRETCHER"
    assert _vehicle_type_from_flags(["stretcher", "wheelchair"]) == "STRETCHER"


def test_compute_price():
    """Flat rates are correct per vehicle type."""
    assert compute_price("STANDARD") == 20.00
    assert compute_price("WHEELCHAIR_VAN") == 35.00
    assert compute_price("STRETCHER") == 50.00
    assert compute_price("UNKNOWN") == 20.00
