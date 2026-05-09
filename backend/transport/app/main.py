import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from confluent_kafka import Consumer, KafkaError
from fastapi import FastAPI

from app.config import settings
from app.kafka_client import publish
from app.matching import match_trip, pop_next_driver, pop_next_escort
from app.router import router
from app.schemas import TripRequest, Location

logger = logging.getLogger(__name__)


def _make_kafka_config(extra: dict | None = None) -> dict:
    cfg: dict = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
    if settings.KAFKA_API_KEY:
        cfg.update({
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": settings.KAFKA_API_KEY,
            "sasl.password": settings.KAFKA_API_SECRET,
        })
    if extra:
        cfg.update(extra)
    return cfg


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_uuid(val) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(val)) if val else None
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _notify_met(path: str, body: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(f"{settings.MET_ENGINE_URL}{path}", json=body)
    except Exception:
        logger.warning("Failed to notify MET Engine at %s", path)


# ── message handlers ──────────────────────────────────────────────────────────

async def _handle_trip_requested(data: dict) -> None:
    try:
        request = TripRequest(
            trip_id=uuid.UUID(str(data["trip_id"])),
            elderly_id=uuid.UUID(str(data["elderly_id"])),
            caregiver_id=uuid.UUID(str(data["caregiver_id"])),
            pickup_location=Location(**data["pickup_location"]),
            dropoff_location=Location(**data["dropoff_location"]),
            appointment_datetime=datetime.fromisoformat(data["appointment_datetime"]),
            mobility_flags=data.get("mobility_flags", []),
            elderly_needs=data.get("elderly_needs", []),
            preferred_languages=data.get("preferred_languages", []),
            preferred_ngo_id=_parse_uuid(data.get("preferred_ngo_id")),
            max_price=data.get("max_price"),
            service_area=data.get("service_area"),
        )
    except Exception:
        logger.exception("Invalid trip.requested payload")
        return

    result = await match_trip(request)

    if result.success:
        publish("trip.offered.driver", {
            "trip_id": str(request.trip_id),
            "driver_id": str(result.driver_id),
            "escort_id": str(result.escort_id),
            "vehicle_type": result.vehicle_type,
            "pickup_location": data["pickup_location"],
            "dropoff_location": data["dropoff_location"],
            "appointment_datetime": data["appointment_datetime"],
            "elderly_needs": request.elderly_needs,
            "estimated_price": result.estimated_price,
        })
        publish("trip.offered.escort", {
            "trip_id": str(request.trip_id),
            "escort_id": str(result.escort_id),
            "driver_id": str(result.driver_id),
            "pickup_location": data["pickup_location"],
            "dropoff_location": data["dropoff_location"],
            "appointment_datetime": data["appointment_datetime"],
            "elderly_needs": request.elderly_needs,
        })
        logger.info("Match found for trip %s", request.trip_id)
    else:
        publish("trip.no_match", {
            "trip_id": str(request.trip_id),
            "elderly_id": str(request.elderly_id),
            "caregiver_id": str(request.caregiver_id),
            "reason": result.reason,
            "attempted_at": _now_iso(),
        })
        logger.info("No match for trip %s: %s", request.trip_id, result.reason)


async def _handle_trip_accepted_driver(data: dict) -> None:
    trip_id = data["trip_id"]
    driver_id = data["driver_id"]
    confirmed_at = _now_iso()
    publish("trip.confirmed", {
        "trip_id": trip_id,
        "driver_id": driver_id,
        "accepted_at": data.get("accepted_at"),
        "confirmed_at": confirmed_at,
    })
    await _notify_met(
        f"/internal/trips/{trip_id}/confirmed",
        {"driver_id": driver_id, "confirmed_at": confirmed_at},
    )
    logger.info("Trip %s confirmed by driver %s", trip_id, driver_id)


async def _handle_trip_rejected_driver(data: dict) -> None:
    trip_id_str = data["trip_id"]
    trip_id = uuid.UUID(trip_id_str)

    next_driver_id = await pop_next_driver(trip_id)
    if next_driver_id:
        publish("trip.offered.driver", {
            "trip_id": trip_id_str,
            "driver_id": next_driver_id,
            "pickup_location": data.get("pickup_location"),
            "dropoff_location": data.get("dropoff_location"),
            "appointment_datetime": data.get("appointment_datetime"),
            "elderly_needs": data.get("elderly_needs", []),
            "estimated_price": data.get("estimated_price"),
        })
        logger.info("Re-offered trip %s to next driver %s", trip_id_str, next_driver_id)
        return

    next_escort_id = await pop_next_escort(trip_id)
    if not next_escort_id:
        publish("trip.no_match", {
            "trip_id": trip_id_str,
            "elderly_id": data.get("elderly_id", ""),
            "caregiver_id": data.get("caregiver_id", ""),
            "reason": "no_available_driver",
            "attempted_at": _now_iso(),
        })
        logger.info("No more candidates for trip %s", trip_id_str)


async def _handle_driver_reaching(data: dict) -> None:
    trip_id = data["trip_id"]
    await _notify_met(
        f"/internal/trips/{trip_id}/reaching",
        {
            "driver_id": data.get("driver_id"),
            "triggered_at": data.get("triggered_at"),
            "type": "driver",
        },
    )
    logger.info("Driver reaching for trip %s", trip_id)


async def _handle_escort_reaching(data: dict) -> None:
    trip_id = data["trip_id"]
    await _notify_met(
        f"/internal/trips/{trip_id}/reaching",
        {
            "escort_id": data.get("escort_id"),
            "triggered_at": data.get("triggered_at"),
            "type": "escort",
        },
    )
    logger.info("Escort reaching for trip %s", trip_id)


_HANDLERS = {
    "trip.requested": _handle_trip_requested,
    "trip.accepted.driver": _handle_trip_accepted_driver,
    "trip.rejected.driver": _handle_trip_rejected_driver,
    "trip.driver_reaching": _handle_driver_reaching,
    "trip.escort_reaching": _handle_escort_reaching,
}


# ── consumer loop ─────────────────────────────────────────────────────────────

async def _consumer_loop(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    consumer = Consumer(
        _make_kafka_config({
            "group.id": "transport-service-group",
            "auto.offset.reset": "earliest",
        })
    )
    consumer.subscribe(list(_HANDLERS.keys()))
    logger.info("Kafka consumer started on topics: %s", list(_HANDLERS.keys()))

    try:
        while not stop_event.is_set():
            msg = await loop.run_in_executor(None, lambda: consumer.poll(1.0))
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Kafka error: %s", msg.error())
                continue
            handler = _HANDLERS.get(msg.topic())
            if not handler:
                continue
            try:
                data = json.loads(msg.value().decode())
                await handler(data)
            except Exception:
                logger.exception("Error processing message on %s", msg.topic())
    finally:
        consumer.close()
        logger.info("Kafka consumer stopped")


# ── lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(_consumer_loop(stop_event))
    yield
    stop_event.set()
    try:
        await asyncio.wait_for(consumer_task, timeout=5.0)
    except asyncio.TimeoutError:
        consumer_task.cancel()


app = FastAPI(title="Transport Service", lifespan=lifespan)
app.include_router(router, prefix="/transport")
