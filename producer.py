from confluent_kafka import Producer
import pandas as pd
import time
import json
import psutil
import os
from datetime import datetime, timezone

# -------------------------------------
# CONFIGURATION (environment-aware)
# -------------------------------------
messages_per_minute = int(os.getenv("MESSAGES_PER_MINUTE", 100))
active_db = os.getenv("ACTIVE_DB", "victoriametrics")
TEST_DURATION = 300  # seconds
csv_file = "Data/extracted_hr_data.csv"
TOPIC = "heart_rate"

# Derived settings
interval = 60 / messages_per_minute
rate_label = f"{messages_per_minute}mpm"
run_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

# -------------------------------------
# PER-MESSAGE LOGGING SETUP
# -------------------------------------
LOG_DIR = os.path.join("logs", "per_message", active_db)
os.makedirs(LOG_DIR, exist_ok=True)
per_msg_log_file = os.path.join(
    LOG_DIR,
    f"per_message_resource_log_{rate_label}_{active_db}_{run_suffix}.csv"
)

with open(per_msg_log_file, "w") as f:
    f.write("timestamp,CPU%,Memory_MB\n")

# -------------------------------------
# KAFKA CONFIG
# -------------------------------------
p = Producer({'bootstrap.servers': 'localhost:29092'})

# Kafka connection test
try:
    p.list_topics(timeout=5)
except Exception as e:
    print(f"❌ Kafka connection failed: {e}")
    exit(1)

def delivery_report(err, msg):
    if err:
        print(f"❌ Message delivery failed: {err}")
    else:
        print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")

# -------------------------------------
# SYSTEM MONITOR SETUP
# -------------------------------------
proc = psutil.Process(os.getpid())
proc.cpu_percent(interval=None)  # Prime CPU counter

def log_usage_on_send():
    cpu = proc.cpu_percent(interval=None)
    mem = proc.memory_info().rss / (1024 * 1024)
    ts = datetime.now(timezone.utc).isoformat()
    with open(per_msg_log_file, "a") as f:
        f.write(f"{ts},{cpu:.2f},{mem:.2f}\n")

# -------------------------------------
# LOAD DATA
# -------------------------------------
try:
    data = pd.read_csv(csv_file)
except Exception as e:
    print(f"❌ Error reading CSV file: {e}")
    exit(1)

print(f"📄 Total rows in dataset: {len(data)}")
print(data.head())

# -------------------------------------
# STREAMING
# -------------------------------------
print(f"\n🚀 Starting producer for {active_db} at {messages_per_minute} mpm (~{interval:.2f}s interval)")
print("📡 Streaming heart rate data...\n")

start_time = time.time()
data_index = 0
total_rows = len(data)

while True:
    elapsed = time.time() - start_time
    if elapsed >= TEST_DURATION:
        print("🛑 Test duration reached (5 minutes). Stopping producer.")
        break

    remaining = int(TEST_DURATION - elapsed)
    print(f"🕒 Remaining time: {remaining}s")

    row = data.iloc[data_index]
    sensor_data = {
        "bed_number": str(row["Bed Number"]),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        "heart_rate": int(row["Heart Rate"])
    }

    try:
        p.produce(
            TOPIC,
            key=sensor_data["bed_number"],
            value=json.dumps(sensor_data),
            callback=delivery_report
        )
        log_usage_on_send()
        print(f"📤 Produced: {sensor_data}")
    except Exception as e:
        print(f"❌ Kafka produce error: {e}")
        p.flush()

    p.poll(0)
    time.sleep(interval)

    # Reuse dataset if exhausted
    data_index = (data_index + 1) % total_rows

p.flush()
print("\n✅ All data sent or test duration completed.")
print(f"📁 Log saved to: {per_msg_log_file}")
