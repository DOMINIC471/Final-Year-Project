from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2
from datetime import datetime
import json

# InfluxDB Master Setup
bucket = "sensor_data"
org = "FYP"
token_master = "your_master_token"
url_master = "http://localhost:8086"

client_master = InfluxDBClient(url=url_master, token=token_master, org=org)
write_api_master = client_master.write_api(write_options=SYNCHRONOUS)

# TimescaleDB Master Setup
timescale_conn_master = psycopg2.connect(
    dbname="sensor_data",
    user="postgres",
    password="new_password",  # Replace with your TimescaleDB password
    host="localhost",
    port=5432
)
timescale_cursor_master = timescale_conn_master.cursor()

# Kafka Consumer Setup
consumer_master = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'master-group',
    'auto.offset.reset': 'earliest'
})

consumer_master.subscribe(["heart_rate"])

# Function to Write to TimescaleDB Master
def write_to_timescale_master(bed_number, timestamp, heart_rate):
    try:
        query = """
        INSERT INTO sensor_data (time, bed_number, heart_rate)
        VALUES (%s, %s, %s)
        """
        timescale_cursor_master.execute(query, (datetime.fromisoformat(timestamp), bed_number, heart_rate))
        timescale_conn_master.commit()
        print(f"Data written to TimescaleDB Master: {bed_number}, {timestamp}, {heart_rate}")
    except Exception as e:
        timescale_conn_master.rollback()
        print(f"Failed to write to TimescaleDB Master: {e}")

# Main Consumer Loop
try:
    while True:
        msg = consumer_master.poll(1.0)

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

        bed_number = data.get("bed_number")
        timestamp = data.get("timestamp")
        heart_rate = data.get("heart_rate")

        if not timestamp or not heart_rate:
            print(f"Invalid data: {data}")
            continue

        print(f"Received data for Master: Bed {bed_number}, Timestamp {timestamp}, Heart Rate {heart_rate}")

        # Write to InfluxDB Master
        try:
            write_api_master.write(bucket=bucket, org=org, record=Point("heart_rate")
                                   .tag("bed_number", bed_number)
                                   .field("heart_rate", heart_rate)
                                   .time(timestamp))
            print(f"Written to InfluxDB Master: {bed_number}, {heart_rate}")
        except Exception as e:
            print(f"Failed to write to InfluxDB Master: {e}")

        # Write to TimescaleDB Master
        write_to_timescale_master(bed_number, timestamp, heart_rate)

except KeyboardInterrupt:
    print("\nMaster Consumer interrupted.")

finally:
    consumer_master.close()
    timescale_cursor_master.close()
    timescale_conn_master.close()
    print("Master Consumer and TimescaleDB connection closed.")
