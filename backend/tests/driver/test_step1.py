import uuid

from app.schemas import DriverCreate, VehicleType, DriverStatus


def test_driver_create_valid():
    """DriverCreate schema accepts well-formed input and maps all fields."""
    data = DriverCreate(
        provider_id=uuid.uuid4(),
        provider_name="SunCare",
        provider_address="123 Yishun Ave",
        provider_phone="+6591234567",
        provider_location={"lat": 1.3521, "lng": 103.8198},
        service_areas=["Yishun", "Woodlands"],
        name="John Tan",
        phone="+6599990000",
        vehicle_type=VehicleType.WHEELCHAIR_VAN,
        capability_flags=["wheelchair", "dementia_trained"],
        availability_windows=[{"day": "MON", "start": "09:00", "end": "17:00"}],
    )
    assert data.name == "John Tan"
    assert data.vehicle_type == VehicleType.WHEELCHAIR_VAN
    assert "Yishun" in data.service_areas


def test_driver_status_no_pending():
    """DriverStatus must be exactly AVAILABLE, BUSY, OFFLINE — never PENDING."""
    values = {s.value for s in DriverStatus}
    assert values == {"AVAILABLE", "BUSY", "OFFLINE"}
    assert "PENDING" not in values
