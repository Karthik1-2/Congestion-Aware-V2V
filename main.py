import networkx as nx
from packet import PacketSimulator
from simulation import VehicleSimulation

from routing import (
    shortest_distance_route,
    congestion_aware_route,
    calculate_route_cost
)


# =========================================
# CREATE SIMULATION
# =========================================

simulation = VehicleSimulation(

    num_vehicles=30,

    communication_range=180
)


# =========================================
# CREATE V2V NETWORK
# =========================================

G = simulation.create_network()


print("\n========================================")
print("     CONGESTION-AWARE V2V ROUTING")
print("========================================")

print(
    "\nNumber of vehicles:",
    len(G.nodes)
)

print(
    "Number of V2V links:",
    len(G.edges)
)


# =========================================
# SELECT SOURCE AND DESTINATION
# =========================================

source = 0

destination = 29


# =========================================
# FIND CONNECTED VEHICLES
# =========================================

if not nx.has_path(
    G,
    source,
    destination
):

    print(
        "\nSource and destination "
        "are not connected."
    )

    components = list(
        nx.connected_components(G)
    )

    largest_component = max(
        components,
        key=len
    )

    nodes = list(
        largest_component
    )

    if len(nodes) >= 2:

        source = nodes[0]

        destination = nodes[-1]

        print(
            "New source:",
            source
        )

        print(
            "New destination:",
            destination
        )

    else:

        print(
            "Not enough connected vehicles."
        )

        exit()


# =========================================
# SHORTEST DISTANCE ROUTE
# =========================================

shortest_route = shortest_distance_route(

    G,

    source,

    destination
)


# =========================================
# CONGESTION-AWARE ROUTE
# =========================================

congestion_route = congestion_aware_route(

    G,

    source,

    destination
)


# =========================================
# DISPLAY SOURCE / DESTINATION
# =========================================

print(
    "\nSource vehicle:",
    source
)

print(
    "Destination vehicle:",
    destination
)


# =========================================
# DISPLAY ROUTES
# =========================================

print(
    "\nShortest-distance route:"
)

print(
    shortest_route
)


print(
    "\nCongestion-aware route:"
)

print(
    congestion_route
)


# =========================================
# ROUTE COSTS
# =========================================

shortest_cost = calculate_route_cost(

    G,

    shortest_route
)


congestion_cost = calculate_route_cost(

    G,

    congestion_route
)


print(
    "\nShortest route cost:",
    round(
        shortest_cost,
        2
    )
)


print(
    "Congestion-aware route cost:",
    round(
        congestion_cost,
        2
    )
)


# =========================================
# ROUTE HOPS
# =========================================

print(
    "\nShortest route hops:",
    len(shortest_route) - 1
)


print(
    "Congestion-aware route hops:",
    len(congestion_route) - 1
)


# =========================================
# SHOW CONGESTION ON CONGESTION-AWARE ROUTE
# =========================================

print(
    "\nCongestion values on selected route:"
)


for i in range(
    len(congestion_route) - 1
):

    u = congestion_route[i]

    v = congestion_route[i + 1]

    congestion = G[u][v][
        "congestion"
    ]

    distance = G[u][v][
        "distance"
    ]

    print(
        f"Vehicle {u} -> Vehicle {v} | "
        f"Distance = {distance:.2f} m | "
        f"Congestion = {congestion:.2f}"
    )

# =========================================
# MULTI-HOP PACKET TRANSMISSION
# =========================================

print("\n========================================")
print("      MULTI-HOP PACKET TRANSMISSION")
print("========================================")

NUM_PACKETS = 1000

# Independent simulators with identical
# random seeds for reproducible experiments
shortest_simulator = PacketSimulator(G, seed=42)
congestion_simulator = PacketSimulator(G, seed=42)

shortest_results = shortest_simulator.transmit(
    shortest_route,
    num_packets=NUM_PACKETS
)

congestion_results = congestion_simulator.transmit(
    congestion_route,
    num_packets=NUM_PACKETS
)


def display_results(name, results):
    print(f"\n{name}")
    print("-" * 40)

    if results is None:
        print("No valid route.")
        return

    print("Packets sent:", results["sent"])
    print("Packets delivered:", results["delivered"])
    print("Packets dropped:", results["dropped"])
    print(f"Packet delivery ratio: {results['pdr']:.2f}%")
    print(
        "Average end-to-end delay:",
        f"{results['average_delay_ms']:.2f} ms"
    )
    print(
        "Total hop transmissions:",
        results["transmissions"]
    )


display_results(
    "SHORTEST-DISTANCE ROUTING",
    shortest_results
)

display_results(
    "CONGESTION-AWARE ROUTING",
    congestion_results
)

print(
    "\n========================================"
)

print(
    "        SIMULATION COMPLETED"
)

print(
    "========================================"
)