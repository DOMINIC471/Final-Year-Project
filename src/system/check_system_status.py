import subprocess
import requests
import time

# -----------------------------
# Basic Config
# -----------------------------
influx_ports = [8086, 8087, 8088]
victoria_ports = [8428, 8429, 8430]
timescale_containers = ["timescaledb", "timescaledb-standby1", "timescaledb-standby2"]
baseline_containers = ["baseline_sql", "baseline-standby1", "baseline-standby2"]
kafka_container = "kafka-1"
expected_kafka_topic = "heart_rate"

# -----------------------------
# Health Check Functions
# -----------------------------
def check_influxdb(port):
    try:
        res = requests.get(f"http://localhost:{port}/health", timeout=3)
        if res.status_code == 200 and res.json().get("status") == "pass":
            print(f"✅ InfluxDB on port {port} is healthy.")
        else:
            print(f"❌ InfluxDB on port {port} is NOT healthy.")
    except Exception as e:
        print(f"❌ InfluxDB on port {port} unreachable: {e}")

def check_victoriametrics(port):
    try:
        res = requests.get(f"http://localhost:{port}/health", timeout=3)
        if "OK" in res.text:
            print(f"✅ VictoriaMetrics on port {port} is healthy.")
        else:
            print(f"❌ VictoriaMetrics on port {port} failed.")
    except Exception as e:
        print(f"❌ VictoriaMetrics on port {port} unreachable: {e}")

def check_timescaledb(container):
    cmd = ["docker", "exec", "-i", container, "psql", "-U", "postgres", "-d", "sensor_data", "-c", "\\dt"]
    try:
        result = subprocess.check_output(cmd).decode()
        if "sensor_data" in result:
            print(f"✅ TimescaleDB ({container}): table 'sensor_data' exists.")
        else:
            print(f"⚠️ TimescaleDB ({container}): table 'sensor_data' MISSING.")
    except Exception as e:
        print(f"❌ TimescaleDB ({container}) unreachable: {e}")

def check_baseline(container):
    cmd = ["docker", "exec", "-i", container, "psql", "-U", "macbookpro", "-d", "baseline_sql", "-c", "\\dt"]
    try:
        result = subprocess.check_output(cmd).decode()
        if "heart_rate_data" in result:
            print(f"✅ Baseline ({container}): table 'heart_rate_data' exists.")
        else:
            print(f"⚠️ Baseline ({container}): table 'heart_rate_data' MISSING.")
    except Exception as e:
        print(f"❌ Baseline ({container}) unreachable: {e}")

def check_kafka_topic():
    cmd = ["docker", "exec", "-i", kafka_container, "kafka-topics", "--list", "--bootstrap-server", "localhost:29092"]
    try:
        result = subprocess.check_output(cmd).decode()
        if expected_kafka_topic in result:
            print(f"✅ Kafka: topic '{expected_kafka_topic}' exists.")
        else:
            print(f"❌ Kafka: topic '{expected_kafka_topic}' is MISSING.")
    except Exception as e:
        print(f"❌ Kafka unreachable: {e}")

def check_consumers():
    try:
        result = subprocess.check_output("ps aux | grep -i '[c]onsumer'", shell=True).decode()
        if result.strip():
            print("✅ Active consumer scripts detected:\n")
            print(result)
        else:
            print("⚠️ No active consumer scripts running.")
    except Exception as e:
        print(f"❌ Error checking consumer processes: {e}")

# -----------------------------
# Run All Checks
# -----------------------------
def run_all_checks():
    print("\n🩺 SYSTEM HEALTH CHECK STARTING...\n")

    for port in influx_ports:
        check_influxdb(port)

    for port in victoria_ports:
        check_victoriametrics(port)

    for container in timescale_containers:
        check_timescaledb(container)

    for container in baseline_containers:
        check_baseline(container)

    check_kafka_topic()
    check_consumers()

    print("\n✅ SYSTEM HEALTH CHECK COMPLETE.\n")

# -----------------------------
if __name__ == "__main__":
    run_all_checks()
