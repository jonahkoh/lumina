from unittest.mock import patch

from app.main import _make_kafka_config


def test_kafka_config_no_sasl():
    """When KAFKA_API_KEY is empty, no SASL fields are added."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
        mock_settings.KAFKA_API_KEY = ""
        cfg = _make_kafka_config()
    assert cfg["bootstrap.servers"] == "localhost:9092"
    assert "security.protocol" not in cfg
    assert "sasl.mechanisms" not in cfg


def test_kafka_config_with_sasl():
    """When KAFKA_API_KEY is set, SASL_SSL fields are injected."""
    with patch("app.main.settings") as mock_settings:
        mock_settings.KAFKA_BOOTSTRAP_SERVERS = "broker:9092"
        mock_settings.KAFKA_API_KEY = "mykey"
        mock_settings.KAFKA_API_SECRET = "mysecret"
        cfg = _make_kafka_config()
    assert cfg["security.protocol"] == "SASL_SSL"
    assert cfg["sasl.mechanisms"] == "PLAIN"
    assert cfg["sasl.username"] == "mykey"
    assert cfg["sasl.password"] == "mysecret"
