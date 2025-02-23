from diagrams import Diagram, Cluster
from diagrams.onprem.queue import Kafka
from diagrams.onprem.database import InfluxDB
from diagrams.onprem.compute import Server
from diagrams.programming.language import Python
from diagrams.custom import Custom

with Diagram("Activity Diagram for Data Operations", direction="LR"):

    producer = Python("Producer Script")
    kafka = Kafka("Kafka Bus")
    consumer = Python("Consumer Script")

    with Cluster("InfluxDB System"):
        master_db = InfluxDB("Master DB")
        standby_db = InfluxDB("Standby DB")
        data_explorer = Custom("Data Explorer", "./explorer_icon.png")  # Replace with your explorer icon.

    # Data ingestion flow
    producer >> kafka >> consumer >> master_db
    consumer >> standby_db

    # Failover logic
    consumer >> [standby_db, master_db]

    # Querying from data explorer
    data_explorer >> [master_db, standby_db]
