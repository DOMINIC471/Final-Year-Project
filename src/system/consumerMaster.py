from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2
from datetime import datetime, timezone
import json
from prometheus_client import start_http_server, Gauge
import requests
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# -------------------------------------
# LOAD ENV
# -------------------------------------
load_dotenv()
print("\U0001F680 consumerMaster.py starting...")

try:
    messages_per_minute = int(os.getenv("MESSAGES_PER_MINUTE", 100))
    active_db = os.getenv("ACTIVE_DB", "influxdb").lower()
    broker = os.getenv("KAFKA_BROKER", "localhost:29092")
    prom_port = int(os.getenv("PROM_PORT", "8000"))
    is_test_mode = os.getenv("IS_TEST_MODE", "0") == "1"
except Exception as e:
    print(f"\u274c Failed to load environment variables: {e}")
    sys.exit(1)

# -------------------------------------
# TARGET MAPPINGS
# -------------------------------------
container_to_type = {
    "influxdb-master": "influxdb",
    "influxdb-standby1": "influxdb",
    "influxdb-standby2": "influxdb",
    "timescaledb": "timescaledb",
    "victoria-metrics": "victoriametrics",
    "baseline_sql": "baseline",
}

influxdb_ports = {
    "influxdb-master": 8086,
    "influxdb-standby1": 8087,
    "influxdb-standby2": 8088,
}

# -------------------------------------
# TARGETS
# -------------------------------------
if is_test_mode:
    write_targets = [
        "influxdb-master",
        "timescaledb",
        "victoria-metrics",
        "baseline_sql"
    ]
else:
    write_targets = [
        "influxdb-master",
        "influxdb-standby1",
        "influxdb-standby2"
    ]

if active_db not in [container_to_type[db] for db in write_targets]:
    print(f"\u274c Unsupported ACTIVE_DB in this context: {active_db}")
    sys.exit(1)

# -------------------------------------
# LOGGING PATHS (TEST MODE)
# -------------------------------------
rate_label = f"{messages_per_minute}mpm"
run_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

if is_test_mode:
    base_log_dir = Path("test_results")
    write_log_dir = base_log_dir / "writes" / active_db
    per_message_dir = base_log_dir / "per_message" / active_db
    system_info_dir = base_log_dir / "system_info"
    global_dir = base_log_dir / "global" / active_db
    for p in [write_log_dir, per_message_dir, system_info_dir, global_dir]:
        p.mkdir(parents=True, exist_ok=True)
else:
    base_log_dir = Path("logs") / "writes" / "master" / active_db
    write_log_dir = base_log_dir
    write_log_dir.mkdir(parents=True, exist_ok=True)

log_filename = f"write_times_{rate_label}_{active_db}_{run_suffix}.log"
write_log_file = write_log_dir / log_filename

# -------------------------------------
# METRICS
# -------------------------------------
start_http_server(prom_port)
kafka_messages_received = Gauge('kafka_messages_received', 'Kafka messages received')
kafka_consumer_lag = Gauge('kafka_consumer_lag', 'Kafka consumer lag')
kafka_messages_processed = Gauge('kafka_messages_processed', 'Kafka messages written')
kafka_messages_failed = Gauge('kafka_messages_failed', 'Kafka message failures')

# -------------------------------------
# WRITE LOG FUNCTION
# -------------------------------------
def log_write_time(bed_number, heart_rate):
    with open(write_log_file, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}, {bed_number}, {heart_rate}\n")

# -------------------------------------
# DB WRITERS
# -------------------------------------
def write_to_influxdb(target, bed, ts, hr):
    try:
        token_map = {
            "influxdb-master": "INFLUXDB_MASTER_TOKEN",
            "influxdb-standby1": "INFLUXDB_STANDBY1_TOKEN",
            "influxdb-standby2": "INFLUXDB_STANDBY2_TOKEN"
        }
        port = influxdb_ports[target]
        token = os.getenv(token_map[target], "MISSING_TOKEN")

        client = InfluxDBClient(
            url=f"http://localhost:{port}",
            token=token,
            org=os.getenv("INFLUXDB_ORG", "FYP")
        )
        write_api = client.write_api(write_options=SYNCHRONOUS)
        bucket = os.getenv("INFLUXDB_BUCKET", "sensor_data")
        write_api.write(
            bucket=bucket,
            org=os.getenv("INFLUXDB_ORG", "FYP"),
            record=Point("heart_rate").tag("bed_number", bed).field("heart_rate", hr).time(ts)
        )
        print(f"✅ {target}: Bed {bed}, HR {hr}")
    except Exception as e:
        print(f"❌ InfluxDB error [{target}]: {e}")
        kafka_messages_failed.inc()

def write_to_victoriametrics(target, bed, ts, hr):
    try:
        epoch_ts = int(datetime.fromisoformat(ts).timestamp())
        res = requests.post(
            "http://localhost:8428/api/v1/import/prometheus",
            data=f'heart_rate{{bed="{bed}"}} {hr} {epoch_ts}'
        )
        if res.status_code not in [200, 204]:
            raise Exception(f"HTTP {res.status_code}")
        print(f"✅ {target}: Bed {bed}, HR {hr}")
    except Exception as e:
        print(f"❌ VM error [{target}]: {e}")
        kafka_messages_failed.inc()

def sql_write(target, table, query, values, label):
    try:
        conn = psycopg2.connect(
            dbname="baseline_sql" if "baseline" in target else "sensor_data",
            user=os.getenv("BASELINE_USER", "macbookpro") if "baseline" in target else os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("BASELINE_PASSWORD", "mybaselinepassword") if "baseline" in target else os.getenv("POSTGRES_PASSWORD", "mynewpassword"),
            host="localhost",
            port=5433 if "baseline" in target else 5432
        )
        cursor = conn.cursor()
        cursor.execute(query, values)
        conn.commit()
        print(f"✅ {target}: Bed {values[1]}, HR {values[2]}")
        conn.close()
    except Exception as e:
        print(f"❌ SQL error [{target}]: {e}")
        kafka_messages_failed.inc()

# -------------------------------------
# Start Heartbeat Emitter
# -------------------------------------
print("🫀 Starting heartbeat emitter...")
heartbeat_env = os.environ.copy()
heartbeat_env["CONSUMER_ID"] = "master"
heartbeat_process = subprocess.Popen(
    ["python3", "src/system/heartbeat_emitter.py", "master"],
    env=heartbeat_env
)

# -------------------------------------
# KAFKA LOOP
# -------------------------------------
print("🔌 Connecting to Kafka broker...")
consumer = Consumer({
    "bootstrap.servers": broker,
    "group.id": f"master-{active_db}-group",
    "auto.offset.reset": "latest"
})
consumer.subscribe(["heart_rate"])
print("📡 Subscribed to 'heart_rate' topic.")

try:
    while True:
        msg = consumer.poll(1.0)
        if not msg or msg.error():
            continue

        try:
            payload = json.loads(msg.value().decode("utf-8"))
            bed = payload["bed_number"]
            hr = payload["heart_rate"]
            ts = datetime.fromisoformat(payload["timestamp"]).astimezone(timezone.utc).isoformat(timespec="milliseconds")
        except Exception as e:
            kafka_messages_failed.inc()
            print(f"⚠️ Invalid msg: {e}")
            continue

        kafka_messages_received.inc()
        kafka_consumer_lag.set(0)
        log_write_time(bed, hr)

        for target in write_targets:
            typ = container_to_type[target]
            if typ == "influxdb":
                write_to_influxdb(target, bed, ts, hr)
            elif typ == "victoriametrics":
                write_to_victoriametrics(target, bed, ts, hr)
            elif typ == "timescaledb":
                sql_write(target, "sensor_data", "INSERT INTO sensor_data (time, bed_number, heart_rate) VALUES (%s, %s, %s)", (datetime.fromisoformat(ts), bed, hr), "TimescaleDB")
            elif typ == "baseline":
                sql_write(target, "heart_rate_data", "INSERT INTO heart_rate_data (bed_number, timestamp, heart_rate) VALUES (%s, %s, %s)", (bed, ts, hr), "Baseline")

        kafka_messages_processed.inc()

except KeyboardInterrupt:
    print("\U0001F6D1 Consumer terminated.")
except Exception as e:
    print(f"\u274c Unhandled exception in consumer loop: {e}")

finally:
    print("🧹 Shutting down master consumer...")
    consumer.close()

    if heartbeat_process:
        print("🫀 Terminating heartbeat emitter...")
        heartbeat_process.terminate()
        heartbeat_process.wait()

    print("✅ Master consumer shutdown complete.")
