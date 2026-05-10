"""
MET Engine — REST router.

Two groups of endpoints
-----------------------
1. /internal/trips/{trip_id}/*  — called by Transport service only (fire-and-forget callbacks).
2. /engine/*                    — called by Bot service (booking intake, cancel).
"""
import logging
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.schemas import (
    AckResponse,
    BookingRequest,
    BookingResponse,
    CancelRequest,
    CompletedNotificationBody,
    ConfirmedNotificationBody,
    ReachingNotificationBody,
)

log = logging.getLogger(__name__)
router = APIRouter()


def _transport_url(path: str) -> str:
    return settings.TRANSPORT_SERVICE_URL.rstrip("/") + path


# ── Internal callbacks (Transport → MET Engine) ───────────────────────────────

@router.post("/internal/trips/{trip_id}/confirmed", response_model=AckResponse)
async def internal_confirmed(trip_id: uuid.UUID, body: ConfirmedNotificationBody):
    """Transport calls this when a driver confirms a trip."""
    log.info("internal confirmed trip_id=%s driver_id=%s", trip_id, body.driver_id)
    return AckResponse()


@router.post("/internal/trips/{trip_id}/reaching", response_model=AckResponse)
async def internal_reaching(trip_id: uuid.UUID, body: ReachingNotificationBody):
    """Transport calls this when a driver/escort is reaching the pickup point."""
    log.info(
        "internal reaching trip_id=%s type=%s driver=%s escort=%s",
        trip_id, body.type, body.driver_id, body.escort_id,
    )
    return AckResponse()


@router.post("/internal/trips/{trip_id}/completed", response_model=AckResponse)
async def internal_completed(trip_id: uuid.UUID, body: CompletedNotificationBody):
    """Transport calls this when a trip is completed."""
    log.info("internal completed trip_id=%s completed_at=%s", trip_id, body.completed_at)
    return AckResponse()


# ── Bot-facing endpoints ──────────────────────────────────────────────────────

@router.post("/engine/book", response_model=BookingResponse)
async def engine_book(req: BookingRequest):
    """
    Bot submits a fully-resolved booking.
    MET Engine proxies it to Transport POST /transport/trips and returns the
    resulting trip_id + status.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                _transport_url("/transport/trips"),
                json=req.model_dump(mode="json"),
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.error("transport rejected booking trip_id=%s status=%s", req.trip_id, exc.response.status_code)
            raise HTTPException(status_code=502, detail="Transport rejected booking") from exc
        except Exception as exc:
            log.error("transport unreachable: %s", exc)
            raise HTTPException(status_code=503, detail="Transport unreachable") from exc

    data = resp.json()
    return BookingResponse(trip_id=data.get("trip_id", req.trip_id), status=data.get("status", "pending"))


@router.post("/engine/cancel", response_model=AckResponse)
async def engine_cancel(req: CancelRequest):
    """Bot requests trip cancellation. MET Engine proxies to Transport."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                _transport_url(f"/transport/trips/{req.trip_id}/cancel"),
                json={},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.error("transport cancel failed trip_id=%s status=%s", req.trip_id, exc.response.status_code)
            raise HTTPException(status_code=502, detail="Transport cancel failed") from exc
        except Exception as exc:
            log.error("transport unreachable on cancel: %s", exc)
            raise HTTPException(status_code=503, detail="Transport unreachable") from exc

    return AckResponse()


@router.get("/engine/trips/{trip_id}/status")
async def engine_trip_status(trip_id: uuid.UUID):
    """Bot queries trip status. MET Engine proxies to Transport."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(_transport_url(f"/transport/trips/{trip_id}/status"))
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail="Transport error") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Transport unreachable") from exc

    return resp.json()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "service": "met-engine"}
