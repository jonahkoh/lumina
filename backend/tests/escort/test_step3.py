from unittest.mock import patch

import app.main as main_module
from app.main import _make_kafka_config


def test_kafka_config_no_sasl_locally():
    """Without API key, escort config has no SASL fields (local docker)."""
    mock = main_module.settings.__class__.model_construct(
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_API_KEY="",
        KAFKA_API_SECRET="",
    )
    with patch.object(main_module, "settings", mock):
        cfg = _make_kafka_config()
    assert cfg["bootstrap.servers"] == "localhost:9092"
    assert "security.protocol" not in cfg


def test_kafka_config_sasl_for_confluent_cloud():
    """With API key, escort config must include SASL_SSL for Confluent Cloud."""
    mock = main_module.settings.__class__.model_construct(
        KAFKA_BOOTSTRAP_SERVERS="pkc-xxx.ap-southeast-1.aws.confluent.cloud:9092",
        KAFKA_API_KEY="ek",
        KAFKA_API_SECRET="es",
    )
    with patch.object(main_module, "settings", mock):
        cfg = _make_kafka_config()
    assert cfg["security.protocol"] == "SASL_SSL"
    assert cfg["sasl.username"] == "ek"
