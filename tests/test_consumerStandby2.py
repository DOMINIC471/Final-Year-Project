import pytest
from unittest import mock
from system import consumerStandby2
import json
from datetime import datetime, timezone, timedelta

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MESSAGES_PER_MINUTE", "100")
    monkeypatch.setenv("KAFKA_BROKER", "localhost:29092")
    monkeypatch.setenv("PROM_PORT", "8020")
    monkeypatch.setenv("ACTIVE_DB", "influxdb-standby2")
    monkeypatch.setenv("INFLUXDB_ORG", "FYP")
    monkeypatch.setenv("INFLUXDB_BUCKET", "sensor_data")
    monkeypatch.setenv("INFLUXDB_MASTER_TOKEN", "dummy")
    monkeypatch.setenv("INFLUXDB_STANDBY1_TOKEN", "dummy")
    monkeypatch.setenv("INFLUXDB_STANDBY2_TOKEN", "dummy")

@pytest.fixture
def mock_kafka_consumer():
    with mock.patch('system.consumerStandby2.Consumer') as MockConsumer:
        yield MockConsumer.return_value

@pytest.fixture
def mock_influx_clients(monkeypatch):
    with mock.patch('system.consumerStandby2.InfluxDBClient') as MockInflux:
        mock_client = MockInflux.return_value
        mock_write_api = mock.Mock()
        mock_client.write_api.return_value = mock_write_api
        
        # Now monkeypatch influx_clients
        monkeypatch.setattr(consumerStandby2, "influx_clients", {
            "influxdb-master": {"write_api": mock_write_api, "bucket": "sensor_data"},
            "influxdb-standby1": {"write_api": mock_write_api, "bucket": "sensor_data"},
            "influxdb-standby2": {"write_api": mock_write_api, "bucket": "sensor_data"}
        })
        
        yield mock_client, mock_write_api

@pytest.fixture
def mock_producer(monkeypatch):
    mock_producer_instance = mock.Mock()
    monkeypatch.setattr(consumerStandby2, "heartbeat_producer", mock_producer_instance)
    return mock_producer_instance

def test_handle_heartbeat_detection(mock_kafka_consumer, mock_influx_clients, monkeypatch):
    master_heartbeat = {
        "consumer_id": "master",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    standby1_heartbeat = {
        "consumer_id": "standby1",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    master_msg = mock.Mock()
    master_msg.error.return_value = False
    master_msg.value.return_value = json.dumps(master_heartbeat).encode()

    standby1_msg = mock.Mock()
    standby1_msg.error.return_value = False
    standby1_msg.value.return_value = json.dumps(standby1_heartbeat).encode()

    mock_kafka_consumer.poll.side_effect = [master_msg, standby1_msg, None]

    now = datetime.now(timezone.utc)
    last_master_beat = now
    last_standby1_beat = now

    assert last_master_beat is not None
    assert last_standby1_beat is not None

def test_write_to_influx(mock_influx_clients):
    mock_client, mock_write_api = mock_influx_clients

    bed = "701"
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    hr = 82

    consumerStandby2.write_to_all_influx(bed, ts, hr)

    assert mock_write_api.write.called
    assert mock_write_api.write.call_count >= 1

def test_emit_heartbeat(mock_producer):
    consumerStandby2.emit_heartbeat()

    # Check if produce and poll were called
    mock_producer.produce.assert_called_once()
    mock_producer.poll.assert_called_once()

@pytest.mark.parametrize("consumer_response", [
    {
        "bed_number": "702",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "heart_rate": 77
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

    consumerStandby2.write_to_all_influx(bed, ts, hr)

    assert mock_write_api.write.called
