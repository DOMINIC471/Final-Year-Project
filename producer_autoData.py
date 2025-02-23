from confluent_kafka import Producer
import random
import time
import json

def delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result."""
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

# Kafka Producer configuration
p = Producer({'bootstrap.servers': 'localhost:9092'})

# Define sensors and their value ranges
sensors = {
    "temperature": (20, 30),
    "humidity": (30, 60),
    "pressure": (900, 1100),
    "light": (100, 1000),
    "co2": (300, 500),
    "noise": (40, 80),
    "motion": (0, 1),  # Binary: 0 or 1
    "air_quality": (0, 500),
    "heart_rate": (60, 100),
    "oxygen_saturation": (90, 100)
}

while True:
    for sensor, value_range in sensors.items():
        # Generate current timestamp
        current_time = time.time()

        # Create sensor data
        sensor_data = {
            "sensor_id": f"{sensor}_sensor",
            "timestamp": round(current_time, 3),  # Keep timestamp precision for processing time accuracy
            "value": round(random.uniform(*value_range), 2)
        }

        # Log sensor data for debugging
        print(f"Generated data: {sensor_data}")

        # Define topic dynamically based on sensor type
        topic = f"{sensor}-topic"

        # Produce data to Kafka topic
        try:
            p.produce(topic, key=sensor_data["sensor_id"], value=json.dumps(sensor_data), callback=delivery_report)
        except Exception as e:
            print(f"Error producing message to {topic}: {e}")

    # Ensure all messages are sent before the next batch
    p.flush()

    # Simulate a delay between message batches
    time.sleep(1)
