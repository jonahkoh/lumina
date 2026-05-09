from datetime import datetime

from app.router import _covers_datetime, _haversine


def test_haversine_yishun_to_woodlands():
    # Yishun MRT → Woodlands MRT is roughly 6–7 km
    dist = _haversine(1.4295, 103.8354, 1.4368, 103.7863)
    assert 5.0 < dist < 8.0


def test_covers_datetime_inside_and_outside_window():
    windows = [{"day": "MON", "start": "09:00", "end": "17:00"}]
    # 2026-05-11 is a Monday
    assert _covers_datetime(windows, datetime(2026, 5, 11, 10, 30))   # inside
    assert not _covers_datetime(windows, datetime(2026, 5, 11, 18, 0))  # outside
