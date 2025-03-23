from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2
from datetime import datetime
import json
from prometheus_client import start_http_server, Gauge
import requests

# InfluxDB Master Setup
bucket = "sensor_data"
org = "FYP"
token_master = "i1tGACkYPJkuTd1QHe8_PyAA9wspcTf2tVkpAmNEtqbv-GYmw09fg-QWETrGwvWAjnQuB8Rv99MLzWFxOSVTvQ=="
url_master = "http://localhost:8086"

client_master = InfluxDBClient(url=url_master, token=token_master, org=org)
write_api_master = client_master.write_api(write_options=SYNCHRONOUS)

# TimescaleDB Master Setup
timescale_conn_master = psycopg2.connect(
    dbname="sensor_data",
    user="postgres",
    password="mynewpassword",
    host="localhost",
    port=5432
)
timescale_cursor_master = timescale_conn_master.cursor()

# Baseline PostgreSQL Setup (on port 5433)
baseline_conn = psycopg2.connect(
    dbname="baseline_sql",
    user="macbookpro",  # replace with your actual PostgreSQL user if different
    password="mybaselinepassword",         # leave empty if using peer auth; set if using password
    host="localhost",
    port=5433
)
baseline_cursor = baseline_conn.cursor()

# VictoriaMetrics Setup
victoriametrics_url = "http://localhost:8428/api/v1/import"

# Kafka Consumer Setup
consumer_master = Consumer({
    'bootstrap.servers': 'localhost:29092',
    'group.id': 'master-group',
    'auto.offset.reset': 'earliest'
})

consumer_master.subscribe(["heart_rate"])

# Prometheus Metrics for Kafka Exporter
kafka_messages_received = Gauge('kafka_messages_received', 'Number of messages received from Kafka')
kafka_consumer_lag = Gauge('kafka_consumer_lag', 'Kafka consumer lag (messages behind)')
kafka_messages_processed = Gauge('kafka_messages_processed', 'Number of successfully processed messages')

# Function to Write to TimescaleDB Master
def write_to_timescale_master(bed_number, timestamp, heart_rate):
    try:
        query = """
        INSERT INTO sensor_data (time, bed_number, heart_rate)
        VALUES (%s, %s, %s)
        """
        timescale_cursor_master.execute(query, (datetime.fromisoformat(timestamp), bed_number, heart_rate))
        timescale_conn_master.commit()
        print(f"✅ Data written to TimescaleDB: {bed_number}, {timestamp}, {heart_rate}")
    except Exception as e:
        timescale_conn_master.rollback()
        print(f"❌ Failed to write to TimescaleDB: {e}")

# Function to Write to Baseline SQL
def write_to_baseline_sql(bed_number, timestamp, heart_rate):
    try:
        query = """
        INSERT INTO heart_rate_data (bed_number, timestamp, heart_rate)
        VALUES (%s, %s, %s)
        """
        baseline_cursor.execute(query, (bed_number, timestamp, heart_rate))
        baseline_conn.commit()
        print(f"🟨 Data written to baseline SQL: {bed_number}, {timestamp}, {heart_rate}")
    except Exception as e:
        baseline_conn.rollback()
        print(f"❌ Failed to write to baseline SQL: {e}")

# Function to Send Data to VictoriaMetrics
def write_to_victoriametrics(bed_number, timestamp, heart_rate):
    try:
        data = [
            {
                "metric": {
                    "__name__": "heart_rate",
                    "bed_number": str(bed_number)
                },
                "values": [heart_rate],
                "timestamps": [int(datetime.fromisoformat(timestamp).timestamp() * 1000)]
            }
        ]
        response = requests.post(victoriametrics_url, json=data)
        if response.status_code == 200:
            print(f"✅ Data written to VictoriaMetrics: {bed_number}, {timestamp}, {heart_rate}")
        else:
            print(f"❌ Failed to write to VictoriaMetrics: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"❌ Error writing to VictoriaMetrics: {e}")

# Start Prometheus HTTP server for metrics (port 8000)
start_http_server(8000)

# Main Consumer Loop
try:
    while True:
        msg = consumer_master.poll(1.0)

        if msg is None:
            continue
        if msg.error():
            print(f"⚠️ Consumer error: {msg.error()}")
            continue

        try:
            data = json.loads(msg.value().decode('utf-8'))
        except json.JSONDecodeError:
            print(f"❌ Malformed message: {msg.value()}")
            continue

        bed_number = data.get("bed_number")
        timestamp = data.get("timestamp")
        heart_rate = data.get("heart_rate")

        if not timestamp or not heart_rate:
            print(f"⚠️ Invalid data: {data}")
            continue

        print(f"📥 Received: Bed {bed_number}, Timestamp {timestamp}, Heart Rate {heart_rate}")

        # Update Prometheus Metrics
        kafka_messages_received.inc()
        kafka_consumer_lag.set(0)

        try:
            iso_timestamp = datetime.fromisoformat(timestamp).isoformat()
        except Exception as e:
            print(f"❌ Invalid timestamp format: {timestamp}. Skipping. Error: {e}")
            continue

        # Write to InfluxDB
        try:
            write_api_master.write(
                bucket=bucket,
                org=org,
                record=Point("heart_rate")
                .tag("bed_number", bed_number)
                .field("heart_rate", heart_rate)
                .time(iso_timestamp)
            )
            print(f"✅ Written to InfluxDB: Bed {bed_number}, Heart Rate: {heart_rate}, Timestamp: {iso_timestamp}")
        except Exception as e:
            print(f"❌ Failed to write to InfluxDB: {e}")

        # Write to TimescaleDB
        write_to_timescale_master(bed_number, iso_timestamp, heart_rate)

        # Write to Baseline PostgreSQL
        write_to_baseline_sql(bed_number, iso_timestamp, heart_rate)

        # Write to VictoriaMetrics
        write_to_victoriametrics(bed_number, iso_timestamp, heart_rate)

        # Update processed messages metric
        kafka_messages_processed.inc()

except KeyboardInterrupt:
    print("\n🛑 Master Consumer interrupted.")

finally:
    consumer_master.close()
    timescale_cursor_master.close()
    timescale_conn_master.close()
    baseline_cursor.close()
    baseline_conn.close()
    print("✅ Master Consumer closed.")
    print("🟨 Baseline SQL DB closed.")
