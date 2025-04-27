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

        # ✅ Safer filename parsing
        filename_base = os.path.splitext(file)[0]
        parts = filename_base.split("_")

        if len(parts) < 4 or parts[0] != "system" or parts[1] != "conditions":
            print(f"⚠️ Skipping invalid filename: {file}")
            continue

        rate_label = parts[2]
        db_name = parts[3]

        data = {
            "DB": db_name,
            "Rate": rate_label,
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
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            value = value.strip()

            if key.startswith("Timestamp"):
                data["Timestamp"] = value
            elif key.startswith("Platform"):
                data["Platform"] = value
            elif key.startswith("CPU Cores"):
                data["CPU_Cores"] = int(value)
            elif key.startswith("CPU Usage"):
                data["CPU_Usage_%"] = float(value.replace('%', ''))
            elif key.startswith("Memory:"):
                data["Memory_GB"] = float(value.replace("GB", ""))
            elif key.startswith("Memory Used"):
                data["Memory_Used_GB"] = float(value.replace("GB", ""))
            elif key.startswith("Memory Usage"):
                data["Memory_Usage_%"] = float(value.replace('%', ''))
            elif key.startswith("Battery"):
                data["Battery_%"] = int(value.replace('%', ''))
            elif key.startswith("Plugged in"):
                data["Plugged_In"] = value

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
