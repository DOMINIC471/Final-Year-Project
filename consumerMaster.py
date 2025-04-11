from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2
from datetime import datetime, timezone
import json
from prometheus_client import start_http_server, Gauge
import requests
import os

# -------------------------------------
# CONFIGURATION (ENV-AWARE)
# -------------------------------------
messages_per_minute = int(os.getenv("MESSAGES_PER_MINUTE", 100))
active_db = os.getenv("ACTIVE_DB", "victoriametrics").lower()
rate_label = f"{messages_per_minute}mpm"

# Unique timestamp for this run to avoid overwriting logs
run_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

# Logging
write_log_dir = os.path.join("logs", "writes", active_db)
os.makedirs(write_log_dir, exist_ok=True)
write_log_file = os.path.join(write_log_dir, f"write_times_{rate_label}_{active_db}_{run_suffix}.log")

def log_write_time(bed_number, heart_rate):
    with open(write_log_file, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}, {bed_number}, {heart_rate}\n")

# -------------------------------------
# DB CONNECTIONS
# -------------------------------------
db_clients = {}

match active_db:
    case "influxdb":
        db_clients["client"] = InfluxDBClient(
            url="http://localhost:8086",
            token="i1tGACkYPJkuTd1QHe8_PyAA9wspcTf2tVkpAmNEtqbv-GYmw09fg-QWETrGwvWAjnQuB8Rv99MLzWFxOSVTvQ==",
            org="FYP"
        )
        db_clients["write_api"] = db_clients["client"].write_api(write_options=SYNCHRONOUS)
        db_clients["bucket"] = "sensor_data"

    case "timescaledb":
        conn = psycopg2.connect(
            dbname="sensor_data",
            user="postgres",
            password="mynewpassword",
            host="localhost",
            port=5432
        )
        db_clients["conn"] = conn
        db_clients["cursor"] = conn.cursor()

    case "baseline":
        conn = psycopg2.connect(
            dbname="baseline_sql",
            user="macbookpro",
            password="mybaselinepassword",
            host="localhost",
            port=5433
        )
        db_clients["conn"] = conn
        db_clients["cursor"] = conn.cursor()

    case "victoriametrics":
        db_clients["url"] = "http://localhost:8428/api/v1/import/prometheus"

# -------------------------------------
# PROMETHEUS METRICS
# -------------------------------------
start_http_server(8000)
kafka_messages_received = Gauge('kafka_messages_received', 'Number of messages received from Kafka')
kafka_consumer_lag = Gauge('kafka_consumer_lag', 'Kafka consumer lag (messages behind)')
kafka_messages_processed = Gauge('kafka_messages_processed', 'Number of successfully processed messages')
kafka_messages_failed = Gauge('kafka_messages_failed', 'Number of failed DB writes')

# -------------------------------------
# DB WRITE FUNCTIONS
# -------------------------------------
def write_to_influxdb(bed_number, timestamp, heart_rate):
    try:
        db_clients["write_api"].write(
            bucket=db_clients["bucket"],
            org="FYP",
            record=Point("heart_rate")
            .tag("bed_number", bed_number)
            .field("heart_rate", heart_rate)
            .time(timestamp)
        )
        print(f"✅ InfluxDB: Bed {bed_number}, HR {heart_rate}, {timestamp}")
        log_write_time(bed_number, heart_rate)
    except Exception as e:
        kafka_messages_failed.inc()
        print(f"❌ InfluxDB write failed: {e}")

def write_to_timescaledb(bed_number, timestamp, heart_rate):
    try:
        db_clients["cursor"].execute("""
            INSERT INTO sensor_data (time, bed_number, heart_rate)
            VALUES (%s, %s, %s)
        """, (datetime.fromisoformat(timestamp), bed_number, heart_rate))
        db_clients["conn"].commit()
        print(f"✅ TimescaleDB: Bed {bed_number}, HR {heart_rate}, {timestamp}")
        log_write_time(bed_number, heart_rate)
    except Exception as e:
        db_clients["conn"].rollback()
        kafka_messages_failed.inc()
        print(f"❌ TimescaleDB write failed: {e}")

def write_to_baseline(bed_number, timestamp, heart_rate):
    try:
        db_clients["cursor"].execute("""
            INSERT INTO heart_rate_data (bed_number, timestamp, heart_rate)
            VALUES (%s, %s, %s)
        """, (bed_number, timestamp, heart_rate))
        db_clients["conn"].commit()
        print(f"🟨 Baseline SQL: Bed {bed_number}, HR {heart_rate}, {timestamp}")
        log_write_time(bed_number, heart_rate)
    except Exception as e:
        db_clients["conn"].rollback()
        kafka_messages_failed.inc()
        print(f"❌ Baseline SQL write failed: {e}")

def write_to_victoriametrics(bed_number, timestamp, heart_rate):
    try:
        epoch_ts = datetime.fromisoformat(timestamp).timestamp()
        line = f'heart_rate{{bed="{bed_number}"}} {heart_rate} {int(epoch_ts)}'
        response = requests.post(db_clients["url"], data=line)
        if response.status_code not in [200, 204]:
            raise RuntimeError(f"VictoriaMetrics error: {response.status_code}, {response.text}")
        print(f"✅ VictoriaMetrics: Bed {bed_number}, HR {heart_rate}, {timestamp}")
        log_write_time(bed_number, heart_rate)
    except Exception as e:
        kafka_messages_failed.inc()
        print(f"❌ VictoriaMetrics write failed: {e}")

# -------------------------------------
# KAFKA CONSUMER
# -------------------------------------
consumer = Consumer({
    'bootstrap.servers': 'localhost:29092',
    'group.id': 'master-group',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(["heart_rate"])

# -------------------------------------
# CONSUMPTION LOOP
# -------------------------------------
try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"⚠️ Kafka error: {msg.error()}")
            continue

        try:
            payload = json.loads(msg.value().decode('utf-8'))
        except json.JSONDecodeError:
            print(f"❌ JSON decode error: {msg.value()}")
            kafka_messages_failed.inc()
            continue

        bed_number = payload.get("bed_number")
        timestamp = payload.get("timestamp")
        heart_rate = payload.get("heart_rate")

        if not (bed_number and timestamp and heart_rate):
            print(f"⚠️ Incomplete message: {payload}")
            kafka_messages_failed.inc()
            continue

        print(f"📥 Kafka: Bed {bed_number}, Time {timestamp}, HR {heart_rate}")
        kafka_messages_received.inc()
        kafka_consumer_lag.set(0)

        try:
            iso_ts = datetime.fromisoformat(timestamp).isoformat()
        except Exception as e:
            print(f"❌ Timestamp error: {e}")
            kafka_messages_failed.inc()
            continue

        match active_db:
            case "influxdb":
                write_to_influxdb(bed_number, iso_ts, heart_rate)
            case "timescaledb":
                write_to_timescaledb(bed_number, iso_ts, heart_rate)
            case "baseline":
                write_to_baseline(bed_number, iso_ts, heart_rate)
            case "victoriametrics":
                write_to_victoriametrics(bed_number, iso_ts, heart_rate)

        kafka_messages_processed.inc()

except KeyboardInterrupt:
    print("\n🛑 Master Consumer stopped.")

finally:
    consumer.close()
    if active_db in ["timescaledb", "baseline"]:
        db_clients["cursor"].close()
        db_clients["conn"].close()
    print("✅ Kafka consumer and DB connections closed.")
