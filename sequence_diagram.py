# Generate a PlantUML script for the updated sequence diagram
plantuml_script = """
@startuml RealTimeHeartRateSystem

actor User

' User interacts with the Display Program
User -> "Display Program" : Select Bed Number (e.g., Bed 603)

' Display Program requests data for the specific Bed from the InfluxDB (Master)
"Display Program" -> "InfluxDB (Master)" : Request Data for Bed 603
"InfluxDB (Master)" -> "Display Program" : Return Real-Time Data for Bed 603

' In case of failure, Display Program requests data from the InfluxDB (Standby)
alt Master Failure
    "Display Program" -> "InfluxDB (Standby)" : Request Data for Bed 603
    "InfluxDB (Standby)" -> "Display Program" : Return Real-Time Data for Bed 603
end

' Display Program plots the real-time data for the User
"Display Program" -> User : Plot Real-Time Heart Rate Graph

' Kafka Bus forwards the request to the Producer
"Kafka Bus" -> "Producer" : Forward Request

' Producer fetches data from HR.csv or Database
"Producer" -> "HR.csv / Database" : Fetch 10-20 Records
"HR.csv / Database" -> "Producer" : Return Records

' Producer publishes the fetched data to Kafka
"Producer" -> "Kafka Bus" : Publish Records

' Kafka Bus forwards records to both ConsumerMaster and ConsumerStandBy
"Kafka Bus" -> "ConsumerMaster" : Deliver Records
"Kafka Bus" -> "ConsumerStandBy" : Deliver Records

' ConsumerMaster writes data to both TimescaleDB and InfluxDB
"ConsumerMaster" -> "TimescaleDB (Master)" : Write Data
"ConsumerMaster" -> "InfluxDB (Master)" : Write Data

' ConsumerStandBy writes data to InfluxDB Standby
"ConsumerStandBy" -> "InfluxDB (Standby)" : Write Data

' InfluxDB UI allows viewing historical data
User -> "InfluxDB UI" : Query Historical Data
"InfluxDB UI" -> "InfluxDB (Master)" : Fetch Historical Records
"InfluxDB (Master)" -> "InfluxDB UI" : Return Historical Data

@enduml

"""

# Save the script to a file
with open("sequence_diagram.puml", "w") as file:
    file.write(plantuml_script)

print("PlantUML script for the updated sequence diagram has been generated as 'sequence_diagram.puml'.")
print("Use PlantUML to visualize the diagram.")
