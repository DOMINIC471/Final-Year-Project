import os
import time
import subprocess
from scripts.system_utils import record_system_conditions

# -------------------------------------
# CONFIGURATION
# -------------------------------------
TEST_TIERS = [10, 20, 40, 60, 80, 100, 200, 500, 1000]
DATABASES = {
    "baseline": {
        "container": "baseline_sql",
        "process": "postgres"
    },
    "influxdb": {
        "container": "influxdb-master",
        "process": "influxd"
    },
    "timescaledb": {
        "container": "timescaledb",
        "process": "postgres"
    },
    "victoriametrics": {
        "container": "victoria-metrics",
        "process": "victoria-metrics"
    }
}
TEST_DURATION = 300
processes = []

# -------------------------------------
def stop_all_containers_except(active_container):
    for db_name, db_info in DATABASES.items():
        container = db_info["container"]
        if container != active_container:
            os.system(f"docker stop {container} > /dev/null 2>&1")

# -------------------------------------
def run_test_for_db_and_rate(db, rate):
    rate_label = f"{rate}mpm"
    print(f"\n🧪 Starting test: DB = {db}, Rate = {rate_label}")

    container_name = DATABASES[db]["container"]

    # Stop other containers
    stop_all_containers_except(container_name)

    # Clean up any old processes
    os.system("pkill -f consumerMaster.py")
    os.system("pkill -f producer.py")
    os.system("pkill -f monitor_resources.py")
    os.system("lsof -ti :8000 | xargs kill -9 2>/dev/null")

    # Start containers
    os.system("docker start zookeeper-1 kafka-1")
    os.system(f"docker start {container_name}")
    time.sleep(3)

    # Record system info to system_info/
    syslog_path = f"logs/system_info/system_conditions_{rate_label}_{db}.txt"
    os.makedirs(os.path.dirname(syslog_path), exist_ok=True)
    record_system_conditions(syslog_path)

    # Start global monitor
    print("📊 Launching monitor_resources.py...")
    monitor = subprocess.Popen(["python3", "monitor_resources.py", db, rate_label])
    processes.append(monitor)

    # Launch consumer
    print("🎧 Launching consumerMaster.py...")
    consumer_env = os.environ.copy()
    consumer_env["MESSAGES_PER_MINUTE"] = str(rate)
    consumer_env["ACTIVE_DB"] = db
    consumer = subprocess.Popen(["python3", "consumerMaster.py"], env=consumer_env)
    processes.append(consumer)
    time.sleep(2)

    # Launch producer (blocking)
    print("🚀 Launching producer.py...")
    producer_env = os.environ.copy()
    producer_env["MESSAGES_PER_MINUTE"] = str(rate)
    producer_env["ACTIVE_DB"] = db
    subprocess.run(["python3", "producer.py"], env=producer_env)

    print(f"⏳ Waiting for test duration ({TEST_DURATION}s)...")
    time.sleep(TEST_DURATION + 5)

# -------------------------------------
def cleanup_all_processes():
    print("\n🧼 Cleaning up background processes...")
    for p in processes:
        p.terminate()
    os.system("pkill -f consumerMaster.py")
    os.system("pkill -f producer.py")
    os.system("pkill -f monitor_resources.py")
    os.system("lsof -ti :8000 | xargs kill -9 2>/dev/null")
    print("✅ All test-related processes stopped.\n")

# -------------------------------------
def main():
    print("📦 RUNNING FULL AUTOMATED TEST SUITE FOR ALL DATABASES")
    try:
        for db in DATABASES:
            for rate in TEST_TIERS:
                run_test_for_db_and_rate(db, rate)
    except KeyboardInterrupt:
        print("\n🛑 KeyboardInterrupt detected!")
    finally:
        cleanup_all_processes()
        print("🧹 Final cleanup complete.")
        print("🏁 All benchmark tests finished.")

# -------------------------------------
if __name__ == "__main__":
    main()
