from unittest.mock import patch

from app.main import _make_kafka_config, _HANDLERS


def test_kafka_config_no_sasl():
    """No SASL fields when KAFKA_API_KEY is empty."""
    with patch("app.main.settings") as s:
        s.KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
        s.KAFKA_API_KEY = ""
        cfg = _make_kafka_config()
    assert cfg["bootstrap.servers"] == "localhost:9092"
    assert "security.protocol" not in cfg


def test_handlers_cover_all_five_topics():
    """_HANDLERS must contain exactly the five expected Kafka topics."""
    expected = {
        "trip.requested",
        "trip.accepted.driver",
        "trip.rejected.driver",
        "trip.driver_reaching",
        "trip.escort_reaching",
    }
    assert set(_HANDLERS.keys()) == expected
