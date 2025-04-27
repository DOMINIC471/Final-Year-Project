import subprocess
import sys
import time
import csv
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# -----------------------------
# Load Environment
# -----------------------------
load_dotenv()

# -----------------------------
# CLI Args
# -----------------------------
DB = sys.argv[1] if len(sys.argv) > 1 else "victoriametrics"
RATE_LABEL = sys.argv[2] if len(sys.argv) > 2 else "100mpm"

# -----------------------------
# Runtime Config
# -----------------------------
INTERVAL = 5
DURATION = int(os.getenv("TEST_DURATION", 300))  # seconds
SAMPLES = DURATION // INTERVAL
IS_TEST_MODE = os.getenv("IS_TEST_MODE", "0") == "1"
TIMESTAMP_SUFFIX = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

# -----------------------------
# Map DB Type → Container Name
# -----------------------------
CONTAINER_MAP = {
    "baseline": "baseline_sql",
    "timescaledb": "timescaledb",
    "influxdb": "influxdb-master",
    "victoriametrics": "victoria-metrics"
}

if DB not in CONTAINER_MAP:
    print(f"❌ Unknown DB: {DB}")
    sys.exit(1)

container = CONTAINER_MAP[DB]
base_dir = "test_results/global" if IS_TEST_MODE else "logs/global"
log_dir = os.path.join(base_dir, DB)
os.makedirs(log_dir, exist_ok=True)
output_file = os.path.join(log_dir, f"global_resource_log_{RATE_LABEL}_{DB}_{TIMESTAMP_SUFFIX}.csv")

print(f"📡 Monitoring container: {container}")
print(f"🧪 Test mode: {'✅' if IS_TEST_MODE else '❌'}")
print(f"📁 Logging to: {output_file}")

# -----------------------------
# Start Monitoring Loop
# -----------------------------
with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Timestamp", "CPU%", "Memory_MB"])

    for _ in range(SAMPLES):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            stats_output = subprocess.check_output(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}},{{.MemUsage}}", container],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            cpu_raw, mem_raw = stats_output.split(",")
            cpu_perc = cpu_raw.replace('%', '').strip()

            mem_value_str = mem_raw.split('/')[0].strip()
            mem_mb = 0.0

            if "MiB" in mem_value_str:
                mem_mb = float(mem_value_str.replace("MiB", "").strip())
            elif "GiB" in mem_value_str:
                mem_mb = float(mem_value_str.replace("GiB", "").strip()) * 1024
            elif "KiB" in mem_value_str:
                mem_mb = float(mem_value_str.replace("KiB", "").strip()) / 1024
            else:
                raise ValueError(f"Unknown memory format: {mem_value_str}")

            writer.writerow([timestamp, cpu_perc, f"{mem_mb:.2f}"])
            f.flush()

        except Exception as e:
            writer.writerow([timestamp, "ERROR", "ERROR"])
            f.flush()
            print(f"⚠️ Error capturing stats: {e}")

        time.sleep(INTERVAL)

print(f"✅ Monitoring complete. Output saved to: {output_file}")
