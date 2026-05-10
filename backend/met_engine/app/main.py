"""
MET Engine — Python FastAPI service.

Responsibilities
----------------
1. Consume Kafka events published by Transport and forward relevant state
   changes to the Bot service via HTTP.
2. Expose internal REST endpoints called by Transport (confirmed / reaching /
   completed callbacks).
3. Expose a bot-facing booking endpoint that proxies to Transport.

Kafka topics consumed
---------------------
  trip.offered.driver   trip.offered.escort   trip.accepted.escort
  trip.confirmed        trip.no_match         trip.completed
  trip.cancelled        payment.initiated     payment.completed

Kafka topics produced
---------------------
  (none — all Transport interactions use REST)
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.config import settings
from app.kafka_client import make_consumer
from app.router import router
from app.schemas import (
    PaymentCompletedPayload,
    PaymentInitiatedPayload,
    TripAcceptedEscortPayload,
    TripCancelledPayload,
    TripCompletedPayload,
    TripConfirmedPayload,
    TripNoMatchPayload,
    TripOfferedDriverPayload,
    TripOfferedEscortPayload,
)

log = logging.getLogger(__name__)

_TOPICS = [
    "trip.offered.driver",
    "trip.offered.escort",
    "trip.accepted.escort",
    "trip.confirmed",
    "trip.no_match",
    "trip.completed",
    "trip.cancelled",
    "payment.initiated",
    "payment.completed",
]

_http: httpx.AsyncClient | None = None


def _bot_url(path: str) -> str:
    return settings.BOT_SERVICE_URL.rstrip("/") + path


# ── per-topic handlers ────────────────────────────────────────────────────────

async def _handle_trip_offered_driver(raw: dict) -> None:
    payload = TripOfferedDriverPayload(**raw)
    log.info("trip.offered.driver trip_id=%s driver_id=%s", payload.trip_id, payload.driver_id)
    await _post_bot("/bot/notify/driver_offered", payload.model_dump(mode="json"))


async def _handle_trip_offered_escort(raw: dict) -> None:
    payload = TripOfferedEscortPayload(**raw)
    log.info("trip.offered.escort trip_id=%s escort_id=%s", payload.trip_id, payload.escort_id)
    await _post_bot("/bot/notify/escort_offered", payload.model_dump(mode="json"))


async def _handle_trip_accepted_escort(raw: dict) -> None:
    payload = TripAcceptedEscortPayload(**raw)
    log.info("trip.accepted.escort trip_id=%s escort_id=%s", payload.trip_id, payload.escort_id)
    await _post_bot("/bot/notify/escort_accepted", payload.model_dump(mode="json"))


async def _handle_trip_confirmed(raw: dict) -> None:
    payload = TripConfirmedPayload(**raw)
    log.info("trip.confirmed trip_id=%s driver_id=%s", payload.trip_id, payload.driver_id)
    await _post_bot("/bot/notify/trip_confirmed", payload.model_dump(mode="json"))


async def _handle_trip_no_match(raw: dict) -> None:
    payload = TripNoMatchPayload(**raw)
    log.info("trip.no_match trip_id=%s", payload.trip_id)
    await _post_bot("/bot/notify/no_match", payload.model_dump(mode="json"))


async def _handle_trip_completed(raw: dict) -> None:
    payload = TripCompletedPayload(**raw)
    log.info("trip.completed trip_id=%s", payload.trip_id)
    await _post_bot("/bot/notify/trip_completed", payload.model_dump(mode="json"))


async def _handle_trip_cancelled(raw: dict) -> None:
    payload = TripCancelledPayload(**raw)
    log.info("trip.cancelled trip_id=%s", payload.trip_id)
    await _post_bot("/bot/notify/trip_cancelled", payload.model_dump(mode="json"))


async def _handle_payment_initiated(raw: dict) -> None:
    payload = PaymentInitiatedPayload(**raw)
    log.info("payment.initiated trip_id=%s amount=%s", payload.trip_id, payload.amount)
    await _post_bot("/bot/notify/payment_initiated", payload.model_dump(mode="json"))


async def _handle_payment_completed(raw: dict) -> None:
    payload = PaymentCompletedPayload(**raw)
    log.info("payment.completed trip_id=%s amount=%s", payload.trip_id, payload.amount)
    await _post_bot("/bot/notify/payment_completed", payload.model_dump(mode="json"))


_HANDLERS: dict = {
    "trip.offered.driver": _handle_trip_offered_driver,
    "trip.offered.escort": _handle_trip_offered_escort,
    "trip.accepted.escort": _handle_trip_accepted_escort,
    "trip.confirmed": _handle_trip_confirmed,
    "trip.no_match": _handle_trip_no_match,
    "trip.completed": _handle_trip_completed,
    "trip.cancelled": _handle_trip_cancelled,
    "payment.initiated": _handle_payment_initiated,
    "payment.completed": _handle_payment_completed,
}


# ── HTTP helper ───────────────────────────────────────────────────────────────

async def _post_bot(path: str, body: dict) -> None:
    """Fire-and-forget POST to Bot service. Logs failures, never raises."""
    assert _http is not None
    try:
        resp = await _http.post(_bot_url(path), json=body, timeout=10.0)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("bot notify failed path=%s err=%s", path, exc)


# ── Kafka consumer loop ───────────────────────────────────────────────────────

async def _consume_loop() -> None:
    consumer = make_consumer()
    consumer.subscribe(_TOPICS)
    log.info("MET Engine subscribed to %s", _TOPICS)
    loop = asyncio.get_running_loop()
    try:
        while True:
            msg = await loop.run_in_executor(None, lambda: consumer.poll(1.0))
            if msg is None:
                continue
            if msg.error():
                log.error("Kafka error: %s", msg.error())
                continue
            topic = msg.topic()
            try:
                raw = json.loads(msg.value().decode())
                handler = _HANDLERS.get(topic)
                if handler:
                    await handler(raw)
                else:
                    log.warning("no handler for topic %s", topic)
            except Exception as exc:
                log.exception("handler error topic=%s err=%s", topic, exc)
    finally:
        consumer.close()


# ── FastAPI lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    global _http
    _http = httpx.AsyncClient()
    task = asyncio.create_task(_consume_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await _http.aclose()


app = FastAPI(title="MET Engine", version="1.0.0", lifespan=lifespan)
app.include_router(router)

logging.basicConfig(level=logging.INFO)
