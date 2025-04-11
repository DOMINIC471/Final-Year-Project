import subprocess
import sys
import time
import csv
from datetime import datetime, timezone

# -----------------------------
# Config
# -----------------------------
DB = sys.argv[1] if len(sys.argv) > 1 else "victoriametrics"
RATE_LABEL = sys.argv[2] if len(sys.argv) > 2 else "100mpm"
INTERVAL = 5
DURATION = 300  # seconds
SAMPLES = DURATION // INTERVAL
TIMESTAMP_SUFFIX = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

CONTAINER_MAP = {
    "baseline": "baseline_sql",
    "timescaledb": "timescaledb",
    "influxdb": "influxdb-master",
    "victoriametrics": "victoria-metrics"
}

# -----------------------------
# Resolve Container
# -----------------------------
if DB not in CONTAINER_MAP:
    print(f"❌ Unknown DB: {DB}")
    sys.exit(1)

container = CONTAINER_MAP[DB]
log_dir = f"logs/global/{DB}"
output_file = f"{log_dir}/global_resource_log_{RATE_LABEL}_{DB}_{TIMESTAMP_SUFFIX}.csv"

subprocess.run(["mkdir", "-p", log_dir])

print(f"📡 Monitoring container-wide resource usage for '{container}'")
print(f"📁 Output: {output_file}")

with open(output_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Timestamp", "CPU%", "Memory_MB"])

    for _ in range(SAMPLES):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            # docker stats --no-stream gives one-shot metrics
            stats_output = subprocess.check_output(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}},{{.MemUsage}}", container],
                stderr=subprocess.DEVNULL
            ).decode().strip()

            cpu_perc, mem_usage = stats_output.split(",")
            cpu_perc = cpu_perc.replace('%', '').strip()

            # Parse memory usage (format: 12.34MiB / 1GiB)
            mem_mb = mem_usage.split('/')[0].strip()
            if "MiB" in mem_mb:
                mem_value = float(mem_mb.replace("MiB", "").strip())
            elif "GiB" in mem_mb:
                mem_value = float(mem_mb.replace("GiB", "").strip()) * 1024
            elif "KiB" in mem_mb:
                mem_value = float(mem_mb.replace("KiB", "").strip()) / 1024
            else:
                mem_value = 0

            writer.writerow([timestamp, cpu_perc, f"{mem_value:.2f}"])
        except Exception as e:
            writer.writerow([timestamp, "ERROR", "ERROR"])

        time.sleep(INTERVAL)

print(f"✅ Done: {output_file}")
