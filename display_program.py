import matplotlib
matplotlib.use('TkAgg')  # Fix for macOS compatibility

from influxdb_client import InfluxDBClient
import tkinter as tk
from tkinter import simpledialog
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
from datetime import datetime

# InfluxDB Configuration
bucket = "sensor_data"
org = "FYP"
token_master = "i1tGACkYPJkuTd1QHe8_PyAA9wspcTf2tVkpAmNEtqbv-GYmw09fg-QWETrGwvWAjnQuB8Rv99MLzWFxOSVTvQ=="
url_master = "http://localhost:8086"

token_standby = "6XwtzXyla097i-lDAAbbxhXxZbF5YPwsF3b_yv004kTO67uspjQ4HHkIyxXqVblMRg90abKcIgy2jGeS7YfhVw=="
url_standby = "http://localhost:8087"

# Initialize InfluxDB Clients
client_master = InfluxDBClient(url=url_master, token=token_master, org=org)
client_standby = InfluxDBClient(url=url_standby, token=token_standby, org=org)

query_api_master = client_master.query_api()
query_api_standby = client_standby.query_api()

# Deques to store timestamps and heart rates
timestamps = deque(maxlen=1000)  # Holds up to 1000 data points
heart_rates = deque(maxlen=1000)

# Global variables
selected_bed = ""

# Function to fetch data from InfluxDB with fallback
def fetch_influxdb_data(query, fallback=False):
    try:
        if not fallback:
            return query_api_master.query(query)
        else:
            return query_api_standby.query(query)
    except Exception as e:
        if not fallback:
            print(f"Master unavailable. Switching to Standby: {e}")
            return fetch_influxdb_data(query, fallback=True)
        else:
            print(f"Error querying both Master and Standby: {e}")
            return []

# Function to fetch historical data
def fetch_historical_data():
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "heart_rate")
      |> filter(fn: (r) => r["_field"] == "heart_rate")
      |> filter(fn: (r) => r["bed_number"] == "{selected_bed}")
      |> yield(name: "historical")
    '''
    results = fetch_influxdb_data(query)
    print("Historical query results:", results)  # Debugging output
    points = []
    for table in results:
        for record in table.records:
            print("Record values:", record.values)  # Debugging output
            points.append(record.values)
    return points

# Function to fetch real-time data
def fetch_real_time_data():
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -1m)
      |> filter(fn: (r) => r["_measurement"] == "heart_rate")
      |> filter(fn: (r) => r["_field"] == "heart_rate")
      |> filter(fn: (r) => r["bed_number"] == "{selected_bed}")
      |> yield(name: "real-time")
    '''
    results = fetch_influxdb_data(query)
    print("Real-time query results:", results)  # Debugging output
    points = []
    for table in results:
        for record in table.records:
            print("Record values:", record.values)  # Debugging output
            points.append(record.values)
    return points

# Function to fetch and append data to deques
def fetch_data():
    global timestamps, heart_rates
    try:
        points = fetch_real_time_data()
        for point in points:
            try:
                timestamp = point.get("_time")
                heart_rate_value = point.get("_value")

                if timestamp and heart_rate_value is not None:
                    if timestamp not in timestamps:
                        timestamps.append(timestamp)
                        heart_rates.append(heart_rate_value)
                else:
                    raise ValueError("Invalid data point: missing timestamp or heart rate value")
            except Exception as e:
                print(f"Error processing point: {e}")
        print(f"Fetched {len(heart_rates)} data points.")
    except Exception as e:
        print(f"Error fetching data: {e}")

# Function to initialize historical data
def initialize_historical_data():
    global timestamps, heart_rates
    try:
        points = fetch_historical_data()
        timestamps.clear()
        heart_rates.clear()
        for point in points:
            try:
                timestamp = point.get("_time")
                heart_rate_value = point.get("_value")

                if timestamp and heart_rate_value is not None:
                    timestamps.append(timestamp)  # `_time` is already a datetime object
                    heart_rates.append(heart_rate_value)  # `_value` is already numeric
                else:
                    raise ValueError("Invalid data point: missing timestamp or heart rate value")
            except Exception as e:
                print(f"Error processing historical point: {e}")
        print(f"Initialized with {len(heart_rates)} historical data points.")
    except Exception as e:
        print(f"Error initializing historical data: {e}")

# Function to update the graph
def update_graph(frame):
    fetch_data()
    ax.clear()
    if timestamps and heart_rates:
        ax.plot(timestamps, heart_rates, marker='o', linestyle='-', color='b')
        ax.set_title(f"Real-Time Heart Rate for Bed {selected_bed}")
        ax.set_xlabel("Time")
        ax.set_ylabel("Heart Rate (bpm)")
        plt.xticks(rotation=45)
        plt.tight_layout()
    else:
        ax.set_title(f"No data available for Bed {selected_bed}")

# Function to start the display program
def start_display():
    global selected_bed
    root = tk.Tk()
    root.withdraw()
    selected_bed = simpledialog.askstring("Input", "Enter Bed Number to Monitor:")

    if selected_bed:
        print(f"Monitoring Bed {selected_bed}")
        initialize_historical_data()

        # Plot the graph immediately
        update_graph(None)  # Pass None to mimic the FuncAnimation call

        # Start animation for updates
        ani = FuncAnimation(fig, update_graph, interval=60000, save_count=360)
        plt.show()
    else:
        print("No Bed Number entered. Exiting...")

# Matplotlib Setup
fig, ax = plt.subplots()

# Start the program
if __name__ == "__main__":
    print("Starting Display Program with Historical + Real-Time Data...")
    try:
        start_display()
    except KeyboardInterrupt:
        print("\nProgram interrupted.")
    finally:
        print("Program exited gracefully.")
