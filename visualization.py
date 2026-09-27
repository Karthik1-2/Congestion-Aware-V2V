
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation
from simulation import VehicleSimulation

simulation = VehicleSimulation(
    num_vehicles=30,
    communication_range=180
)

fig, ax = plt.subplots(figsize=(12, 5))


def update(frame):
    ax.clear()

    # Move vehicles after the initial frame
    if frame > 0:
        simulation.move_vehicles(dt=1)

    G = simulation.create_network()

    positions = nx.get_node_attributes(G, "pos")

    # Draw road lanes
    for y in [5, 35, 65, 95]:
        ax.axhline(
            y,
            color="gray",
            linestyle="--",
            alpha=0.5
        )

    # Draw wireless communication links
    nx.draw_networkx_edges(
        G,
        positions,
        ax=ax,
        edge_color="lightgray",
        alpha=0.5
    )

    # Draw vehicles
    nx.draw_networkx_nodes(
        G,
        positions,
        ax=ax,
        node_color="royalblue",
        node_size=180
    )

    nx.draw_networkx_labels(
        G,
        positions,
        ax=ax,
        font_size=7,
        font_color="white"
    )

    ax.set_xlim(0, 1000)
    ax.set_ylim(0, 110)
    ax.set_title(
        f"Dynamic V2V Network - Time: {frame}s"
    )
    ax.set_xlabel("Road distance (metres)")
    ax.set_ylabel("Road lanes")


animation = FuncAnimation(
    fig,
    update,
    frames=100,
    interval=300,
    repeat=False
)

plt.tight_layout()
plt.show()