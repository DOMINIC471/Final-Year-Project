import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle, FancyArrowPatch

def draw_use_case_diagram():
    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(-2, 12)
    ax.set_ylim(-2, 12)

    # System Boundary
    system_boundary = Rectangle((2, 0), 6, 10, edgecolor='black', facecolor='none', linewidth=2)
    ax.add_patch(system_boundary)
    ax.text(4.5, 10.5, "System", fontsize=12, weight='bold')

    # Use Cases
    use_cases = {
        "Write Sensor Data": (5, 8),
        "Query Data": (5, 6),
        "View Graphs": (5, 4),
        "Failover to Standby": (5, 2)
    }
    for name, (x, y) in use_cases.items():
        ax.add_patch(Ellipse((x, y), 3, 1.5, edgecolor='blue', facecolor='lightblue', linewidth=2))
        ax.text(x, y, name, ha='center', va='center', fontsize=10)

    # Actors
    actors = {
        "Producer": (0, 9),
        "Consumer": (0, 5),
        "Data Explorer": (0, 3)
    }
    for name, (x, y) in actors.items():
        ax.text(x, y, name, ha='center', va='center', fontsize=10, bbox=dict(facecolor='white', edgecolor='black', boxstyle='round'))

    # Relationships
    relationships = [
        ("Producer", "Write Sensor Data"),
        ("Consumer", "Write Sensor Data"),
        ("Consumer", "Query Data"),
        ("Data Explorer", "View Graphs"),
        ("Consumer", "Failover to Standby")
    ]
    for actor, use_case in relationships:
        start_x, start_y = actors[actor]
        end_x, end_y = use_cases[use_case]
        arrow = FancyArrowPatch((start_x + 1, start_y), (end_x - 1.5, end_y), arrowstyle='-|>', mutation_scale=10, color='black', linewidth=1.5)
        ax.add_patch(arrow)

    # Remove axes for better visualization
    ax.axis('off')
    plt.title("Use Case Diagram", fontsize=16)
    plt.show()

# Call the function to draw the diagram
draw_use_case_diagram()
