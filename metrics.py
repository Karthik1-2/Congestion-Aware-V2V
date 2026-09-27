
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from simulation import VehicleSimulation

from routing import (
    shortest_distance_route,
    congestion_aware_route,
    delivery_aware_route
)

from packet import PacketSimulator


# ==========================================
# 1. EXPERIMENT CONFIGURATION
# ==========================================

VEHICLE_COUNTS = [20, 40, 60, 80, 100]

TRIALS = 20
NUM_PACKETS = 1000
COMMUNICATION_RANGE = 180

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

ALGORITHMS = [
    "Shortest Distance",
    "Congestion Aware",
    "Delivery Aware"
]

COLORS = {
    "Shortest Distance": "red",
    "Congestion Aware": "blue",
    "Delivery Aware": "green"
}


# ==========================================
# 2. RUN A SINGLE TRIAL
# ==========================================

def run_trial(vehicle_count, trial):

    seed = vehicle_count * 1000 + trial

    simulation = VehicleSimulation(
        num_vehicles=vehicle_count,
        communication_range=COMMUNICATION_RANGE,
        seed=seed
    )

    G = simulation.create_network()

    # Select vehicles at opposite ends
    # of the road to test multi-hop routing.
    sorted_vehicles = sorted(
        simulation.vehicles,
        key=lambda v: simulation.vehicles[v]["x"]
    )

    source = sorted_vehicles[0]
    destination = sorted_vehicles[-1]

    # Exclude disconnected trials
    if not nx.has_path(G, source, destination):
        return None

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

    results = {}

    for name, route in routes.items():

        if route is None:
            return None

        simulator = PacketSimulator(
            G,
            seed=seed + 50000
        )

        packet_results = simulator.transmit(
            route,
            num_packets=NUM_PACKETS
        )

        results[name] = {
            "pdr": packet_results["pdr"],
            "delivered": packet_results["delivered"],
            "sent": packet_results["sent"],
            "delay": packet_results["average_delay_ms"],
            "transmissions": packet_results["transmissions"],
            "hops": len(route) - 1
        }

    return results


# ==========================================
# 3. TEST ALL VEHICLE DENSITIES
# ==========================================

rows = []

for vehicle_count in VEHICLE_COUNTS:

    print("\n" + "=" * 55)
    print(f"TESTING {vehicle_count} VEHICLES")
    print("=" * 55)

    trial_results = []

    for trial in range(TRIALS):

        result = run_trial(
            vehicle_count,
            trial
        )

        if result is not None:
            trial_results.append(result)

    completed = len(trial_results)

    print(
        f"Connected trials: {completed}/{TRIALS}"
    )

    if completed == 0:
        print("No connected routes found.")
        continue

    # ======================================
    # CALCULATE AVERAGE PERFORMANCE
    # ======================================

    for algorithm in ALGORITHMS:

        results = [
            trial[algorithm]
            for trial in trial_results
        ]

        total_sent = sum(
            r["sent"] for r in results
        )

        total_delivered = sum(
            r["delivered"] for r in results
        )

        pdr = (
            100 * total_delivered / total_sent
        )

        # Weight delay by successfully
        # delivered packet counts.
        if total_delivered > 0:

            average_delay = sum(
                r["delay"] * r["delivered"]
                for r in results
            ) / total_delivered

        else:
            average_delay = float("nan")

        average_hops = sum(
            r["hops"] for r in results
        ) / completed

        average_transmissions = sum(
            r["transmissions"] for r in results
        ) / completed

        row = {
            "vehicles": vehicle_count,
            "algorithm": algorithm,
            "connected_trials": completed,
            "attempted_trials": TRIALS,
            "pdr": round(pdr, 2),
            "delay_ms": round(average_delay, 2),
            "average_hops": round(average_hops, 2),
            "transmissions": round(
                average_transmissions, 2
            )
        }

        rows.append(row)

        print(f"\n{algorithm}")
        print(f"  PDR: {pdr:.2f}%")
        print(
            f"  Average delay: "
            f"{average_delay:.2f} ms"
        )
        print(
            f"  Average hops: "
            f"{average_hops:.2f}"
        )


# ==========================================
# 4. SAVE CSV RESULTS
# ==========================================

csv_path = (
    RESULTS_DIR / "three_algorithm_comparison.csv"
)

with open(
    csv_path,
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=[
            "vehicles",
            "algorithm",
            "connected_trials",
            "attempted_trials",
            "pdr",
            "delay_ms",
            "average_hops",
            "transmissions"
        ]
    )

    writer.writeheader()
    writer.writerows(rows)

print(f"\nResults saved to: {csv_path}")


# ==========================================
# 5. GENERATE PERFORMANCE GRAPHS
# ==========================================

def plot_metric(metric, ylabel, filename):

    plt.figure(figsize=(10, 6))

    for algorithm in ALGORITHMS:

        selected = [
            row for row in rows
            if row["algorithm"] == algorithm
        ]

        x = [
            row["vehicles"]
            for row in selected
        ]

        y = [
            row[metric]
            for row in selected
        ]

        plt.plot(
            x,
            y,
            marker="o",
            linewidth=2,
            markersize=7,
            color=COLORS[algorithm],
            label=algorithm
        )

    plt.xlabel("Number of Vehicles")
    plt.ylabel(ylabel)

    plt.title(
        f"{ylabel} vs Vehicle Density"
    )

    plt.xticks(VEHICLE_COUNTS)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.savefig(
        RESULTS_DIR / filename,
        dpi=300
    )

    plt.close()


if rows:

    plot_metric(
        "pdr",
        "Packet Delivery Ratio (%)",
        "three_algorithm_pdr.png"
    )

    plot_metric(
        "delay_ms",
        "Average End-to-End Delay (ms)",
        "three_algorithm_delay.png"
    )

    plot_metric(
        "average_hops",
        "Average Hop Count",
        "three_algorithm_hops.png"
    )

    plot_metric(
        "transmissions",
        "Average Hop Transmissions",
        "three_algorithm_transmissions.png"
    )

    print("All comparison graphs generated.")

