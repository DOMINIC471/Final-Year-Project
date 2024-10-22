from confluent_kafka import Producer
import random
import time

def delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

p = Producer({'bootstrap.servers': 'localhost:9092'})

# Simulate sending messages from different services
for i in range(10):  # Producing 10 messages
    service_name = f'service-{i}'
    sensor_value = round(random.uniform(20.0, 30.0), 2)  # Simulate random sensor values between 20 and 30
    message_value = f'Message from {service_name}, Sensor value: {sensor_value}'

    p.produce('test-topic', key=service_name, value=message_value, callback=delivery_report)
    p.flush()
    time.sleep(1)  # Simulate delay between messages

# Wait for any outstanding messages to be delivered and delivery reports received
p.flush()
