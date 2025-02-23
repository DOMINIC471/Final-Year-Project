from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import json

# InfluxDB Standby Setup
bucket = "sensor_data"
org = "FYP"
token_standby = "NhNHBVzXz68MTGBqnPEcw2k12QEiBPFnDuwse3YgyjW5sMdXdqSev3evOBC7ET9hgYF6kOv62ryYsIlXNqIqmw=="
url_standby = "http://localhost:8087"  # Adjust for Standby InfluxDB instance

client_standby = InfluxDBClient(url=url_standby, token=token_standby, org=org)
write_api_standby = client_standby.write_api(write_options=SYNCHRONOUS)

# Kafka Consumer Setup
consumer_standby = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'standby-group',
    'auto.offset.reset': 'earliest'
})

# Subscribe to the Kafka topic
consumer_standby.subscribe(["heart_rate"])

# Main Consumer Loop
try:
    while True:
        msg = consumer_standby.poll(1.0)

        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue

        try:
            data = json.loads(msg.value().decode('utf-8'))
        except json.JSONDecodeError:
            print(f"Malformed message: {msg.value()}")
            continue

        # Extract the data fields
        bed_number = data.get("bed_number")
        timestamp = data.get("timestamp")
        heart_rate = data.get("heart_rate")

        if not timestamp or not heart_rate:
            print(f"Invalid data: {data}")
            continue

        print(f"Received data for Standby: Bed {bed_number}, Timestamp {timestamp}, Heart Rate {heart_rate}")

        # Write to InfluxDB Standby
        try:
            write_api_standby.write(bucket=bucket, org=org, record=Point("heart_rate")
                                    .tag("bed_number", bed_number)
                                    .field("heart_rate", heart_rate)
                                    .time(timestamp))
            print(f"Written to InfluxDB Standby: {bed_number}, {heart_rate}")
        except Exception as e:
            print(f"Failed to write to InfluxDB Standby: {e}")

except KeyboardInterrupt:
    print("\nStandby Consumer interrupted.")

finally:
    consumer_standby.close()
    print("Standby Consumer connection closed.")
