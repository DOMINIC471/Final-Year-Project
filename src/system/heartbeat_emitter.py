import os
import time
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from confluent_kafka import Producer

# -------------------------------------
# ENVIRONMENT SETUP
# -------------------------------------
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:29092")
TOPIC = "heartbeat"
CONSUMER_ID = os.getenv("CONSUMER_ID", sys.argv[1] if len(sys.argv) > 1 else "master")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 2))  # Default to every 2 seconds

# Heartbeat file path
heartbeat_file = Path(f"/tmp/heartbeat_{CONSUMER_ID}_alive")

# -------------------------------------
# KAFKA PRODUCER
# -------------------------------------
producer = Producer({
    "bootstrap.servers": KAFKA_BROKER
})

def delivery_report(err, msg):
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✅ [Heartbeat] {CONSUMER_ID} @ {datetime.now(timezone.utc).isoformat()} (offset {msg.offset()})")

print(f"🫀 Heartbeat emitter started for {CONSUMER_ID} (every {HEARTBEAT_INTERVAL}s)...")

try:
    while True:
        now = datetime.now(timezone.utc)

        heartbeat = {
            "consumer_id": CONSUMER_ID,
            "timestamp": now.isoformat()
        }

        try:
            producer.produce(TOPIC, json.dumps(heartbeat).encode("utf-8"), callback=delivery_report)
            producer.poll(0)
        except Exception as e:
            print(f"❌ Failed to emit heartbeat: {e}")

        # 🔧 File touch for liveness tracking
        heartbeat_file.touch()

        time.sleep(HEARTBEAT_INTERVAL)

except KeyboardInterrupt:
    print("\n🛑 Heartbeat emitter interrupted. Shutting down...")

finally:
    producer.flush()
    print("✅ Heartbeat emitter closed cleanly.")
