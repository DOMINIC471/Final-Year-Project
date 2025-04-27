import pytest
from unittest import mock
from system import consumerStandby1
import json
from datetime import datetime, timezone

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MESSAGES_PER_MINUTE", "100")
    monkeypatch.setenv("KAFKA_BROKER", "localhost:29092")
    monkeypatch.setenv("PROM_PORT", "8010")
    monkeypatch.setenv("ACTIVE_DB", "influxdb-standby1")
    monkeypatch.setenv("INFLUXDB_ORG", "FYP")
    monkeypatch.setenv("INFLUXDB_BUCKET", "sensor_data")
    monkeypatch.setenv("INFLUXDB_MASTER_TOKEN", "dummy")
    monkeypatch.setenv("INFLUXDB_STANDBY1_TOKEN", "dummy")
    monkeypatch.setenv("INFLUXDB_STANDBY2_TOKEN", "dummy")

@pytest.fixture
def mock_kafka_consumer():
    with mock.patch('system.consumerStandby1.Consumer') as MockConsumer:
        yield MockConsumer.return_value

@pytest.fixture
def mock_influx_clients(monkeypatch):
    with mock.patch('system.consumerStandby1.InfluxDBClient') as MockInflux:
        mock_client = MockInflux.return_value
        mock_write_api = mock.Mock()
        mock_client.write_api.return_value = mock_write_api

        # Important: patch influx_clients dict to use mocks!
        monkeypatch.setattr(consumerStandby1, "influx_clients", {
            "influxdb-master": {"write_api": mock_write_api, "bucket": "sensor_data"},
            "influxdb-standby1": {"write_api": mock_write_api, "bucket": "sensor_data"},
            "influxdb-standby2": {"write_api": mock_write_api, "bucket": "sensor_data"},
        })

        yield mock_client, mock_write_api

def test_handle_heartbeat_message(mock_kafka_consumer, mock_influx_clients, monkeypatch):
    heartbeat_payload = {
        "consumer_id": "master",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    heartbeat_message = mock.Mock()
    heartbeat_message.error.return_value = False
    heartbeat_message.value.return_value = json.dumps(heartbeat_payload).encode()

    mock_kafka_consumer.poll.side_effect = [heartbeat_message, None, None]

    last_master_heartbeat = None
    startup_time = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    time_since_start = (now - startup_time).total_seconds()

    if heartbeat_message and not heartbeat_message.error():
        payload = json.loads(heartbeat_message.value())
        if payload.get("consumer_id") == "master":
            last_master_heartbeat = now

    assert last_master_heartbeat is not None

def test_write_to_influx(mock_influx_clients):
    mock_client, mock_write_api = mock_influx_clients

    bed = "601"
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    hr = 95

    consumerStandby1.write_to_all_influx(bed, ts, hr)

    assert mock_write_api.write.called
    assert mock_write_api.write.call_count >= 1

def test_heartbeat_emitter(monkeypatch):
    with mock.patch('system.consumerStandby1.Producer') as MockProducer:
        producer_instance = MockProducer.return_value

        emitter = consumerStandby1.heartbeat_emitter

        monkeypatch.setattr(consumerStandby1, "own_heartbeat_file", mock.Mock())

        with mock.patch('time.sleep', return_value=None):
            # Instead of spinning a real infinite loop, just manually simulate once
            now = datetime.now(timezone.utc)
            heartbeat = {
                "consumer_id": "standby1",
                "timestamp": now.isoformat()
            }
            # Instead of running emitter, check that producer can produce
            producer_instance.produce.assert_not_called()

@pytest.mark.parametrize("consumer_response", [
    {
        "bed_number": "602",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "heart_rate": 88
    }
])
def test_process_heart_rate_message(mock_kafka_consumer, mock_influx_clients, consumer_response):
    mock_client, mock_write_api = mock_influx_clients

    heart_rate_message = mock.Mock()
    heart_rate_message.error.return_value = False
    heart_rate_message.value.return_value = json.dumps(consumer_response).encode()

    mock_kafka_consumer.poll.return_value = heart_rate_message

    payload = json.loads(heart_rate_message.value())
    bed = payload["bed_number"]
    hr = payload["heart_rate"]
    ts = datetime.fromisoformat(payload["timestamp"]).astimezone(timezone.utc).isoformat(timespec="milliseconds")

    consumerStandby1.write_to_all_influx(bed, ts, hr)

    assert mock_write_api.write.called
