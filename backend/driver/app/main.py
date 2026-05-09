import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError, Producer
from fastapi import FastAPI
from sqlalchemy.orm.attributes import flag_modified

from app.database import AsyncSessionLocal, Base, engine, settings
from app.models import Driver
from app.router import router

logger = logging.getLogger(__name__)


# ── Kafka config factory ──────────────────────────────────────────────────────

def _make_kafka_config(extra: dict | None = None) -> dict:
    cfg: dict = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
    # Use SASL_SSL only when credentials are provided (Confluent Cloud / GKE).
    # Local docker Kafka runs without auth.
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


# ── message handler ───────────────────────────────────────────────────────────

async def _handle_trip_offered(data: dict, producer: Producer) -> None:
    try:
        driver_id = uuid.UUID(str(data["driver_id"]))
        trip_id = uuid.UUID(str(data["trip_id"]))
    except (KeyError, ValueError):
        logger.warning("Malformed trip.offered.driver message: %s", data)
        return

    async with AsyncSessionLocal() as db:
        driver = await db.get(Driver, driver_id)
        if not driver:
            return  # not a driver managed by this service

        future_ids = list(driver.future_trip_ids or [])
        if trip_id not in future_ids:
            future_ids.append(trip_id)
        driver.future_trip_ids = future_ids
        flag_modified(driver, "future_trip_ids")
        await db.commit()

    payload = json.dumps({
        "trip_id": str(trip_id),
        "driver_id": str(driver_id),
        "notified_at": datetime.now(timezone.utc).isoformat(),
    }).encode()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: (producer.produce("trip.notified.driver", value=payload), producer.flush()),
    )
    logger.info("Published trip.notified.driver for trip %s", trip_id)


# ── consumer loop ─────────────────────────────────────────────────────────────

async def _consumer_loop(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    consumer = Consumer(
        _make_kafka_config({
            "group.id": "driver-service-group",
            "auto.offset.reset": "earliest",
        })
    )
    producer = Producer(_make_kafka_config())
    consumer.subscribe(["trip.offered.driver"])
    logger.info("Kafka consumer started on topic trip.offered.driver")

    try:
        while not stop_event.is_set():
            msg = await loop.run_in_executor(None, lambda: consumer.poll(1.0))
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Kafka error: %s", msg.error())
                continue
            try:
                data = json.loads(msg.value().decode())
                await _handle_trip_offered(data, producer)
            except Exception:
                logger.exception("Error processing message")
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


app = FastAPI(title="Driver Service", lifespan=lifespan)
app.include_router(router, prefix="/drivers")
