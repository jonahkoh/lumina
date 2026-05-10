"""
MET Engine — Kafka consumer factory.

MET Engine only consumes; it never publishes to Kafka directly.
All side-effects are driven via REST calls to Transport or Bot services.
"""
from confluent_kafka import Consumer

from app.config import settings


def make_consumer(group_id: str = "met-engine-group") -> Consumer:
    conf: dict = {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    }
    if settings.KAFKA_API_KEY and settings.KAFKA_API_SECRET:
        conf.update(
            {
                "security.protocol": "SASL_SSL",
                "sasl.mechanisms": "PLAIN",
                "sasl.username": settings.KAFKA_API_KEY,
                "sasl.password": settings.KAFKA_API_SECRET,
            }
        )
    return Consumer(conf)
