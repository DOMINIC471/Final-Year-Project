from diagrams import Diagram, Cluster
from diagrams.programming.language import Python
from diagrams.generic.database import SQL
from diagrams.generic.storage import Storage
from diagrams.onprem.queue import Kafka

with Diagram("Class Diagram for Producer and Consumer", show=True):
    producer_class = Python("KafkaProducer")
    consumer_class = Python("KafkaConsumer")

    with Cluster("Attributes"):
        producer_attributes = [Storage("KafkaConfig"), Storage("SensorConfig")]
        consumer_attributes = [
            Storage("KafkaConfig"),
            Storage("InfluxDBConfig"),
            Storage("HeartbeatConfig"),
        ]

    with Cluster("Methods"):
        producer_methods = [
            SQL("produce_message"),
            SQL("delivery_report"),
        ]
        consumer_methods = [
            SQL("consume_message"),
            SQL("write_to_influxdb"),
            SQL("send_heartbeat"),
            SQL("is_master_alive"),
        ]

    # Producer relationships
    producer_class >> producer_attributes
    producer_class >> producer_methods

    # Consumer relationships
    consumer_class >> consumer_attributes
    consumer_class >> consumer_methods

    # Interaction between Producer and Kafka
    producer_class >> Kafka("Kafka Bus")

    # Interaction between Consumer and Kafka/InfluxDB
    consumer_class << Kafka("Kafka Bus")
    consumer_class >> SQL("MasterDB")
    consumer_class >> SQL("StandbyDB")
