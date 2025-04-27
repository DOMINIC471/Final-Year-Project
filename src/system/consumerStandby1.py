import os
import sys
import json
import time
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from confluent_kafka import Consumer, Producer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from prometheus_client import start_http_server, Gauge

# -----------------------------------
# SETUP
# -----------------------------------
load_dotenv()
print("\U0001F680 consumerStandby1.py starting...")

messages_per_minute = int(os.getenv("MESSAGES_PER_MINUTE", 100))
broker = os.getenv("KAFKA_BROKER", "localhost:29092")
prom_port = int(os.getenv("PROM_PORT", "8010"))
consumer_role = os.getenv("CONSUMER_ROLE", "standby1").lower()
active_db = os.getenv("ACTIVE_DB", "influxdb-standby1").lower()

if not active_db.startswith("influxdb"):
    print(f"❌ This standby consumer is for InfluxDB only. Invalid DB: {active_db}")
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[2]
write_log_dir = ROOT_DIR / "logs" / "writes" / consumer_role / "influxdb"
write_log_dir.mkdir(parents=True, exist_ok=True)
log_file = write_log_dir / f"write_times_influxdb_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.log"
own_heartbeat_file = Path("/tmp/heartbeat_standby1_alive")
promotion_lock = Path("/tmp/icu_promotion.lock")

# Metrics
start_http_server(prom_port)
kafka_messages_received = Gauge('kafka_messages_received', 'Kafka messages received')
kafka_consumer_lag = Gauge('kafka_consumer_lag', 'Kafka consumer lag')
kafka_messages_processed = Gauge('kafka_messages_processed', 'Kafka messages written')
kafka_messages_failed = Gauge('kafka_messages_failed', 'Kafka message failures')

# -----------------------------------
# InfluxDB Clients
# -----------------------------------
influx_clients = {}
token_map = {
    "influxdb-master": os.getenv("INFLUXDB_MASTER_TOKEN"),
    "influxdb-standby1": os.getenv("INFLUXDB_STANDBY1_TOKEN"),
    "influxdb-standby2": os.getenv("INFLUXDB_STANDBY2_TOKEN"),
}
for target, token in token_map.items():
    port = 8086 if target == "influxdb-master" else (8087 if target == "influxdb-standby1" else 8088)
    influx_clients[target] = {
        "client": InfluxDBClient(url=f"http://localhost:{port}", token=token, org=os.getenv("INFLUXDB_ORG", "FYP"))
    }
    influx_clients[target]["write_api"] = influx_clients[target]["client"].write_api(write_options=SYNCHRONOUS)
    influx_clients[target]["bucket"] = os.getenv("INFLUXDB_BUCKET", "sensor_data")

def log_write(bed, hr):
    with open(log_file, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}, {bed}, {hr}\n")
        f.flush()

def write_to_all_influx(bed, ts, hr):
    for target, ctx in influx_clients.items():
        try:
            ctx["write_api"].write(
                bucket=ctx["bucket"],
                org=os.getenv("INFLUXDB_ORG", "FYP"),
                record=Point("heart_rate").tag("bed_number", bed).field("heart_rate", hr).time(ts)
            )
            log_write(bed, hr)
            print(f"✅ {target}: Bed {bed}, HR {hr}")
        except Exception as e:
            kafka_messages_failed.inc()
            print(f"❌ {target} write error: {e}")

# -----------------------------------
# Heartbeat emitter for standby1
# -----------------------------------
def heartbeat_emitter():
    producer = Producer({"bootstrap.servers": broker})
    while True:
        now = datetime.now(timezone.utc)
        heartbeat = {
            "consumer_id": "standby1",
            "timestamp": now.isoformat()
        }
        try:
            producer.produce("heartbeat", json.dumps(heartbeat).encode("utf-8"))
            producer.poll(0)
        except Exception as e:
            print(f"❌ Heartbeat emitter error: {e}")
        own_heartbeat_file.touch()
        time.sleep(2)

# -----------------------------------
# Main consumer logic
# -----------------------------------
consumer = Consumer({
    "bootstrap.servers": broker,
    "group.id": f"{consumer_role}-heartbeat-group-{uuid.uuid4()}",
    "auto.offset.reset": "latest"
})
consumer.subscribe(["heartbeat"])
print(f"🚑 Subscribed to heartbeat")

print("⏳ Monitoring master heartbeat...")
last_master_heartbeat = None
startup_time = datetime.now(timezone.utc)

GRACE_PERIOD = 8
MAX_HEARTBEAT_LAG = 15
HEARTBEAT_WAIT_TIME = 10

try:
    while True:
        msg = consumer.poll(1.0)
        now = datetime.now(timezone.utc)
        time_since_start = (now - startup_time).total_seconds()

        if msg and not msg.error():
            payload = json.loads(msg.value())
            if payload.get("consumer_id") == "master":
                last_master_heartbeat = now
                print(f"💓 Master heartbeat @ {now.isoformat()}")

        if time_since_start > HEARTBEAT_WAIT_TIME and last_master_heartbeat is None:
            print("❌ No heartbeat received during startup. Promoting...")
            break

        if last_master_heartbeat and time_since_start > GRACE_PERIOD:
            lag = (now - last_master_heartbeat).total_seconds()
            if lag > MAX_HEARTBEAT_LAG:
                print("✅ Master heartbeat lag detected. Promoting...")
                break

except KeyboardInterrupt:
    print("🛑 Standby1 interrupted during monitoring.")
finally:
    consumer.close()

# -----------------------------------
# After Promotion
# -----------------------------------
promotion_lock.write_text("standby1")
own_heartbeat_file.touch()

print("🚨 FAILOVER: Standby1 assuming master consumer duties!")
heartbeat_thread = threading.Thread(target=heartbeat_emitter, daemon=True)
heartbeat_thread.start()

consumer = Consumer({
    "bootstrap.servers": broker,
    "group.id": f"standby1-heart_rate-group-{uuid.uuid4()}",
    "auto.offset.reset": "latest"
})
consumer.subscribe(["heart_rate"])
print("🚑 Subscribed to 'heart_rate' topic after promotion.")

try:
    while True:
        msg = consumer.poll(1.0)
        now = datetime.now(timezone.utc)

        if msg and not msg.error():
            try:
                payload = json.loads(msg.value())
                bed = payload["bed_number"]
                hr = payload["heart_rate"]
                ts = datetime.fromisoformat(payload["timestamp"]).astimezone(timezone.utc).isoformat(timespec="milliseconds")

                kafka_messages_received.inc()
                kafka_consumer_lag.set(0)
                write_to_all_influx(bed, ts, hr)
                kafka_messages_processed.inc()
            except Exception as e:
                print(f"⚠️ Invalid message: {e}")
                kafka_messages_failed.inc()

        # Detect if master has recovered
        heartbeat_msg = consumer.poll(0)
        if heartbeat_msg and not heartbeat_msg.error():
            payload = json.loads(heartbeat_msg.value())
            if payload.get("consumer_id") == "master":
                print("🎉 Master has recovered! Demoting standby1...")
                break

except KeyboardInterrupt:
    print("🛑 Standby1 interrupted during failover mode.")
finally:
    consumer.close()
    heartbeat_thread.join(timeout=1)
    if own_heartbeat_file.exists():
        own_heartbeat_file.unlink()
    if promotion_lock.exists():
        try:
            if promotion_lock.read_text().strip() == "standby1":
                promotion_lock.unlink()
                print("🧹 Cleaned up promotion lock after demotion.")
        except Exception as e:
            print(f"⚠️ Failed to clean promotion lock: {e}")
    print("✅ Standby1 shutdown complete.")
