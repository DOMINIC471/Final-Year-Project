from confluent_kafka import Producer
import pandas as pd
import time
import json
from datetime import datetime  # ✅ Added for precise timestamp

# Delivery report callback
def delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result."""
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

# Kafka Producer configuration
p = Producer({'bootstrap.servers': 'localhost:29092'})

# Path to the cleaned CSV file
csv_file = "Data/extracted_hr_data.csv"  # Replace with the correct path

# Load the cleaned CSV file
try:
    data = pd.read_csv(csv_file)
except Exception as e:
    print(f"Error reading CSV file: {e}")
    exit(1)

# Debug: Print row count and sample data
print(f"Total rows in dataset: {len(data)}")
print(data.head())

# Kafka Topic
TOPIC = "heart_rate"

# Batch size and interval
batch_size = 10  # Number of records per batch
interval = 60  # Delay in seconds between batches

# Start producing
print("Starting Producer...")
for i in range(0, len(data), batch_size):
    batch = data.iloc[i:i + batch_size]
    print(f"Processing batch {i // batch_size + 1}, Rows: {len(batch)}")

    # Process each record in the batch
    for _, row in batch.iterrows():
        # Prepare the message and ensure proper conversion to native types
        sensor_data = {
            "bed_number": str(row["Bed Number"]),  # Convert to string
            "timestamp": datetime.now().isoformat(timespec='milliseconds'),  # ✅ High-precision timestamp
            "heart_rate": int(row["Heart Rate"])  # Convert to native int
        }

        # Produce data to Kafka
        try:
            p.produce(TOPIC, key=sensor_data["bed_number"], value=json.dumps(sensor_data), callback=delivery_report)
            print(f"Produced: {sensor_data}")
        except Exception as e:
            print(f"Error producing message: {e}")

    # Flush after each batch to ensure all messages are delivered
    p.flush()
    print(f"Batch {i // batch_size + 1} sent. Waiting for {interval} seconds...")

    # Wait before sending the next batch unless it's the last one
    if i + batch_size < len(data):
        time.sleep(interval)

print("All data sent!")
