import json 
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import os

def clean_traj(traj, task):
    cleaned = []
    i = 0
    counter = 0
    while(i < len(traj)):
        if(traj[i]['role'] == 'assistant' and traj[i]['content'] is None):
            i += 1
            entry = {'index': counter, 'role': traj[i]['role'], 'function': traj[i]['name'], 'response': traj[i]['content']}
        else:
            entry = {'index': counter, 'role': traj[i]['role'], 'content': traj[i]['content']}
        cleaned.append(entry)
        i += 1
        counter+=1
    cleaned[0]['task'] = task
    return cleaned

def clean_trajectories(data, save=False):
    folder = 'trajectories'
    clean_data = []
    for i in range(len(data)):
        file = os.path.join(folder, f'{i}')
        trajectory = clean_traj(data[i]['traj'], data[i]['info']['task']['instruction'])
        clean_data.append(trajectory)
        if save:
            with open(file, "w") as f:
                json.dump(trajectory, f, indent=4)  
    return clean_data

def get_graph(trajectory, filename):
    G = nx.DiGraph()
    color_map = {
        "user": "skyblue",
        "assistant": "lightgreen",
        "tool": "orange",
        "system": "lightgray",
    }
    nodes_per_row = 6
    row_height = 2
    for i, item in enumerate(trajectory):
        role = item["role"]
        label= item['index']
        G.add_node(i, label=label, role=role)
        if i > 0:
            G.add_edge(i - 1, i)
    
    pos = {}
    for i in G.nodes:
        row = i // nodes_per_row
        col = i % nodes_per_row
        if row % 2 == 0:
            x = col
        else:
            x = nodes_per_row - 1 - col
        y = -row * row_height
        pos[i] = (x, y)

    node_colors = [color_map[G.nodes[i]["role"]] for i in G.nodes]
    labels = nx.get_node_attributes(G, "label")

    # Draw the graph
    plt.figure(figsize=(10, 6))
    nx.draw(G, pos, with_labels=False, node_color=node_colors, node_size=2500, arrows=True, arrowstyle='->', arrowsize=15)
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_color="black")

    # Create legend handles
    legend_handles = [Patch(color=color_map[role], label=role.capitalize()) for role in color_map]
    plt.legend(handles=legend_handles, loc="lower left", title="Roles")
    plt.title("Trajectory Visualization")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(filename, dpi=300) 

def create_graphs(data):
    folder = 'graphs'
    for i in range(len(data)):
        filename = os.path.join(folder, f'{i}.png')
        trajectory = data[i]
        get_graph(trajectory, filename)

if __name__ == "__main__":
    filename = 'raw_logs/tool-calling-none-0.1_range_0-100_user-none-llm_06232025.json'
    data = json.load(open(filename, 'r'))
    data = clean_trajectories(data, save=True)
    create_graphs(data)