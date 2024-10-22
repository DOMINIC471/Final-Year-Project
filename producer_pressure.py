# producer_pressure.py
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

# Send random pressure sensor data to Kafka topic
while True:
    pressure_value = round(random.uniform(980.0, 1050.0), 2)  # Simulate pressure between 980hPa and 1050hPa
    message = f"Sensor value: {pressure_value}"
    
    # Send message to the pressure-topic
    p.produce('pressure-topic', value=message, callback=delivery_report)
    p.flush()
    
    # Send data every 4 seconds
    time.sleep(4)
