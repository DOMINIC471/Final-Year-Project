import os
import pandas as pd
import matplotlib.pyplot as plt

# Adjusted for correct repo structure
LOGS_DIR = os.path.join("test_results", "per_message")
OUT_DIR = os.path.join("summaries", "per_message")
os.makedirs(OUT_DIR, exist_ok=True)

summary_rows = []
TEST_DURATION = 300  # 5 minutes

def analyze_logs():
    for db in os.listdir(LOGS_DIR):
        db_path = os.path.join(LOGS_DIR, db)
        if not os.path.isdir(db_path):
            continue

        for file in os.listdir(db_path):
            if file.startswith("per_message_resource_log_") and file.endswith(".csv"):
                file_path = os.path.join(db_path, file)

                try:
                    df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
                    df["CPU%"] = pd.to_numeric(df["CPU%"], errors="coerce")
                    df["Memory_MB"] = pd.to_numeric(df["Memory_MB"], errors="coerce")
                    df.dropna(inplace=True)

                    if df.empty or len(df) < 2:
                        print(f"⚠️ Skipping short file: {file}")
                        continue

                    actual_count = len(df)
                    first_cpu = df.iloc[0]["CPU%"]
                    first_mem = df.iloc[0]["Memory_MB"]
                    df_trimmed = df.iloc[1:]  # Skip first reading

                    # Extract rate and DB name safely
                    parts = file.replace(".csv", "").split("_")
                    rate_label = next(p for p in parts if "mpm" in p)
                    rate = int(rate_label.replace("mpm", ""))
                    db_name = parts[-1]

                    expected_count = int((rate / 60) * TEST_DURATION)
                    gap = expected_count - actual_count

                    if actual_count < expected_count * 0.9:
                        print(f"⚠️ {file}: Low message count! Expected ~{expected_count}, got {actual_count} (gap={gap})")

                    summary_rows.append({
                        "DB": db_name,
                        "Rate": rate,
                        "First_CPU%": first_cpu,
                        "First_Mem_MB": first_mem,
                        "Avg_CPU%": df_trimmed["CPU%"].mean(),
                        "Max_CPU%": df_trimmed["CPU%"].max(),
                        "Avg_Mem_MB": df_trimmed["Memory_MB"].mean(),
                        "Max_Mem_MB": df_trimmed["Memory_MB"].max(),
                        "Messages_Logged": actual_count,
                        "Expected_Messages": expected_count,
                        "Gap": gap
                    })

                except Exception as e:
                    print(f"❌ Failed to process {file}: {e}")

    # Save summary CSV
    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(by=["DB", "Rate"])
    print("\n📊 Per-Message Resource Usage Summary:")
    print(summary_df.to_string(index=False))

    summary_path = os.path.join(OUT_DIR, "per_message_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"\n✅ Saved summary to: {summary_path}")

    # CPU plot
    plt.figure(figsize=(10, 6))
    for db in summary_df["DB"].unique():
        subset = summary_df[summary_df["DB"] == db]
        plt.plot(subset["Rate"], subset["Avg_CPU%"], marker="o", label=db)
    plt.title("Producer Avg CPU% (excluding first) vs MPM")
    plt.xlabel("Messages Per Minute")
    plt.ylabel("Average CPU Usage (%)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    cpu_plot_path = os.path.join(OUT_DIR, "producer_cpu_vs_mpm.png")
    plt.savefig(cpu_plot_path)
    print(f"📈 Saved plot: {cpu_plot_path}")
    plt.show()

    # Memory plot
    plt.figure(figsize=(10, 6))
    for db in summary_df["DB"].unique():
        subset = summary_df[summary_df["DB"] == db]
        plt.plot(subset["Rate"], subset["Avg_Mem_MB"], marker="o", label=db)
    plt.title("Producer Avg Memory MB (excluding first) vs MPM")
    plt.xlabel("Messages Per Minute")
    plt.ylabel("Average Memory (MB)")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    mem_plot_path = os.path.join(OUT_DIR, "producer_mem_vs_mpm.png")
    plt.savefig(mem_plot_path)
    print(f"📈 Saved plot: {mem_plot_path}")
    plt.show()


if __name__ == "__main__":
    analyze_logs()
