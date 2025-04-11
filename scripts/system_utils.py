import subprocess
import platform
import psutil
import datetime

# ----------------------------------------
# Record System State (CPU, Memory, Battery)
# ----------------------------------------
def record_system_conditions(filepath="system_conditions.txt"):
    try:
        with open(filepath, "w") as f:
            f.write(f"Timestamp: {datetime.datetime.utcnow().isoformat()} UTC\n")
            f.write(f"Platform: {platform.platform()}\n")
            f.write(f"CPU Cores: {psutil.cpu_count(logical=True)}\n")
            f.write(f"CPU Usage: {psutil.cpu_percent()}%\n")
            f.write(f"Memory: {psutil.virtual_memory().total / (1024 ** 3):.2f} GB\n")
            f.write(f"Memory Used: {psutil.virtual_memory().used / (1024 ** 3):.2f} GB\n")
            f.write(f"Memory Usage: {psutil.virtual_memory().percent}%\n")

            try:
                battery = psutil.sensors_battery()
                if battery:
                    f.write(f"Battery: {battery.percent}%\n")
                    f.write(f"Plugged in: {battery.power_plugged}\n")
            except Exception:
                pass

            # Add running user-facing apps
            f.write("\nRunning Applications (Top 15 by CPU):\n")
            proc = subprocess.Popen(
                "ps -axo comm,%cpu --sort=-%cpu | head -n 15",
                stdout=subprocess.PIPE,
                shell=True
            )
            output, _ = proc.communicate()
            f.write(output.decode("utf-8"))
    except Exception as e:
        print(f"❌ Failed to record system state: {e}")
