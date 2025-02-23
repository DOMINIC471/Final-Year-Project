import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.dates import date2num, DateFormatter
from datetime import datetime, timedelta

# Define the project phases and deadlines using phase numbers only
project_phases = [
    {"Phase": "Phase 1", "Start": "2024-10-01", "End": "2024-10-18"},
    {"Phase": "Phase 2", "Start": "2024-10-21", "End": "2024-11-10"},
    {"Phase": "Phase 3", "Start": "2024-11-13", "End": "2025-01-03"},
    {"Phase": "Phase 4", "Start": "2025-01-06", "End": "2025-01-10"},
    {"Phase": "Phase 5", "Start": "2025-01-13", "End": "2025-03-31"},
    {"Phase": "Phase 6", "Start": "2025-04-02", "End": "2025-04-15"},
    {"Phase": "Phase 7", "Start": "2025-04-17", "End": "2025-04-28"},
    {"Phase": "Phase 8", "Start": "2025-04-30", "End": "2025-05-05"}
]

# Convert dates and prepare data for plotting
data = pd.DataFrame(project_phases)
data['Start'] = pd.to_datetime(data['Start'])
data['End'] = pd.to_datetime(data['End'])
data['Duration'] = data['End'] - data['Start']

# Plotting the Gantt chart with arrows connecting phases
fig, ax = plt.subplots(figsize=(16, 8))
for i, task in enumerate(data.itertuples()):
    ax.barh(task.Phase, (task.End - task.Start).days, left=date2num(task.Start), color='skyblue')
    # Adding arrows to connect phases from the end of one to the start of the next
    if i < len(data) - 1:
        next_task = data.iloc[i + 1]
        ax.annotate('', xy=(date2num(next_task.Start), i + 0.5),
                    xytext=(date2num(task.End), i + 0.5),
                    arrowprops=dict(arrowstyle='->', lw=1.5, color='red'))

# Formatting the chart to remove unnecessary distance from the start date
ax.set_xlim([date2num(data['Start'].min()), date2num(data['End'].max() + timedelta(days=5))])
ax.xaxis_date()
ax.xaxis.set_major_formatter(DateFormatter('%d-%m-%Y'))
plt.xticks(date2num(data['Start'].tolist() + data['End'].tolist()), rotation=45, fontsize=10)
ax.set_xlabel('Date')
ax.set_title('Gantt Chart for Project Phases with Arrows')
plt.tight_layout()
plt.show()
