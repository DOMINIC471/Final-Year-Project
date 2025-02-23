from influxdb_client import InfluxDBClient

# Initialize client
client = InfluxDBClient(url="http://localhost:8086", token="MkgL8fi5idXV7ZGnIR6ua-8IxKnbcq6vT49v1hvD7S5Ee-fSphEUc5PxM5pkFnjH23eOLno6GDBoE5gfOJ2RUg==", org="FYP")

# Query API
query_api = client.query_api()

# Query data
query = f'from(bucket: "sensor_data") |> range(start: -1h)'
tables = query_api.query(query=query)

# Display results
for table in tables:
    for record in table.records:
        print(f'Time: {record.get_time()}, Value: {record.get_value()}')
