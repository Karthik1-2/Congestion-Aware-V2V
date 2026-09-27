
import networkx as nx

from simulation import VehicleSimulation

from routing import (
    shortest_distance_route,
    congestion_aware_route,
    delivery_aware_route
)

from packet import PacketSimulator


# Create network
simulation = VehicleSimulation(
    num_vehicles=60,
    communication_range=180,
    seed=42
)

G = simulation.create_network()

# Select vehicles at opposite ends of the road
sorted_vehicles = sorted(
    simulation.vehicles,
    key=lambda v: simulation.vehicles[v]["x"]
)

source = sorted_vehicles[0]
destination = sorted_vehicles[-1]

print("Source:", source)
print("Destination:", destination)

if not nx.has_path(G, source, destination):
    print("Source and destination are not connected.")
    raise SystemExit


# Calculate all three routes
routes = {
    "Shortest Distance": shortest_distance_route(
        G, source, destination
    ),

    "Congestion Aware": congestion_aware_route(
        G, source, destination
    ),

    "Delivery Aware": delivery_aware_route(
        G, source, destination
    )
}


# Compare packet transmission
print("\nV2V ROUTING COMPARISON")
print("=" * 55)

for name, route in routes.items():

    simulator = PacketSimulator(
        G,
        seed=42
    )

    results = simulator.transmit(
        route,
        num_packets=1000
    )

    print(f"\n{name}")
    print("-" * 40)
    print("Route:", route)
    print("Hops:", len(route) - 1)

    print(
        "Packet Delivery Ratio:",
        f"{results['pdr']:.2f}%"
    )

    print(
        "Average Delay:",
        f"{results['average_delay_ms']:.2f} ms"
    )

    print(
        "Hop Transmissions:",
        results["transmissions"]
    )

print("\nComparison completed.")