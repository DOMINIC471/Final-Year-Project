import os
import subprocess
import time
import signal
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# -----------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------
load_dotenv()

MESSAGES_PER_MINUTE = int(os.getenv("MESSAGES_PER_MINUTE", 20))
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:29092")
IS_TEST_MODE = os.getenv("IS_TEST_MODE", "0") == "1"
CSV_FILE = os.getenv("CSV_FILE", "data/extracted_hr_data.csv")

# -----------------------------
# CONSUMER ROLES & PROM PORTS
# -----------------------------
CONSUMER_ROLES = ["master", "standby1", "standby2"]
PROMETHEUS_PORTS = {
    "master": 8000,
    "standby1": 8010,
    "standby2": 8020
}

# -----------------------------
# CLEANUP EXISTING PROCESSES
# -----------------------------
def kill_existing(script_name):
    try:
        output = subprocess.check_output(["pgrep", "-f", script_name]).decode().strip().split('\n')
        for pid in output:
            if pid.isdigit():
                print(f"🔪 Killing previous {script_name} PID {pid}")
                os.kill(int(pid), signal.SIGTERM)
    except subprocess.CalledProcessError:
        pass  # No such process

print("\n🧹 Cleaning up old consumer/producer processes...")
for script in [
    "consumerMaster.py", "consumerStandby1.py", "consumerStandby2.py",
    "heartbeat_emitter.py", "heartbeat_listener.py", "producer.py"
]:
    kill_existing(script)

time.sleep(2)

# -----------------------------
# START DOCKER SERVICES
# -----------------------------
print("\n🚀 Ensuring Kafka & DB containers are running...")
subprocess.run(["docker-compose", "up", "-d"], check=True)
time.sleep(5)

# -----------------------------
# START PRODUCER
# -----------------------------
print("\n📤 Launching producer.py...")
producer_env = os.environ.copy()
producer_env.update({
    "MESSAGES_PER_MINUTE": str(MESSAGES_PER_MINUTE),
    "KAFKA_BROKER": KAFKA_BROKER,
    "ACTIVE_DB": "general",
    "IS_TEST_MODE": "1" if IS_TEST_MODE else "0"
})
producer_process = subprocess.Popen(["python3", "src/system/producer.py"], env=producer_env)
time.sleep(3)

# -----------------------------
# START CONSUMERS (in order: master -> standby1 -> standby2)
# -----------------------------
print("\n🎧 Starting consumer processes...")
consumer_processes = []

for role in CONSUMER_ROLES:
    prom_port = PROMETHEUS_PORTS[role]
    env = os.environ.copy()
    env.update({
        "MESSAGES_PER_MINUTE": str(MESSAGES_PER_MINUTE),
        "ACTIVE_DB": "influxdb",
        "CONSUMER_ROLE": role,
        "CONSUMER_ID": role,
        "KAFKA_BROKER": KAFKA_BROKER,
        "IS_TEST_MODE": "1" if IS_TEST_MODE else "0",
        "PROM_PORT": str(prom_port)
    })

    script = "src/system/consumerMaster.py" if role == "master" else f"src/system/consumerStandby{role[-1]}.py"
    print(f"   ➤ Launching {script} as {role}...")
    process = subprocess.Popen(["python3", script], env=env)
    consumer_processes.append(process)
    time.sleep(2)  # Small delay between launches

# -----------------------------
# DISPLAY PROGRAM PLACEHOLDER
# -----------------------------
print("\n📊 Launching Display Program...")
subprocess.Popen(["python3", "hr_monitor/manage.py", "runserver"])

# -----------------------------
# SHUTDOWN HANDLER
# -----------------------------
print("\n🔚 Press Ctrl+C to terminate all components...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Shutting down subprocesses...")

    # Terminate all consumers and producer
    for p in consumer_processes:
        p.terminate()
    producer_process.terminate()

    # Clean up leftover lock/alive files
    print("🧹 Cleaning up heartbeat/lock files...")
    tmp_dir = Path("/tmp")
    for filename in ["heartbeat_master_alive", "heartbeat_standby1_alive", "heartbeat_standby2_alive", "icu_promotion.lock"]:
        filepath = tmp_dir / filename
        if filepath.exists():
            print(f"   ➤ Deleting {filepath}")
            filepath.unlink()

    print("✅ All subprocesses terminated and environment cleaned up.")
