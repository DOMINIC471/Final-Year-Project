from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS

# Initialize client
client = InfluxDBClient(url="http://localhost:8086", token="MkgL8fi5idXV7ZGnIR6ua-8IxKnbcq6vT49v1hvD7S5Ee-fSphEUc5PxM5pkFnjH23eOLno6GDBoE5gfOJ2RUg==", org="FYP")

# Write API
write_api = client.write_api(write_options=SYNCHRONOUS)

# Create data point
point = Point("sensor_data").tag("location", "lab").field("temperature", 25.3)

# Write data to sensor_data bucket
write_api.write(bucket="sensor_data", org="FYP", record=point)

print("Data written successfully.")
