from graphviz import Digraph

# Initialize the Digraph
component_diagram = Digraph("Component Diagram", filename="component_diagram", format="png")
component_diagram.attr(rankdir="LR")

# Define components
component_diagram.node("Producer", shape="rectangle", style="filled", color="lightblue", label="Producer\n(Sensor Data Generator)")
component_diagram.node("Kafka", shape="ellipse", style="filled", color="lightgrey", label="Kafka Broker\n(Message Bus)")
component_diagram.node("Consumer", shape="rectangle", style="filled", color="lightgreen", label="Consumer\n(Data Processor)")
component_diagram.node("MasterDB", shape="cylinder", style="filled", color="yellow", label="Master\nInfluxDB")
component_diagram.node("StandbyDB", shape="cylinder", style="filled", color="yellow", label="Standby\nInfluxDB")
component_diagram.node("DataExplorer", shape="rectangle", style="filled", color="orange", label="Data Explorer\n(InfluxDB UI)")

# Connections
component_diagram.edge("Producer", "Kafka", label="Publishes Sensor Data")
component_diagram.edge("Kafka", "Consumer", label="Distributes Data")
component_diagram.edge("Consumer", "MasterDB", label="Writes Data")
component_diagram.edge("Consumer", "StandbyDB", label="Writes Data (Failover)")
component_diagram.edge("MasterDB", "DataExplorer", label="Visualizes Data")
component_diagram.edge("StandbyDB", "DataExplorer", label="(Failover Visuals)")

# Render the diagram
component_diagram.render(view=True)
