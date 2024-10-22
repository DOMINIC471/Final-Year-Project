# producer_humidity.py
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

# Send random humidity sensor data to Kafka topic
while True:
    humidity_value = round(random.uniform(40.0, 60.0), 2)  # Simulate humidity between 40% and 60%
    message = f"Sensor value: {humidity_value}"
    
    # Send message to the humidity-topic
    p.produce('humidity-topic', value=message, callback=delivery_report)
    p.flush()
    
    # Send data every 3 seconds
    time.sleep(3)
