import json
import logging
from functools import lru_cache

from confluent_kafka import Producer

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_producer() -> Producer:
    cfg: dict = {"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS}
    if settings.KAFKA_API_KEY:
        cfg.update({
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": settings.KAFKA_API_KEY,
            "sasl.password": settings.KAFKA_API_SECRET,
        })
    return Producer(cfg)


def publish(topic: str, payload: dict) -> None:
    producer = _get_producer()
    producer.produce(topic, json.dumps(payload).encode())
    producer.poll(0)
    logger.info("Published to %s: %s", topic, payload.get("trip_id", ""))
