from confluent_kafka import Consumer, Producer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2
from datetime import datetime
import time
import json

# InfluxDB setup
bucket = "sensor_data"
org = "FYP"
token = "i1tGACkYPJkuTd1QHe8_PyAA9wspcTf2tVkpAmNEtqbv-GYmw09fg-QWETrGwvWAjnQuB8Rv99MLzWFxOSVTvQ=="
token_standby = "NhNHBVzXz68MTGBqnPEcw2k12QEiBPFnDuwse3YgyjW5sMdXdqSev3evOBC7ET9hgYF6kOv62ryYsIlXNqIqmw=="
url_master = "http://localhost:8086"
url_standby = "http://localhost:8087"

# TimescaleDB setup
timescale_conn = psycopg2.connect(
    dbname="sensor_data",
    user="postgres",
    password="new_password",  # Replace with your TimescaleDB password
    host="localhost",
    port=5432
)
timescale_cursor = timescale_conn.cursor()

# Connect to InfluxDB (Master and Standby)
client_master = InfluxDBClient(url=url_master, token=token, org=org)
client_standby = InfluxDBClient(url=url_standby, token=token_standby, org=org)

write_api_master = client_master.write_api(write_options=SYNCHRONOUS)
write_api_standby = client_standby.write_api(write_options=SYNCHRONOUS)

# Kafka Consumer setup
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'sensor-data-group',
    'auto.offset.reset': 'earliest'
})

# Subscribe to all sensor topics
topics = [
    "temperature-topic", "humidity-topic", "pressure-topic",
    "light-topic", "co2-topic", "noise-topic",
    "motion-topic", "air_quality-topic", "heart_rate-topic",
    "oxygen_saturation-topic"
]
consumer.subscribe(topics)

# Kafka Producer setup (to send heartbeats)
producer = Producer({
    'bootstrap.servers': 'localhost:9092'
})

# Variables to track latencies
latencies_master = []
latencies_standby = []
latencies_timescale = []

def send_heartbeat():
    """Send periodic heartbeat to Kafka."""
    status_message = f"Consumer is alive at {datetime.now()}"
    producer.produce('status-topic', value=status_message)
    producer.flush()
    print(f"Heartbeat sent: {status_message}")

def is_master_alive():
    """Check if the master database is reachable."""
    try:
        client_master.ping()
        return True
    except Exception as e:
        print(f"Master database is down: {e}")
        return False

def write_to_timescale(sensor_id, timestamp, value):
    """Write sensor data to TimescaleDB and measure latency."""
    try:
        start_time = time.time()
        query = """
        INSERT INTO sensor_data (time, sensor_id, value)
        VALUES (%s, %s, %s)
        """
        timescale_cursor.execute(query, (datetime.utcfromtimestamp(timestamp), sensor_id, value))
        timescale_conn.commit()
        latency = (time.time() - start_time) * 1000  # Latency in ms
        latencies_timescale.append(latency)
        print(f"Data written to TimescaleDB for {sensor_id}. Latency: {latency:.2f} ms")
    except Exception as e:
        print(f"Failed to write to TimescaleDB: {e}")

try:
    last_heartbeat_time = time.time()
    heartbeat_interval = 5  # Heartbeat every 5 seconds

    while True:
        msg = consumer.poll(1.0)
        current_time = time.time()

        # Send periodic heartbeats
        if current_time - last_heartbeat_time >= heartbeat_interval:
            send_heartbeat()
            last_heartbeat_time = current_time

        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        # Log raw message for debugging
        print(f"Raw message received: {msg.value()}")

        try:
            data = json.loads(msg.value().decode('utf-8'))
        except json.JSONDecodeError:
            print(f"Malformed message received: {msg.value()}")
            continue

        # Extract data fields
        sensor_id = data.get("sensor_id", "unknown_sensor")
        timestamp = data.get("timestamp")
        value = data.get("value")

        # Validate data
        if not isinstance(timestamp, (int, float)):
            print(f"Invalid timestamp format: {timestamp}")
            continue
        if value is None or not isinstance(value, (int, float)):
            print(f"Invalid value format: {value}")
            continue

        # Calculate processing time
        processing_time = current_time - timestamp

        # Log timestamps and processing time for debugging
        print(f"Current time: {current_time}, Message timestamp: {timestamp}")
        print(f"Processing time for {sensor_id}: {processing_time:.3f} seconds")

        # Skip invalid processing times
        if processing_time < 0 or processing_time > 5:
            print(f"Warning: Anomalous processing time ({processing_time:.3f}) for {sensor_id}")
            continue

        # Check master database availability
        master_alive = is_master_alive()

        try:
            # Measure write latency for InfluxDB Master
            if master_alive:
                start_time = time.time()
                try:
                    write_api_master.write(bucket=bucket, org=org, record=Point("sensor_data")
                                            .tag("sensor_id", sensor_id)
                                            .field("value", value)
                                            .time(int(timestamp), write_precision='s'))
                    latency = (time.time() - start_time) * 1000
                    latencies_master.append(latency)
                    print(f"Data written to Master InfluxDB for {sensor_id}. Latency: {latency:.2f} ms")
                except Exception as e:
                    print(f"Failed to write to Master InfluxDB: {e}")

            # Measure write latency for InfluxDB Standby
            start_time = time.time()
            write_api_standby.write(bucket=bucket, org=org, record=Point("sensor_data")
                                    .tag("sensor_id", sensor_id)
                                    .field("value", value)
                                    .time(int(timestamp), write_precision='s'))
            latency = (time.time() - start_time) * 1000
            latencies_standby.append(latency)
            print(f"Data written to Standby InfluxDB for {sensor_id}. Latency: {latency:.2f} ms")

            # Write processing time
            if master_alive:
                try:
                    write_api_master.write(bucket=bucket, org=org, record=Point("processing_time")
                                            .tag("sensor_id", sensor_id)
                                            .field("time_taken", processing_time)
                                            .time(int(timestamp), write_precision='s'))
                    print(f"Processing time written to Master InfluxDB for {sensor_id}")
                except Exception as e:
                    print(f"Failed to write processing time to Master InfluxDB: {e}")

            write_api_standby.write(bucket=bucket, org=org, record=Point("processing_time")
                                    .tag("sensor_id", sensor_id)
                                    .field("time_taken", processing_time)
                                    .time(int(timestamp), write_precision='s'))
            print(f"Processing time written to Standby InfluxDB for {sensor_id}")

            # Write data to TimescaleDB
            write_to_timescale(sensor_id, timestamp, value)

        except Exception as e:
            print(f"Error writing to databases: {e}")

except KeyboardInterrupt:
    print("\nConsumer interrupted.")

finally:
    # Calculate and print average latencies
    def calculate_average(latencies):
        return sum(latencies) / len(latencies) if latencies else 0

    print("\nAverage write latencies:")
    print(f"InfluxDB Master: {calculate_average(latencies_master):.2f} ms")
    print(f"InfluxDB Standby: {calculate_average(latencies_standby):.2f} ms")
    print(f"TimescaleDB: {calculate_average(latencies_timescale):.2f} ms")

    consumer.close()
    timescale_cursor.close()
    timescale_conn.close()
    print("Consumer and TimescaleDB connection closed.")
