import os
import time
import subprocess
from dotenv import load_dotenv
from src.tests.system_utils import record_system_conditions

# -------------------------------------
# LOAD ENVIRONMENT VARIABLES
# -------------------------------------
load_dotenv()

# Runtime configuration from .env or default fallback
DEFAULT_TIERS = [10, 20, 40, 60, 80, 100, 200, 500, 1000]
MESSAGES_PER_MINUTE = int(os.getenv("MESSAGES_PER_MINUTE", 20))
TEST_TIERS = DEFAULT_TIERS
TEST_DURATION = int(os.getenv("TEST_DURATION", 300))

# Kafka configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:29092")

# Supported databases
DATABASES = {
    "baseline_sql": {"type": "baseline", "process": "postgres", "prom_port": 8000},
    "influxdb-master": {"type": "influxdb", "process": "influxd", "prom_port": 8000},
    "timescaledb": {"type": "timescaledb", "process": "postgres", "prom_port": 8000},
    "victoria-metrics": {"type": "victoriametrics", "process": "victoria-metrics", "prom_port": 8000},
}

processes = []

# -------------------------------------
def stop_all_containers_except(active_container):
    for container in DATABASES:
        if container != active_container:
            subprocess.run(["docker-compose", "stop", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# -------------------------------------
def kill_port(port):
    subprocess.run(f"lsof -ti :{port} | xargs kill -9", shell=True)

# -------------------------------------
def run_test_for_db_and_rate(active_container, rate):
    db_type = DATABASES[active_container]["type"]
    prom_port = DATABASES[active_container]["prom_port"]
    rate_label = f"{rate}mpm"
    print(f"\n🧪 Starting test: DB = {db_type}, Rate = {rate_label}")

    stop_all_containers_except(active_container)

    # Kill lingering processes + free Prometheus port
    for script in ["consumerMaster.py", "producer.py", "monitor_resources.py"]:
        subprocess.run(f"pkill -f {script}", shell=True)
    kill_port(prom_port)

    print("🐳 Starting containers: Zookeeper, Kafka, DB...")
    subprocess.run(["docker-compose", "start", "zookeeper-1", "kafka-1", active_container])
    time.sleep(5)

    syslog_path = f"test_results/system_info/system_conditions_{rate_label}_{db_type}.txt"
    os.makedirs(os.path.dirname(syslog_path), exist_ok=True)
    record_system_conditions(syslog_path)

    print("📊 Launching monitor_resources.py...")
    monitor = subprocess.Popen(["python3", "src/tests/monitor_resources.py", db_type, rate_label])
    processes.append(monitor)

    print("🎧 Launching consumerMaster.py...")
    consumer_env = os.environ.copy()
    consumer_env.update({
        "MESSAGES_PER_MINUTE": str(rate),
        "ACTIVE_DB": active_container,
        "IS_TEST_MODE": "1",
        "PROM_PORT": str(prom_port),
        "KAFKA_BROKER": KAFKA_BROKER
    })
    consumer = subprocess.Popen(["python3", "src/system/consumerMaster.py"], env=consumer_env)
    processes.append(consumer)

    time.sleep(2)

    print("🚀 Launching producer.py...")
    producer_env = os.environ.copy()
    producer_env.update({
        "MESSAGES_PER_MINUTE": str(rate),
        "ACTIVE_DB": db_type,
        "IS_TEST_MODE": "1",
        "KAFKA_BROKER": KAFKA_BROKER
    })
    subprocess.run(["python3", "src/system/producer.py"], env=producer_env)

    print(f"⏳ Waiting for test duration ({TEST_DURATION}s)...")
    time.sleep(TEST_DURATION + 5)

# -------------------------------------
def cleanup_all_processes():
    print("\n🧼 Cleaning up background processes...")
    for p in processes:
        p.terminate()

    for script in ["consumerMaster.py", "producer.py", "monitor_resources.py"]:
        subprocess.run(f"pkill -f {script}", shell=True)

    for db_info in DATABASES.values():
        kill_port(db_info["prom_port"])

    print("🛑 Stopping all Docker containers...")
    subprocess.run(["docker-compose", "stop"])

    print("✅ All test-related processes and containers stopped.\n")

# -------------------------------------
def main():
    print("📦 RUNNING FULL AUTOMATED TEST SUITE FOR ALL DATABASES")
    try:
        for container in DATABASES:
            for rate in TEST_TIERS:
                run_test_for_db_and_rate(container, rate)
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted manually.")
    finally:
        cleanup_all_processes()
        print("🧹 Final cleanup complete.")
        print("🏁 All benchmark tests finished.")

# -------------------------------------
if __name__ == "__main__":
    main()
