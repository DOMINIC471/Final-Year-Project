import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# Corrected paths
LOGS_DIR = os.path.join("test_results", "writes")
OUT_DIR = os.path.join("summaries", "writes")
os.makedirs(OUT_DIR, exist_ok=True)

summary_rows = []

def parse_timestamp(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def analyze_write_logs():
    for db in os.listdir(LOGS_DIR):
        db_path = os.path.join(LOGS_DIR, db)
        if not os.path.isdir(db_path):
            continue

        for file in os.listdir(db_path):
            if file.startswith("write_times_") and file.endswith(".log"):
                path = os.path.join(db_path, file)

                try:
                    with open(path, "r") as f:
                        lines = [line.strip() for line in f if "," in line]

                    timestamps = [parse_timestamp(line.split(",")[0]) for line in lines]
                    timestamps = [t for t in timestamps if t is not None]

                    if len(timestamps) < 2:
                        print(f"⚠️ Skipping too few writes in {file}")
                        continue

                    timestamps.sort()
                    duration = (timestamps[-1] - timestamps[0]).total_seconds()
                    writes = len(timestamps)
                    writes_per_sec = writes / duration if duration > 0 else 0

                    parts = file.replace(".log", "").split("_")
                    rate = int(next(p for p in parts if "mpm" in p).replace("mpm", ""))
                    db_name = parts[-1]

                    deltas = [(timestamps[i+1] - timestamps[i]).total_seconds() * 1000 for i in range(len(timestamps) - 1)]
                    avg_latency_ms = sum(deltas) / len(deltas)

                    summary_rows.append({
                        "DB": db_name,
                        "Rate": rate,
                        "Messages_Written": writes,
                        "Duration_s": duration,
                        "Writes_per_sec": writes_per_sec,
                        "Avg_Latency_ms": avg_latency_ms
                    })

                except Exception as e:
                    print(f"❌ Failed to process {file}: {e}")

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(by=["DB", "Rate"])
    print("\n🧾 Write Performance Summary:")
    print(summary_df.to_string(index=False))

    summary_csv = os.path.join(OUT_DIR, "write_summary.csv")
    summary_df.to_csv(summary_csv, index=False)
    print(f"\n✅ Saved summary to {summary_csv}")

    # Plot: Writes/sec vs MPM
    plt.figure(figsize=(10, 6))
    for db in summary_df["DB"].unique():
        subset = summary_df[summary_df["DB"] == db]
        plt.plot(subset["Rate"], subset["Writes_per_sec"], marker="o", label=db)
    plt.title("Write Throughput (writes/sec) vs MPM")
    plt.xlabel("Messages Per Minute")
    plt.ylabel("Writes per Second")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plot_path = os.path.join(OUT_DIR, "writes_per_sec_vs_mpm.png")
    plt.savefig(plot_path)
    print(f"📈 Saved plot: {plot_path}")
    plt.show()

    # Plot: Latency vs MPM
    plt.figure(figsize=(10, 6))
    for db in summary_df["DB"].unique():
        subset = summary_df[summary_df["DB"] == db]
        plt.plot(subset["Rate"], subset["Avg_Latency_ms"], marker="o", label=db)
    plt.title("Avg Write Latency (ms) vs MPM")
    plt.xlabel("Messages Per Minute")
    plt.ylabel("Average Latency (ms)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    latency_plot_path = os.path.join(OUT_DIR, "write_latency_vs_mpm.png")
    plt.savefig(latency_plot_path)
    print(f"📈 Saved plot: {latency_plot_path}")
    plt.show()

if __name__ == "__main__":
    analyze_write_logs()
