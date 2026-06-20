import uuid

import pytest
from pydantic import ValidationError

from app.schemas import EscortCreate, EscortStatus


def test_escort_create_valid_languages():
    """EscortCreate accepts valid language codes and maps all fields."""
    data = EscortCreate(
        provider_id=uuid.uuid4(),
        provider_name="SunCare",
        provider_address="123 Yishun Ave",
        provider_phone="+6591234567",
        provider_location={"lat": 1.3521, "lng": 103.8198},
        service_areas=["Yishun"],
        name="Li Mei",
        phone="+6591110000",
        languages=["english", "chinese"],
        specialisations=["dementia", "wheelchair"],
        availability_windows=[{"day": "MON", "start": "09:00", "end": "17:00"}],
    )
    assert data.name == "Li Mei"
    assert "chinese" in data.languages


def test_escort_create_rejects_invalid_language():
    """EscortCreate must reject unknown language codes."""
    with pytest.raises(ValidationError):
        EscortCreate(
            provider_id=uuid.uuid4(),
            provider_name="SunCare",
            provider_address="123 Yishun Ave",
            provider_phone="+6591234567",
            provider_location={"lat": 1.3521, "lng": 103.8198},
            name="Li Mei",
            phone="+6591110000",
            languages=["french"],  # not in allowed set
        )
