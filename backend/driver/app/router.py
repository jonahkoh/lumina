import math
import uuid
from datetime import datetime as dt_class
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models import Driver, DriverStatus, VehicleType
from app.schemas import (
    DriverCreate,
    DriverResponse,
    DriverWithScore,
    StatusUpdate,
    TripUpdate,
)

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in km between two lat/lng points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _covers_datetime(windows: list, dt: dt_class) -> bool:
    """True if any availability window covers the given datetime."""
    day_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
    day_str = day_map[dt.weekday()]
    t = dt.strftime("%H:%M")
    for w in windows:
        if w.get("day") == day_str and w.get("start", "00:00") <= t <= w.get("end", "23:59"):
            return True
    return False


async def _get_driver_or_404(driver_id: uuid.UUID, db: AsyncSession) -> Driver:
    driver = await db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("", response_model=DriverResponse, status_code=201)
async def create_driver(body: DriverCreate, db: AsyncSession = Depends(get_db)):
    driver = Driver(**body.model_dump(), status=DriverStatus.AVAILABLE)
    db.add(driver)
    await db.commit()
    await db.refresh(driver)
    return driver


# NOTE: /available must be declared before /{driver_id} to prevent FastAPI
# from treating the literal string "available" as a UUID path parameter.
@router.get("/available", response_model=List[DriverWithScore])
async def get_available_drivers(
    vehicle_type: VehicleType = Query(...),
    capability_flags: List[str] = Query(default=[]),
    service_area: str = Query(...),
    appointment_datetime: str = Query(..., alias="datetime"),
    pickup_lat: float = Query(...),
    pickup_lng: float = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        requested_dt = dt_class.fromisoformat(appointment_datetime)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid datetime, expected ISO 8601")

    result = await db.execute(
        select(Driver).where(Driver.status == DriverStatus.AVAILABLE)
    )
    candidates = result.scalars().all()

    scored: list[tuple[float, DriverWithScore]] = []
    for d in candidates:
        # Hard filters
        if d.vehicle_type != vehicle_type:
            continue
        if not all(f in (d.capability_flags or []) for f in capability_flags):
            continue
        if service_area not in (d.service_areas or []):
            continue
        if not _covers_datetime(d.availability_windows or [], requested_dt):
            continue

        loc = d.provider_location or {}
        dist_km = _haversine(loc.get("lat", 0.0), loc.get("lng", 0.0), pickup_lat, pickup_lng)
        proximity_score = max(0.0, 1.0 - dist_km / 50.0)
        score = round(0.6 * proximity_score + 0.4 * 1.0, 4)

        row = DriverWithScore(
            **DriverResponse.model_validate(d).model_dump(),
            match_score=score,
        )
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_driver_or_404(driver_id, db)


@router.patch("/{driver_id}/status", response_model=DriverResponse)
async def update_status(
    driver_id: uuid.UUID,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    driver = await _get_driver_or_404(driver_id, db)
    driver.status = body.status
    await db.commit()
    await db.refresh(driver)
    return driver


@router.patch("/{driver_id}/trips", response_model=DriverResponse)
async def update_trips(
    driver_id: uuid.UUID,
    body: TripUpdate,
    db: AsyncSession = Depends(get_db),
):
    driver = await _get_driver_or_404(driver_id, db)

    future_ids = list(driver.future_trip_ids or [])
    past_ids = list(driver.past_trip_ids or [])

    if body.add_future_trip_id and body.add_future_trip_id not in future_ids:
        future_ids.append(body.add_future_trip_id)
    if body.remove_future_trip_id:
        future_ids = [t for t in future_ids if t != body.remove_future_trip_id]
    if body.add_past_trip_id and body.add_past_trip_id not in past_ids:
        past_ids.append(body.add_past_trip_id)

    driver.future_trip_ids = future_ids
    driver.past_trip_ids = past_ids
    # ARRAY columns need explicit dirty-marking; SQLAlchemy won't detect list reassignment
    flag_modified(driver, "future_trip_ids")
    flag_modified(driver, "past_trip_ids")
    await db.commit()
    await db.refresh(driver)
    return driver
