import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError
from fastapi import FastAPI

from app.database import AsyncSessionLocal, Base, engine, settings
from app.models import AuditOutcome, TripType
from app.router import _write_audit, router
from app.schemas import TripAuditCreate

logger = logging.getLogger(__name__)


# ── Kafka config factory ──────────────────────────────────────────────────────

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


# ── message handlers ──────────────────────────────────────────────────────────

def _parse_uuid(val: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(val)) if val else None
    except ValueError:
        return None


def _parse_dt(val: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(str(val)) if val else None
    except ValueError:
        return None


def _parse_trip_type(val: str | None) -> TripType | None:
    try:
        return TripType(val) if val else None
    except ValueError:
        return None


async def _handle_completed(data: dict) -> None:
    body = TripAuditCreate(
        trip_id=uuid.UUID(str(data["trip_id"])),
        elderly_id=uuid.UUID(str(data["elderly_id"])),
        caregiver_id=uuid.UUID(str(data["caregiver_id"])),
        outcome=AuditOutcome.COMPLETED,
        driver_id=_parse_uuid(data.get("driver_id")),
        escort_id=_parse_uuid(data.get("escort_id")),
        provider_id=_parse_uuid(data.get("provider_id")),
        provider_name=data.get("provider_name"),
        pickup_location=data.get("pickup_location"),
        dropoff_location=data.get("dropoff_location"),
        appointment_datetime=_parse_dt(data.get("appointment_datetime")),
        photo_url=data.get("photo_url"),
        dropoff_confirmed=data.get("dropoff_confirmed"),
        completed_at=_parse_dt(data.get("completed_at")),
        trip_type=_parse_trip_type(data.get("trip_type")),
    )
    async with AsyncSessionLocal() as db:
        await _write_audit(body, db)
    logger.info("Audit written for completed trip %s", data["trip_id"])


async def _handle_no_match(data: dict) -> None:
    body = TripAuditCreate(
        trip_id=uuid.UUID(str(data["trip_id"])),
        elderly_id=uuid.UUID(str(data["elderly_id"])),
        caregiver_id=uuid.UUID(str(data["caregiver_id"])),
        outcome=AuditOutcome.NO_MATCH,
        reason=data.get("reason"),
    )
    async with AsyncSessionLocal() as db:
        await _write_audit(body, db)
    logger.info("Audit written for no-match trip %s", data["trip_id"])


async def _handle_cancelled(data: dict) -> None:
    body = TripAuditCreate(
        trip_id=uuid.UUID(str(data["trip_id"])),
        elderly_id=uuid.UUID(str(data["elderly_id"])),
        caregiver_id=uuid.UUID(str(data["caregiver_id"])),
        outcome=AuditOutcome.CANCELLED,
        reason=data.get("reason"),
    )
    async with AsyncSessionLocal() as db:
        await _write_audit(body, db)
    logger.info("Audit written for cancelled trip %s", data["trip_id"])


_HANDLERS = {
    "trip.completed": _handle_completed,
    "trip.no_match": _handle_no_match,
    "trip.cancelled": _handle_cancelled,
}


# ── consumer loop ─────────────────────────────────────────────────────────────

async def _consumer_loop(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    consumer = Consumer(
        _make_kafka_config({
            "group.id": "trip-audit-service-group",
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(_consumer_loop(stop_event))

    yield

    stop_event.set()
    try:
        await asyncio.wait_for(consumer_task, timeout=5.0)
    except asyncio.TimeoutError:
        consumer_task.cancel()


app = FastAPI(title="Trip Audit Service", lifespan=lifespan)
app.include_router(router, prefix="/trips")
