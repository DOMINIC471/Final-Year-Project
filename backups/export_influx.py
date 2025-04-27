from influxdb_client import InfluxDBClient
import csv
from datetime import datetime

# Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_ORG = "FYP"
INFLUX_BUCKET = "sensor_data"
INFLUX_TOKEN = "i1tGACkYPJkuTd1QHe8_PyAA9wspcTf2tVkpAmNEtqbv-GYmw09fg-QWETrGwvWAjnQuB8Rv99MLzWFxOSVTvQ=="

# Set time range for export
TIME_RANGE = "-30d"  # Options: -1h, -7d, -1y, or use exact range if needed

# Connect to InfluxDB
client = InfluxDBClient(
    url=INFLUX_URL,
    token=INFLUX_TOKEN,
    org=INFLUX_ORG
)

# Query heart rate data
query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {TIME_RANGE})
  |> filter(fn: (r) => r._measurement == "heart_rate")
  |> filter(fn: (r) => r._field == "heart_rate")
'''

print(f"⏳ Querying InfluxDB ({TIME_RANGE} range)...")
tables = client.query_api().query(query)

# Output CSV
output_filename = f"influx_heart_rate_export_{datetime.now().strftime('%Y%m%dT%H%M%S')}.csv"
with open(output_filename, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "bed_number", "heart_rate"])

    row_count = 0
    for table in tables:
        for record in table.records:
            writer.writerow([
                record.get_time().isoformat(),
                record.values.get("bed_number", ""),
                record.get_value()
            ])
            row_count += 1

print(f"✅ Export complete! {row_count} records written to {output_filename}")
