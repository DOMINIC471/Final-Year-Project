from confluent_kafka import Producer
import pandas as pd
import time
import json
import psutil
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# -------------------------------------
# LOAD ENV VARS
# -------------------------------------
load_dotenv()

MESSAGES_PER_MINUTE = int(os.getenv("MESSAGES_PER_MINUTE", 20))
BROKER = os.getenv("KAFKA_BROKER", "localhost:29092")
ACTIVE_DB = os.getenv("ACTIVE_DB", "general").lower()
IS_TEST_MODE = os.getenv("IS_TEST_MODE", "0") == "1"
TEST_DURATION = 300 if IS_TEST_MODE else None

CSV_FILE = os.path.join("data", "extracted_hr_data.csv")
TOPIC = "heart_rate"

INTERVAL = 60 / MESSAGES_PER_MINUTE if MESSAGES_PER_MINUTE > 0 else 1
RATE_LABEL = f"{MESSAGES_PER_MINUTE}mpm"
RUN_SUFFIX = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

# -------------------------------------
# LOGGING SETUP (only for test mode)
# -------------------------------------
if IS_TEST_MODE:
    log_subdir = "test_results"
    db_dir = ACTIVE_DB
    log_folder = os.path.join(log_subdir, "per_message", db_dir)
    os.makedirs(log_folder, exist_ok=True)
    LOG_FILE = os.path.join(log_folder, f"producer_log_{RUN_SUFFIX}.csv")

    with open(LOG_FILE, "w") as f:
        f.write("timestamp,CPU%,Memory_MB\n")

    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)

    def log_usage():
        cpu = proc.cpu_percent(interval=None)
        mem = proc.memory_info().rss / (1024 * 1024)
        ts = datetime.now(timezone.utc).isoformat()
        with open(LOG_FILE, "a") as f:
            f.write(f"{ts},{cpu:.2f},{mem:.2f}\n")
else:
    log_usage = lambda: None  # no-op when not in test mode

# -------------------------------------
# LOAD DATA
# -------------------------------------
try:
    data = pd.read_csv(CSV_FILE)
    if data.empty:
        raise ValueError("CSV is empty.")
    print(f"📄 Loaded {len(data)} heart rate records.")
except Exception as e:
    print(f"❌ Failed to load CSV file: {e}")
    exit(1)

# -------------------------------------
# KAFKA SETUP
# -------------------------------------
print(f"🔌 Connecting to Kafka at {BROKER}...")
p = Producer({'bootstrap.servers': BROKER})

try:
    metadata = p.list_topics(timeout=5)
    if TOPIC not in metadata.topics:
        print(f"⚠️ Kafka topic '{TOPIC}' does not exist. Ensure it's created.")
except Exception as e:
    print(f"❌ Kafka connection failed: {e}")
    exit(1)

def delivery_report(err, msg):
    if err:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✅ Delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

# -------------------------------------
# MAIN PRODUCER LOOP
# -------------------------------------
def main():
    print(f"\n🚀 Kafka Producer Started at {MESSAGES_PER_MINUTE} mpm (~{INTERVAL:.2f}s interval)\n")

    start_time = time.time()
    index = 0
    total_rows = len(data)

    try:
        while True:
            if IS_TEST_MODE and (time.time() - start_time >= TEST_DURATION):
                print("\n🛑 Test duration complete. Exiting producer loop.")
                break

            row = data.iloc[index]
            timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
            message = {
                "bed_number": str(row["Bed Number"]),
                "timestamp": timestamp,
                "heart_rate": int(row["Heart Rate"])
            }

            try:
                p.produce(
                    TOPIC,
                    key=message["bed_number"],
                    value=json.dumps(message),
                    callback=delivery_report
                )
                log_usage()
            except Exception as e:
                print(f"❌ Kafka produce error: {e}")
                p.flush()

            p.poll(0)
            time.sleep(INTERVAL)
            index = (index + 1) % total_rows

    finally:
        try:
            flush_result = p.flush()
            print(f"\n✅ Kafka flush complete: {flush_result}")
        except Exception as e:
            print(f"⚠️ Error during final flush: {e}")

        if IS_TEST_MODE:
            print(f"✅ Producer shutdown complete. Resource logs saved to: {LOG_FILE}")
        else:
            print("✅ Producer shutdown complete.")

# -------------------------------------
# PROTECT ENTRYPOINT
# -------------------------------------
if __name__ == "__main__":
    main()
