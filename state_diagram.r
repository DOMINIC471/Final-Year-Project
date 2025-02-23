from graphviz import Digraph

# Create a new directed graph
state_diagram = Digraph("StateDiagram", format="png")
state_diagram.attr(rankdir="LR", size="10")

# Define states for Master Database
state_diagram.node("MasterAvailable", "Master DB Available", shape="ellipse")
state_diagram.node("MasterDown", "Master DB Down", shape="ellipse")
state_diagram.node("FailoverToStandby", "Failover to Standby DB", shape="ellipse")
state_diagram.node("RecoverMaster", "Recover Master DB", shape="ellipse")

# Define states for Consumer
state_diagram.node("ConsumerRunning", "Consumer Running", shape="ellipse")
state_diagram.node("ConsumerWritesToBoth", "Writing to Both DBs", shape="ellipse")
state_diagram.node("ConsumerWritesToStandby", "Writing to Standby Only", shape="ellipse")

# Transitions for Master DB
state_diagram.edge("MasterAvailable", "MasterDown", label="Master Fails")
state_diagram.edge("MasterDown", "RecoverMaster", label="Master Recovered")
state_diagram.edge("RecoverMaster", "MasterAvailable", label="Back Online")

# Transitions for Consumer
state_diagram.edge("ConsumerRunning", "ConsumerWritesToBoth", label="Master & Standby Available")
state_diagram.edge("ConsumerRunning", "ConsumerWritesToStandby", label="Master Down Detected")
state_diagram.edge("ConsumerWritesToStandby", "ConsumerWritesToBoth", label="Master Back Online")

# Interaction between Master DB and Consumer
state_diagram.edge("MasterDown", "ConsumerWritesToStandby", label="Failover Triggered")
state_diagram.edge("RecoverMaster", "ConsumerWritesToBoth", label="Consumer Syncs with Master")

# Render the diagram
state_diagram.render("state_diagram", view=True)
