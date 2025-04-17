import os
import pandas as pd

# -------------------------------
# CONFIGURATION
# -------------------------------
SYSINFO_DIR = os.path.join("logs", "system_info")
OUT_DIR = os.path.join("summaries", "system_info")
os.makedirs(OUT_DIR, exist_ok=True)

summary_rows = []

# -------------------------------
# PARSE EACH FILE
# -------------------------------
for file in os.listdir(SYSINFO_DIR):
    if not file.endswith(".txt"):
        continue

    file_path = os.path.join(SYSINFO_DIR, file)
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()

        # Extract DB and rate from filename
        parts = file.replace(".txt", "").split("_")
        rate = parts[2]
        db_name = parts[3]

        data = {
            "DB": db_name,
            "Rate": rate,
            "Timestamp": "",
            "Platform": "",
            "CPU_Cores": None,
            "CPU_Usage_%": None,
            "Memory_GB": None,
            "Memory_Used_GB": None,
            "Memory_Usage_%": None,
            "Battery_%": None,
            "Plugged_In": ""
        }

        for line in lines:
            if line.startswith("Timestamp:"):
                data["Timestamp"] = line.split(":", 1)[1].strip()
            elif line.startswith("Platform:"):
                data["Platform"] = line.split(":", 1)[1].strip()
            elif line.startswith("CPU Cores:"):
                data["CPU_Cores"] = int(line.split(":")[1].strip())
            elif line.startswith("CPU Usage:"):
                data["CPU_Usage_%"] = float(line.split(":")[1].strip().replace('%', ''))
            elif line.startswith("Memory:"):
                data["Memory_GB"] = float(line.split(":")[1].strip().replace('GB', ''))
            elif line.startswith("Memory Used:"):
                data["Memory_Used_GB"] = float(line.split(":")[1].strip().replace('GB', ''))
            elif line.startswith("Memory Usage:"):
                data["Memory_Usage_%"] = float(line.split(":")[1].strip().replace('%', ''))
            elif line.startswith("Battery:"):
                data["Battery_%"] = int(line.split(":")[1].strip().replace('%', ''))
            elif line.startswith("Plugged in:"):
                data["Plugged_In"] = line.split(":")[1].strip()

        summary_rows.append(data)

    except Exception as e:
        print(f"❌ Failed to parse {file}: {e}")

# -------------------------------
# EXPORT SUMMARY
# -------------------------------
summary_df = pd.DataFrame(summary_rows)
summary_df = summary_df.sort_values(by=["DB", "Rate"])
out_path = os.path.join(OUT_DIR, "system_info_summary.csv")
summary_df.to_csv(out_path, index=False)

print("📊 System Info Summary:")
print(summary_df.to_string(index=False))
print(f"\n✅ Saved to: {out_path}")
