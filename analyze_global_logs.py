import os
import pandas as pd
import matplotlib.pyplot as plt

# Set path to global logs folder
LOGS_DIR = os.path.join("logs", "global")
OUT_DIR = os.path.join("summaries", "global")
os.makedirs(OUT_DIR, exist_ok=True)

SUMMARY_ROWS = []

# Loop through each DB folder
for db in os.listdir(LOGS_DIR):
    db_path = os.path.join(LOGS_DIR, db)
    if not os.path.isdir(db_path):
        continue

    for file in os.listdir(db_path):
        if file.startswith("global_resource_log_") and file.endswith(".csv"):
            full_path = os.path.join(db_path, file)

            try:
                df = pd.read_csv(full_path)
                df = df[(df["CPU%"] != "ERROR") & (df["Memory_MB"] != "ERROR")]
                df["CPU%"] = pd.to_numeric(df["CPU%"], errors="coerce")
                df["Memory_MB"] = pd.to_numeric(df["Memory_MB"], errors="coerce")
                df.dropna(inplace=True)

                # ✅ SAFER FILENAME PARSING HERE
                filename_base = file.replace(".csv", "")
                parts = filename_base.split("_")
                rate_label = parts[-3]
                rate = int(rate_label.replace("mpm", ""))
                db_name = parts[-2]

                SUMMARY_ROWS.append({
                    "DB": db_name,
                    "Rate": rate,
                    "Avg_CPU%": df["CPU%"].mean(),
                    "Max_CPU%": df["CPU%"].max(),
                    "Avg_Mem_MB": df["Memory_MB"].mean(),
                    "Max_Mem_MB": df["Memory_MB"].max()
                })
            except Exception as e:
                print(f"❌ Failed to process {file}: {e}")

# Create summary DataFrame
summary_df = pd.DataFrame(SUMMARY_ROWS)
summary_df = summary_df.sort_values(by=["DB", "Rate"])
print("\n📊 Global Resource Usage Summary:")
print(summary_df.to_string(index=False))

# Save summary CSV
summary_csv_path = os.path.join(OUT_DIR, "global_summary.csv")
summary_df.to_csv(summary_csv_path, index=False)
print(f"\n✅ Saved summary to {summary_csv_path}")

# Plot: CPU% vs MPM
plt.figure(figsize=(10, 6))
for db in summary_df["DB"].unique():
    subset = summary_df[summary_df["DB"] == db]
    plt.plot(subset["Rate"], subset["Avg_CPU%"], marker="o", label=db)
plt.title("Average CPU% vs Messages Per Minute")
plt.xlabel("Messages Per Minute (MPM)")
plt.ylabel("Average CPU Usage (%)")
plt.grid(True)
plt.legend()
plt.tight_layout()
cpu_plot_path = os.path.join(OUT_DIR, "cpu_vs_mpm.png")
plt.savefig(cpu_plot_path)
print(f"📈 Saved plot: {cpu_plot_path}")
plt.show()

# Plot: Memory vs MPM
plt.figure(figsize=(10, 6))
for db in summary_df["DB"].unique():
    subset = summary_df[summary_df["DB"] == db]
    plt.plot(subset["Rate"], subset["Avg_Mem_MB"], marker="o", label=db)
plt.title("Average Memory Usage vs Messages Per Minute")
plt.xlabel("Messages Per Minute (MPM)")
plt.ylabel("Average Memory (MB)")
plt.grid(True)
plt.legend()
plt.tight_layout()
mem_plot_path = os.path.join(OUT_DIR, "memory_vs_mpm.png")
plt.savefig(mem_plot_path)
print(f"📈 Saved plot: {mem_plot_path}")
plt.show()
