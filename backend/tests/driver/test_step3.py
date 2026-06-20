from unittest.mock import patch

import app.main as main_module
from app.main import _make_kafka_config


def test_kafka_config_local_no_sasl():
    """No API key → plain config, no SASL fields (local docker Kafka)."""
    mock = main_module.settings.__class__.model_construct(
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_API_KEY="",
        KAFKA_API_SECRET="",
    )
    with patch.object(main_module, "settings", mock):
        cfg = _make_kafka_config()
    assert cfg["bootstrap.servers"] == "localhost:9092"
    assert "security.protocol" not in cfg


def test_kafka_config_cloud_includes_sasl():
    """With API key → SASL_SSL fields present (Confluent Cloud / GKE)."""
    mock = main_module.settings.__class__.model_construct(
        KAFKA_BOOTSTRAP_SERVERS="pkc-xxx.ap-southeast-1.aws.confluent.cloud:9092",
        KAFKA_API_KEY="testkey",
        KAFKA_API_SECRET="testsecret",
    )
    with patch.object(main_module, "settings", mock):
        cfg = _make_kafka_config()
    assert cfg["security.protocol"] == "SASL_SSL"
    assert cfg["sasl.mechanisms"] == "PLAIN"
    assert cfg["sasl.username"] == "testkey"
    assert cfg["sasl.password"] == "testsecret"
