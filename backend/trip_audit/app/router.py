import uuid
from datetime import date, datetime, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditOutcome, TripAudit
from app.schemas import TripAuditCreate, TripAuditResponse

router = APIRouter()


# ── shared write helper (used by both HTTP route and Kafka consumer) ──────────

async def _write_audit(body: TripAuditCreate, db: AsyncSession) -> TripAudit:
    audit = TripAudit(**body.model_dump())
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("", response_model=TripAuditResponse, status_code=201)
async def create_trip_audit(body: TripAuditCreate, db: AsyncSession = Depends(get_db)):
    return await _write_audit(body, db)


@router.get("", response_model=List[TripAuditResponse])
async def list_trip_audits(
    elderly_id: Optional[uuid.UUID] = Query(default=None),
    caregiver_id: Optional[uuid.UUID] = Query(default=None),
    outcome: Optional[AuditOutcome] = Query(default=None),
    provider_id: Optional[uuid.UUID] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(TripAudit)

    if elderly_id:
        query = query.where(TripAudit.elderly_id == elderly_id)
    if caregiver_id:
        query = query.where(TripAudit.caregiver_id == caregiver_id)
    if outcome:
        query = query.where(TripAudit.outcome == outcome)
    if provider_id:
        query = query.where(TripAudit.provider_id == provider_id)
    if from_date:
        query = query.where(TripAudit.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        query = query.where(TripAudit.created_at <= datetime.combine(to_date, time.max))

    query = query.order_by(TripAudit.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{trip_id}", response_model=TripAuditResponse)
async def get_trip_audit(trip_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TripAudit).where(TripAudit.trip_id == trip_id)
    )
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Trip audit not found")
    return audit
