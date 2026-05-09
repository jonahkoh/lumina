import json
import math
import uuid
from datetime import datetime as dt_class, timezone
from typing import List, Optional

from confluent_kafka import Producer
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.models import Escort, EscortStatus
from app.schemas import (
    EscortCreate,
    EscortResponse,
    EscortWithScore,
    RejectBody,
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


async def _get_escort_or_404(escort_id: uuid.UUID, db: AsyncSession) -> Escort:
    escort = await db.get(Escort, escort_id)
    if not escort:
        raise HTTPException(status_code=404, detail="Escort not found")
    return escort


def _get_producer() -> Producer:
    from app.main import _make_kafka_config
    return Producer(_make_kafka_config())


def _publish(producer: Producer, topic: str, payload: dict) -> None:
    producer.produce(topic, value=json.dumps(payload).encode())
    producer.flush()


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("", response_model=EscortResponse, status_code=201)
async def create_escort(body: EscortCreate, db: AsyncSession = Depends(get_db)):
    escort = Escort(**body.model_dump(), status=EscortStatus.AVAILABLE)
    db.add(escort)
    await db.commit()
    await db.refresh(escort)
    return escort


# NOTE: /available must be declared before /{escort_id} to avoid routing conflict.
@router.get("/available", response_model=List[EscortWithScore])
async def get_available_escorts(
    specialisations: List[str] = Query(default=[]),
    languages: List[str] = Query(default=[]),
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
        select(Escort).where(Escort.status == EscortStatus.AVAILABLE)
    )
    candidates = result.scalars().all()

    scored: list[tuple[float, EscortWithScore]] = []
    for e in candidates:
        escort_specs = e.specialisations or []
        escort_langs = e.languages or []

        # Hard filters
        if not all(s in escort_specs for s in specialisations):
            continue
        if languages and not any(lang in escort_langs for lang in languages):
            continue
        if service_area not in (e.service_areas or []):
            continue
        if not _covers_datetime(e.availability_windows or [], requested_dt):
            continue

        loc = e.provider_location or {}
        dist_km = _haversine(loc.get("lat", 0.0), loc.get("lng", 0.0), pickup_lat, pickup_lng)
        proximity_score = max(0.0, 1.0 - dist_km / 50.0)

        if specialisations:
            matched = sum(1 for s in specialisations if s in escort_specs)
            specialisation_score = matched / len(specialisations)
        else:
            specialisation_score = 1.0

        score = round(0.6 * proximity_score + 0.4 * specialisation_score, 4)
        row = EscortWithScore(
            **EscortResponse.model_validate(e).model_dump(),
            match_score=score,
        )
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


@router.get("", response_model=List[EscortResponse])
async def list_escorts(
    provider_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Escort)
    if provider_id:
        query = query.where(Escort.provider_id == provider_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{escort_id}", response_model=EscortResponse)
async def get_escort(escort_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_escort_or_404(escort_id, db)


@router.patch("/{escort_id}/status", response_model=EscortResponse)
async def update_status(
    escort_id: uuid.UUID,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    escort = await _get_escort_or_404(escort_id, db)
    escort.status = body.status
    await db.commit()
    await db.refresh(escort)
    return escort


@router.patch("/{escort_id}/trips", response_model=EscortResponse)
async def update_trips(
    escort_id: uuid.UUID,
    body: TripUpdate,
    db: AsyncSession = Depends(get_db),
):
    escort = await _get_escort_or_404(escort_id, db)

    future_ids = list(escort.future_trip_ids or [])
    past_ids = list(escort.past_trip_ids or [])

    if body.add_future_trip_id and body.add_future_trip_id not in future_ids:
        future_ids.append(body.add_future_trip_id)
    if body.remove_future_trip_id:
        future_ids = [t for t in future_ids if t != body.remove_future_trip_id]
    if body.add_past_trip_id and body.add_past_trip_id not in past_ids:
        past_ids.append(body.add_past_trip_id)

    escort.future_trip_ids = future_ids
    escort.past_trip_ids = past_ids
    flag_modified(escort, "future_trip_ids")
    flag_modified(escort, "past_trip_ids")
    await db.commit()
    await db.refresh(escort)
    return escort


# ── trip lifecycle ────────────────────────────────────────────────────────────

@router.post("/{escort_id}/trips/{trip_id}/accept")
async def accept_trip(
    escort_id: uuid.UUID,
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    escort = await _get_escort_or_404(escort_id, db)
    escort.status = EscortStatus.BUSY
    await db.commit()

    _publish(_get_producer(), "trip.accepted.escort", {
        "trip_id": str(trip_id),
        "escort_id": str(escort_id),
        "accepted_at": dt_class.now(timezone.utc).isoformat(),
    })
    return {"message": "accepted"}


@router.post("/{escort_id}/trips/{trip_id}/reject")
async def reject_trip(
    escort_id: uuid.UUID,
    trip_id: uuid.UUID,
    body: RejectBody,
    db: AsyncSession = Depends(get_db),
):
    escort = await _get_escort_or_404(escort_id, db)

    future_ids = [t for t in (escort.future_trip_ids or []) if t != trip_id]
    escort.future_trip_ids = future_ids
    flag_modified(escort, "future_trip_ids")
    await db.commit()

    _publish(_get_producer(), "trip.rejected.escort", {
        "trip_id": str(trip_id),
        "escort_id": str(escort_id),
        "rejected_at": dt_class.now(timezone.utc).isoformat(),
        "reason": body.reason,
    })
    return {"message": "rejected"}


@router.post("/{escort_id}/trips/{trip_id}/complete")
async def complete_trip(
    escort_id: uuid.UUID,
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    escort = await _get_escort_or_404(escort_id, db)

    future_ids = [t for t in (escort.future_trip_ids or []) if t != trip_id]
    past_ids = list(escort.past_trip_ids or [])
    if trip_id not in past_ids:
        past_ids.append(trip_id)

    escort.future_trip_ids = future_ids
    escort.past_trip_ids = past_ids
    escort.status = EscortStatus.AVAILABLE
    flag_modified(escort, "future_trip_ids")
    flag_modified(escort, "past_trip_ids")
    await db.commit()

    _publish(_get_producer(), "trip.completed.escort", {
        "trip_id": str(trip_id),
        "escort_id": str(escort_id),
        "completed_at": dt_class.now(timezone.utc).isoformat(),
    })
    return {"message": "completed"}


@router.post("/{escort_id}/trips/{trip_id}/reaching")
async def reaching_trip(
    escort_id: uuid.UUID,
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await _get_escort_or_404(escort_id, db)

    _publish(_get_producer(), "trip.escort_reaching", {
        "trip_id": str(trip_id),
        "escort_id": str(escort_id),
        "triggered_at": dt_class.now(timezone.utc).isoformat(),
    })
    return {"message": "notified"}
