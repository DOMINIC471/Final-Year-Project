# producer_temperature.py
from confluent_kafka import Producer
import random
import time

# Kafka Producer configuration
p = Producer({
    'bootstrap.servers': 'localhost:9092'
})

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

# Send random temperature sensor data to Kafka topic
while True:
    temp_value = round(random.uniform(20.0, 30.0), 2)  # Simulate temperature between 20 and 30
    message = f"Sensor value: {temp_value}"
    
    # Send message to the temperature-topic
    p.produce('temperature-topic', value=message, callback=delivery_report)
    p.flush()
    
    # Send data every 2 seconds
    time.sleep(2)
