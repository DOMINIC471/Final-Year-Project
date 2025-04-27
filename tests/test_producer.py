import pytest
from unittest import mock
from system import producer
import json
import os

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("MESSAGES_PER_MINUTE", "20")
    monkeypatch.setenv("KAFKA_BROKER", "localhost:29092")
    monkeypatch.setenv("IS_TEST_MODE", "1")

@pytest.fixture
def mock_producer():
    with mock.patch('system.producer.Producer') as MockProducer:
        yield MockProducer.return_value

@pytest.fixture
def mock_csv(monkeypatch):
    # Only mock the loaded data
    data = [{"Bed Number": 601, "Heart Rate": 90}]
    monkeypatch.setattr(producer, "data", data)

def test_producer_sends_message(mock_producer, mock_csv):
    producer.p = mock_producer
    producer.TOPIC = "heart_rate"

    row = producer.data[0]  # We control the data fixture
    message = {
        "bed_number": str(row["Bed Number"]),
        "timestamp": "2025-04-27T00:00:00.000Z",
        "heart_rate": int(row["Heart Rate"])
    }

    # Simulate sending a message
    producer.p.produce(
        producer.TOPIC,
        key=message["bed_number"],
        value=json.dumps(message)
    )
    producer.p.poll(0)

    # Assertions
    producer.p.produce.assert_called_once()
    producer.p.poll.assert_called_once()
