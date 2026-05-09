import asyncio
import uuid
from typing import Optional

import httpx
import redis.asyncio as aioredis

from app.config import settings
from app.schemas import DriverMatch, EscortMatch, MatchResult, TripNeeds, TripRequest

_CANDIDATE_TTL = 10800  # 3 hours


def _vehicle_type_from_flags(mobility_flags: list[str]) -> str:
    if "stretcher" in mobility_flags:
        return "STRETCHER"
    if "wheelchair" in mobility_flags:
        return "WHEELCHAIR_VAN"
    return "STANDARD"


def compute_price(vehicle_type: str) -> float:
    rates = {"STANDARD": 20.00, "WHEELCHAIR_VAN": 35.00, "STRETCHER": 50.00}
    return rates.get(vehicle_type, 20.00)


def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def find_and_cache_drivers(needs: TripNeeds) -> list[DriverMatch]:
    vehicle_type = _vehicle_type_from_flags(needs.mobility_flags)
    params: dict = {
        "vehicle_type": vehicle_type,
        "datetime": needs.appointment_datetime.isoformat(),
        "pickup_lat": needs.pickup_location.lat,
        "pickup_lng": needs.pickup_location.lng,
    }
    if needs.elderly_needs:
        params["capability_flags"] = needs.elderly_needs
    if needs.service_area:
        params["service_area"] = needs.service_area

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{settings.DRIVER_SERVICE_URL}/drivers/available", params=params
        )
        resp.raise_for_status()
        raw = resp.json()

    matches = [
        DriverMatch(
            driver_id=uuid.UUID(d["driver_id"]),
            vehicle_type=d.get("vehicle_type", vehicle_type),
            match_score=d.get("match_score", 0.0),
        )
        for d in raw
    ]

    if matches:
        async with _redis() as r:
            key = f"candidates:driver:{needs.trip_id}"
            await r.delete(key)
            await r.rpush(key, *[str(m.driver_id) for m in matches])
            await r.expire(key, _CANDIDATE_TTL)

    return matches


async def find_and_cache_escorts(needs: TripNeeds) -> list[EscortMatch]:
    params: dict = {
        "datetime": needs.appointment_datetime.isoformat(),
        "pickup_lat": needs.pickup_location.lat,
        "pickup_lng": needs.pickup_location.lng,
    }
    if needs.elderly_needs:
        params["specialisations"] = needs.elderly_needs
    if needs.preferred_languages:
        params["languages"] = needs.preferred_languages
    if needs.service_area:
        params["service_area"] = needs.service_area

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{settings.ESCORT_SERVICE_URL}/escorts/available", params=params
        )
        resp.raise_for_status()
        raw = resp.json()

    matches = [
        EscortMatch(
            escort_id=uuid.UUID(e["escort_id"]),
            match_score=e.get("match_score", 0.0),
        )
        for e in raw
    ]

    if matches:
        async with _redis() as r:
            key = f"candidates:escort:{needs.trip_id}"
            await r.delete(key)
            await r.rpush(key, *[str(m.escort_id) for m in matches])
            await r.expire(key, _CANDIDATE_TTL)

    return matches


async def pop_next_driver(trip_id: uuid.UUID) -> Optional[str]:
    async with _redis() as r:
        return await r.lpop(f"candidates:driver:{trip_id}")


async def pop_next_escort(trip_id: uuid.UUID) -> Optional[str]:
    async with _redis() as r:
        return await r.lpop(f"candidates:escort:{trip_id}")


async def match_trip(trip_request: TripRequest) -> MatchResult:
    needs = TripNeeds(
        trip_id=trip_request.trip_id,
        pickup_location=trip_request.pickup_location,
        dropoff_location=trip_request.dropoff_location,
        appointment_datetime=trip_request.appointment_datetime,
        mobility_flags=trip_request.mobility_flags,
        elderly_needs=trip_request.elderly_needs,
        preferred_languages=trip_request.preferred_languages,
        service_area=trip_request.service_area,
    )

    drivers, escorts = await asyncio.gather(
        find_and_cache_drivers(needs),
        find_and_cache_escorts(needs),
    )

    if not drivers:
        return MatchResult(success=False, reason="no_available_driver")
    if not escorts:
        return MatchResult(success=False, reason="no_available_escort")

    driver = drivers[0]
    escort = escorts[0]
    vehicle_type = _vehicle_type_from_flags(trip_request.mobility_flags)

    return MatchResult(
        success=True,
        driver_id=driver.driver_id,
        escort_id=escort.escort_id,
        vehicle_type=vehicle_type,
        estimated_price=compute_price(vehicle_type),
    )
