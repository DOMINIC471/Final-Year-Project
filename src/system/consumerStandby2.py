import os
import sys
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from confluent_kafka import Consumer, Producer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from prometheus_client import start_http_server, Gauge

# -------------------------------------
# ENV & CONFIG
# -------------------------------------
load_dotenv()
print("\U0001F680 consumerStandby2.py starting...")

messages_per_minute = int(os.getenv("MESSAGES_PER_MINUTE", 100))
active_db = os.getenv("ACTIVE_DB", "influxdb-standby2").lower()
broker = os.getenv("KAFKA_BROKER", "localhost:29092")
consumer_role = os.getenv("CONSUMER_ID", "standby2").lower()
prom_port = int(os.getenv("PROM_PORT", "8020"))

if not active_db.startswith("influxdb"):
    print(f"❌ This standby consumer is for InfluxDB only. Invalid DB: {active_db}")
    sys.exit(1)

ROOT_DIR = Path(__file__).resolve().parents[2]
write_log_dir = ROOT_DIR / "logs" / "writes" / consumer_role / "influxdb"
write_log_dir.mkdir(parents=True, exist_ok=True)
log_file = write_log_dir / f"write_times_influxdb_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.log"
own_heartbeat_file = Path("/tmp/heartbeat_standby2_alive")
promotion_lock = Path("/tmp/icu_promotion.lock")

# -------------------------------------
# LOGGING
# -------------------------------------
def log_write(bed, hr):
    with open(log_file, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}, {bed}, {hr}\n")
        f.flush()

# -------------------------------------
# METRICS
# -------------------------------------
start_http_server(prom_port)
kafka_messages_received = Gauge('kafka_messages_received', 'Kafka messages received by standby2')
kafka_consumer_lag = Gauge('kafka_consumer_lag', 'Kafka consumer lag for standby2')
kafka_messages_processed = Gauge('kafka_messages_processed', 'Kafka messages processed by standby2')
kafka_messages_failed = Gauge('kafka_messages_failed', 'Kafka message failures in standby2')

# -------------------------------------
# InfluxDB Clients
# -------------------------------------
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

# -------------------------------------
# HEARTBEAT PRODUCER
# -------------------------------------
heartbeat_producer = Producer({"bootstrap.servers": broker})

def emit_heartbeat():
    now = datetime.now(timezone.utc)
    heartbeat = {
        "consumer_id": "standby2",
        "timestamp": now.isoformat()
    }
    heartbeat_producer.produce("heartbeat", json.dumps(heartbeat).encode("utf-8"))
    heartbeat_producer.poll(0)

# -------------------------------------
# HEARTBEAT MONITORING
# -------------------------------------
print("\u23f3 Listening for master & standby1 heartbeats...")
consumer = Consumer({
    "bootstrap.servers": broker,
    "group.id": f"{consumer_role}-heartbeat-group-{uuid.uuid4()}",
    "auto.offset.reset": "latest"
})
consumer.subscribe(["heartbeat"])
print("🚁 Subscribed to heartbeat")

last_master_beat = None
last_standby1_beat = None
startup_time = datetime.now(timezone.utc)
GRACE_PERIOD = 8

try:
    while True:
        msg = consumer.poll(1.0)
        now = datetime.now(timezone.utc)

        if msg and not msg.error():
            try:
                payload = json.loads(msg.value())
                cid = payload.get("consumer_id")
                if cid == "master":
                    last_master_beat = now
                    print(f"💓 Master heartbeat @ {now.isoformat()}")
                elif cid == "standby1":
                    last_standby1_beat = now
                    print(f"💓 Standby1 heartbeat @ {now.isoformat()}")
            except Exception as e:
                print(f"⚠️ Bad heartbeat: {e}")

        time_since_start = (now - startup_time).total_seconds()

        if (
            time_since_start > GRACE_PERIOD and
            (not last_master_beat or now - last_master_beat > timedelta(seconds=10)) and
            (not last_standby1_beat or now - last_standby1_beat > timedelta(seconds=10))
        ):
            print("🔥 Both master and standby1 are dead. Checking promotion lock...")
            if promotion_lock.exists():
                print("⏸️ Promotion lock exists — another standby already active. Staying passive.")
                time.sleep(5)
                continue
            else:
                print("⏳ Waiting 8 seconds to confirm...")
                time.sleep(8)
                if promotion_lock.exists():
                    print("⏸️ Promotion lock appeared. Staying passive.")
                    continue
                print("🔥 No promotion lock — standby2 promoting!")
                promotion_lock.write_text("standby2")
                own_heartbeat_file.touch()
                break

        time.sleep(1)

    # --------------------------------------------------------
    consumer.close()
    consumer = Consumer({
        "bootstrap.servers": broker,
        "group.id": f"{consumer_role}-active-group-{uuid.uuid4()}",
        "auto.offset.reset": "latest"
    })
    consumer.subscribe(["heart_rate"])
    print("🚃 Subscribed to heart_rate as active standby2!")

    last_heartbeat_emit = time.time()

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
                print(f"⚠️ Bad message: {e}")
                kafka_messages_failed.inc()

        if time.time() - last_heartbeat_emit >= 2:
            emit_heartbeat()
            own_heartbeat_file.touch()
            last_heartbeat_emit = time.time()

except KeyboardInterrupt:
    print("\n🛑 Standby2 Consumer stopped.")
finally:
    consumer.close()
    heartbeat_producer.flush()
    if own_heartbeat_file.exists():
        own_heartbeat_file.unlink()
    print("✅ Standby2 shutdown complete.")
