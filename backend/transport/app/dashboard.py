import uuid
from typing import Any, Optional

import httpx

from app.config import settings


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> Any:
    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def admin_dashboard(provider_id: Optional[uuid.UUID]) -> dict:
    params = {"provider_id": str(provider_id)} if provider_id else {}
    async with httpx.AsyncClient(timeout=10) as client:
        drivers, escorts, trips = await _get_all(client, params)
    past_trips = [t for t in trips if t.get("outcome") == "COMPLETED"]
    upcoming_trips = [
        tid
        for d in drivers
        for tid in d.get("future_trip_ids", [])
    ]
    return {
        "drivers": drivers,
        "escorts": escorts,
        "past_trips": past_trips,
        "upcoming_trips": upcoming_trips,
    }


async def _get_all(client: httpx.AsyncClient, params: dict) -> tuple:
    import asyncio
    drivers_task = _get(client, f"{settings.DRIVER_SERVICE_URL}/drivers", params)
    escorts_task = _get(client, f"{settings.ESCORT_SERVICE_URL}/escorts", params)
    trips_task = _get(client, f"{settings.TRIP_AUDIT_SERVICE_URL}/trips")
    return await asyncio.gather(drivers_task, escorts_task, trips_task)


async def driver_dashboard(driver_id: uuid.UUID) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        driver = await _get(client, f"{settings.DRIVER_SERVICE_URL}/drivers/{driver_id}")
        past_trips = await _get(
            client,
            f"{settings.TRIP_AUDIT_SERVICE_URL}/trips",
            {"driver_id": str(driver_id), "outcome": "COMPLETED"},
        )
    return {
        "driver": driver,
        "past_trips": past_trips,
        "upcoming_trips": driver.get("future_trip_ids", []),
    }


async def escort_dashboard(escort_id: uuid.UUID) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        escort = await _get(client, f"{settings.ESCORT_SERVICE_URL}/escorts/{escort_id}")
        past_trips = await _get(
            client,
            f"{settings.TRIP_AUDIT_SERVICE_URL}/trips",
            {"escort_id": str(escort_id), "outcome": "COMPLETED"},
        )
    return {
        "escort": escort,
        "past_trips": past_trips,
        "upcoming_trips": escort.get("future_trip_ids", []),
    }
