# 📄 visualize_graph.py
import json
import networkx as nx
import matplotlib.pyplot as plt

with open("output_graph.json", "r") as f:
    graph = json.load(f)

G = nx.DiGraph()
G.add_nodes_from(graph["nodes"])
G.add_edges_from(graph["edges"])

plt.figure(figsize=(10, 6))
pos = nx.spring_layout(G)

# 노드 시각화
nx.draw_networkx_nodes(G, pos, node_size=700)

# 엣지 (화살표) 시각화 - 분홍색 강조
nx.draw_networkx_edges(
    G,
    pos,
    arrows=True,
    arrowstyle='-|>',
    arrowsize=20,
    edge_color="#e75480",
    width=2
)

# 라벨
nx.draw_networkx_labels(G, pos)

plt.title("Dependency Graph")
plt.axis("off")
plt.savefig("graph_output.png")
print("✅ 의존 그래프 시각화 완료: graph_output.png")
