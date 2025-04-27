import subprocess
import platform
import psutil
from datetime import datetime

# ----------------------------------------
# Record System State: CPU, Memory, Battery, Top Processes
# ----------------------------------------
def record_system_conditions(filepath="system_conditions.txt"):
    try:
        with open(filepath, "w") as f:
            f.write(f"Timestamp: {datetime.utcnow().isoformat()} UTC\n")
            f.write(f"Platform: {platform.platform()}\n")
            f.write(f"CPU Cores: {psutil.cpu_count(logical=True)}\n")
            f.write(f"CPU Usage: {psutil.cpu_percent(interval=1):.2f}%\n")

            vm = psutil.virtual_memory()
            f.write(f"Memory: {vm.total / (1024 ** 3):.2f} GB\n")
            f.write(f"Memory Used: {vm.used / (1024 ** 3):.2f} GB\n")
            f.write(f"Memory Usage: {vm.percent:.2f}%\n")

            try:
                battery = psutil.sensors_battery()
                if battery:
                    f.write(f"Battery: {battery.percent}%\n")
                    f.write(f"Plugged in: {battery.power_plugged}\n")
            except Exception:
                f.write("Battery: N/A\n")

            f.write("\nTop 15 Running Applications by CPU:\n")
            result = subprocess.run(
                ["ps", "-axo", "comm,%cpu", "--sort=-%cpu"],
                capture_output=True,
                text=True
            )
            top_lines = result.stdout.strip().split("\n")[:16]  # header + top 15
            f.write("\n".join(top_lines))

    except Exception as e:
        print(f"❌ Failed to record system state: {e}")
