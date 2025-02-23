from graphviz import Digraph

# Create a new directed graph
deployment_diagram = Digraph("DeploymentDiagram", format="png")
deployment_diagram.attr(rankdir="TB")  # Top-to-bottom layout

# Nodes for Producers and Consumers
deployment_diagram.node("Producer", "Producer Script\n(Runs Locally)")
deployment_diagram.node("Consumer", "Consumer Script\n(Runs Locally)")

# Kafka Bus
deployment_diagram.node("Kafka", "Kafka Bus\n(Docker Container)")

# Databases
deployment_diagram.node("MasterDB", "InfluxDB Master\n(Docker Container\nPort: 8086)")
deployment_diagram.node("StandbyDB", "InfluxDB Standby\n(Docker Container\nPort: 8087)")

# Data Explorer (UI)
deployment_diagram.node("DataExplorer", "Data Explorer (UI)\n(InfluxDB Web UI)")

# Relationships
deployment_diagram.edge("Producer", "Kafka", "Sends sensor data")
deployment_diagram.edge("Kafka", "Consumer", "Delivers messages")
deployment_diagram.edge("Consumer", "MasterDB", "Writes data to Master")
deployment_diagram.edge("Consumer", "StandbyDB", "Writes data to Standby")
deployment_diagram.edge("MasterDB", "DataExplorer", "Queries and visualizes data")
deployment_diagram.edge("StandbyDB", "DataExplorer", "Queries and visualizes data (Failover)")

# Render the diagram
deployment_diagram.render("deployment_diagram", view=True)
