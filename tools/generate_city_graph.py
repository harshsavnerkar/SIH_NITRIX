#!/usr/bin/env python3
import json
from pathlib import Path

# Generate a rich road graph network around Barave Road / Kalyan / Pune
# with main corridors, arterial roads, cross streets, and intersections.

nodes_lat = []
nodes_lon = []
edges = []

def add_node(lat, lon):
    nodes_lat.append(round(lat, 6))
    nodes_lon.append(round(lon, 6))
    return len(nodes_lat) - 1

def add_edge(u, v):
    edges.append([u, v])

# Corridor 1: Barave Road Main Corridor (West to East)
c1_nodes = []
base_lat, base_lon = 19.2420, 73.1300
for i in range(25):
    lat = base_lat + i * 0.00015
    lon = base_lon + i * 0.00040
    c1_nodes.append(add_node(lat, lon))

for i in range(len(c1_nodes) - 1):
    add_edge(c1_nodes[i], c1_nodes[i+1])

# Corridor 2: North-South Arterial Avenue
c2_nodes = []
base_lat, base_lon = 19.2400, 73.1350
for i in range(20):
    lat = base_lat + i * 0.00030
    lon = base_lon + i * 0.00005
    c2_nodes.append(add_node(lat, lon))

for i in range(len(c2_nodes) - 1):
    add_edge(c2_nodes[i], c2_nodes[i+1])

# Corridor 3: Parallel Bypass Highway
c3_nodes = []
base_lat, base_lon = 19.2410, 73.1280
for i in range(22):
    lat = base_lat + i * 0.00020
    lon = base_lon + i * 0.00045
    c3_nodes.append(add_node(lat, lon))

for i in range(len(c3_nodes) - 1):
    add_edge(c3_nodes[i], c3_nodes[i+1])

# Cross streets connecting Corridor 1, 2, and 3
for i in range(0, 20, 4):
    add_edge(c1_nodes[i], c2_nodes[min(i, len(c2_nodes)-1)])
    add_edge(c1_nodes[i], c3_nodes[min(i, len(c3_nodes)-1)])

# Additional Pune central network
p_base_lat, p_base_lon = 18.5200, 73.8500
p_nodes = []
for r in range(5):
    row_nodes = []
    for c in range(5):
        lat = p_base_lat + r * 0.0010
        lon = p_base_lon + c * 0.0010
        row_nodes.append(add_node(lat, lon))
    p_nodes.append(row_nodes)

for r in range(5):
    for c in range(5):
        if c < 4:
            add_edge(p_nodes[r][c], p_nodes[r][c+1])
        if r < 4:
            add_edge(p_nodes[r][c], p_nodes[r+1][c])

graph_data = [{"lat": nodes_lat, "lon": nodes_lon}, edges]

out_paths = [
    Path("android/app/src/main/assets/maps/road_graph.json"),
    Path("python/hmm/road_graph.json")
]

for p in out_paths:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(graph_data, f, separators=(",", ":"))
    print(f"Wrote {len(nodes_lat)} nodes and {len(edges)} edges to {p}")
