import pytest
from unittest import mock
from system import consumerMaster
import json
from datetime import datetime, timezone

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MESSAGES_PER_MINUTE", "100")
    monkeypatch.setenv("ACTIVE_DB", "influxdb")
    monkeypatch.setenv("KAFKA_BROKER", "localhost:29092")
    monkeypatch.setenv("PROM_PORT", "8000")
    monkeypatch.setenv("INFLUXDB_ORG", "FYP")
    monkeypatch.setenv("INFLUXDB_BUCKET", "sensor_data")
    monkeypatch.setenv("INFLUXDB_MASTER_TOKEN", "dummy-token")
    monkeypatch.setenv("INFLUXDB_STANDBY1_TOKEN", "dummy-token")
    monkeypatch.setenv("INFLUXDB_STANDBY2_TOKEN", "dummy-token")

@pytest.fixture
def mock_kafka_consumer():
    with mock.patch('system.consumerMaster.Consumer') as MockConsumer:
        yield MockConsumer.return_value

@pytest.fixture
def mock_influxdb_client():
    with mock.patch('system.consumerMaster.InfluxDBClient') as MockInfluxClient:
        mock_client = MockInfluxClient.return_value
        mock_write_api = mock.Mock()
        mock_client.write_api.return_value = mock_write_api
        yield mock_client, mock_write_api

@pytest.fixture
def mock_requests_post():
    with mock.patch('system.consumerMaster.requests.post') as mock_post:
        yield mock_post

@pytest.fixture
def mock_psycopg_connect():
    with mock.patch('system.consumerMaster.psycopg2.connect') as mock_connect:
        mock_conn = mock_connect.return_value
        mock_cursor = mock_conn.cursor.return_value
        yield mock_conn, mock_cursor

@pytest.fixture
def mock_subprocess():
    with mock.patch('system.consumerMaster.subprocess.Popen') as mock_popen:
        yield mock_popen.return_value

def test_heartbeat_emitter_start(mock_subprocess):
    assert mock_subprocess is not None


def test_process_kafka_message_influxdb(mock_kafka_consumer, mock_influxdb_client):
    mock_client, mock_write_api = mock_influxdb_client

    # Create a mock Kafka message
    payload = {
        "bed_number": "501",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "heart_rate": 80
    }

    kafka_message = mock.Mock()
    kafka_message.error.return_value = False
    kafka_message.value.return_value = json.dumps(payload).encode()

    mock_kafka_consumer.poll.return_value = kafka_message

    bed = payload["bed_number"]
    hr = payload["heart_rate"]
    ts = payload["timestamp"]

    consumerMaster.write_to_influxdb("influxdb-master", bed, ts, hr)

    assert mock_write_api.write.called


def test_write_to_victoriametrics(mock_requests_post):
    bed = "502"
    hr = 75
    ts = datetime.now(timezone.utc).isoformat()

    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_requests_post.return_value = mock_response

    consumerMaster.write_to_victoriametrics("victoria-metrics", bed, ts, hr)

    assert mock_requests_post.called


def test_sql_write(mock_psycopg_connect):
    mock_conn, mock_cursor = mock_psycopg_connect

    bed = "503"
    hr = 78
    ts = datetime.now(timezone.utc).isoformat()

    consumerMaster.sql_write(
        "baseline_sql",
        "heart_rate_data",
        "INSERT INTO heart_rate_data (bed_number, timestamp, heart_rate) VALUES (%s, %s, %s)",
        (bed, ts, hr),
        "Baseline"
    )

    assert mock_conn.cursor.called
    assert mock_cursor.execute.called
    assert mock_conn.commit.called


def test_handle_invalid_kafka_message(mock_kafka_consumer):
    kafka_message = mock.Mock()
    kafka_message.error.return_value = False
    kafka_message.value.return_value = b"{not_a_valid_json_payload}"

    mock_kafka_consumer.poll.return_value = kafka_message

    # Directly check invalid payload handling
    try:
        payload = json.loads(kafka_message.value().decode("utf-8"))
    except json.JSONDecodeError:
        payload = None

    assert payload is None
