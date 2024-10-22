from confluent_kafka import Consumer, Producer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
import pytz
import time

# InfluxDB setup
bucket = "sensor_data"
org = "FYP"
token = "MkgL8fi5idXV7ZGnIR6ua-8IxKnbcq6vT49v1hvD7S5Ee-fSphEUc5PxM5pkFnjH23eOLno6GDBoE5gfOJ2RUg=="  
token_standby = "eYWtsn2BR84E2Iv5gy6FJ6phpQZWQ57I3z9EAnv16nAzdJwd-psplEgYa5kx6rjyEwX838xuuF-FFkUDzdZwrA=="
url_master = "http://localhost:8086"
url_standby = "http://localhost:8087"

# Connect to InfluxDB (Master and Standby)
client_master = InfluxDBClient(url=url_master, token=token, org=org)
client_standby = InfluxDBClient(url=url_standby, token=token_standby, org=org)

write_api_master = client_master.write_api(write_options=SYNCHRONOUS)
write_api_standby = client_standby.write_api(write_options=SYNCHRONOUS)

# Kafka Consumer setup
consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'mygroup',
    'auto.offset.reset': 'earliest'
})

consumer.subscribe(['test-topic', 'temperature-topic', 'humidity-topic', 'pressure-topic'])

# Kafka Producer setup (to send heartbeats)
producer = Producer({
    'bootstrap.servers': 'localhost:9092'
})

# Heartbeat function to send status to Kafka
def send_heartbeat():
    status_message = f"Consumer is alive at {datetime.now()}"
    producer.produce('status-topic', value=status_message)
    producer.flush()
    print(f"Heartbeat sent: {status_message}")

try:
    last_heartbeat_time = time.time()
    heartbeat_interval = 5  # Send heartbeat every 5 seconds

    while True:
        msg = consumer.poll(1.0)

        # Send a heartbeat if the interval has passed
        current_time = time.time()
        if current_time - last_heartbeat_time >= heartbeat_interval:
            send_heartbeat()
            last_heartbeat_time = current_time

        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        # Check if the key is not None before decoding
        if msg.key() is not None:
            service_name = msg.key().decode('utf-8')
        else:
            service_name = "No Key"  # Handle cases where there is no key
        
        message_value = msg.value().decode('utf-8')
        
        print(f"Received message from {service_name}: {message_value}")

        # Check if the message contains a valid float sensor value
        try:
            # Assuming the message format is "Sensor value: XX.XX"
            if "Sensor value:" in message_value:
                sensor_value = float(message_value.split(":")[-1].strip())

                # Create a point to write to InfluxDB
                point = Point("sensor_data") \
                  .tag("source", service_name) \
                  .field("value", sensor_value) \
                  .time(datetime.now(pytz.timezone('Europe/London')))

                # Write the data to both InfluxDB instances (Master and Standby)
                write_api_master.write(bucket=bucket, org=org, record=point)
                print("Data written to Master InfluxDB")
                
                write_api_standby.write(bucket=bucket, org=org, record=point)
                print("Data written to Standby InfluxDB")
            else:
                print(f"Message does not contain sensor data: {message_value}")
        except ValueError as e:
            print(f"Failed to process message: {message_value}, error: {e}")

except KeyboardInterrupt:
    pass

finally:
    # Close down consumer to commit final offsets.
    consumer.close()
