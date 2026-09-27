"""Stage 15: reproducible, dynamic V2V routing comparison.

Run alongside simulation.py and routing.py:
    python stage15_experiment.py
For a quick check:
    python stage15_experiment.py --trials 1 --packets 5
"""
import argparse
import csv
import math
import random
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import networkx as nx

from simulation import VehicleSimulation
from routing import (
    shortest_distance_route,
    congestion_aware_route,
    delivery_aware_route,
)

ALGORITHMS = {
    'Shortest Distance': shortest_distance_route,
    'Congestion Aware': congestion_aware_route,
    'Delivery Aware': delivery_aware_route,
}
VEHICLE_COUNTS = (30, 60, 80, 100)
MAX_STEPS = 15
MAX_HOPS = 15
MAX_RECOVERIES = 5
MOVEMENT_DT = 0.5
COMMUNICATION_RANGE = 100
BASE_SEED = 20260927
RESULTS = Path(__file__).resolve().parent / 'results'


def route_or_none(function, graph, source, destination):
    """Validate an algorithm's route against the supplied graph."""
    try:
        route = function(graph.copy(), source, destination)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    if not route or route[0] != source or route[-1] != destination:
        return None
    if any(not graph.has_edge(u, v) for u, v in zip(route, route[1:])):
        return None
    return route


def choose_pair(graph, rng):
    """Prefer reachable >=3-hop pairs; otherwise sample a reachable pair.

    Selection is based on unweighted shortest-hop distance, independently
    of the three algorithms being evaluated.
    """
    long_pairs = []
    other_pairs = []
    for source, lengths in nx.all_pairs_shortest_path_length(graph):
        for destination, hops in lengths.items():
            if source >= destination or hops == 0:
                continue
            if hops >= 3:
                long_pairs.append((source, destination))
            else:
                other_pairs.append((source, destination))
    pool = long_pairs or other_pairs
    if not pool:
        return None
    return rng.choice(pool)


def make_scenario(vehicle_count, trial, packet):
    """One independently seeded moving traffic scenario, reused by all algorithms."""
    seed = BASE_SEED + vehicle_count * 1000000 + trial * 10000 + packet
    simulation = VehicleSimulation(
        num_vehicles=vehicle_count,
        communication_range=COMMUNICATION_RANGE,
        seed=seed,
    )
    graphs = [simulation.create_network()]
    pair = choose_pair(graphs[0], random.Random(seed + 12345))
    for _ in range(MAX_STEPS):
        simulation.move_vehicles(MOVEMENT_DT)
        graphs.append(simulation.create_network())
    return pair, graphs, seed


def simulate_packet(graphs, pair, route_function, seed):
    """One hop attempt per step; detect breaks between planning and movement."""
    result = dict(delivered=0, dropped=1, direct=0, multi_hop=0,
                  hops=0, transmissions=0, delay_ms=0.0, link_breaks=0,
                  recovery_attempts=0, successful_recoveries=0,
                  failed_recoveries=0)
    if pair is None:
        return result
    source, destination = pair
    current = source
    rng = random.Random(seed + 987654)
    route = route_or_none(route_function, graphs[0], current, destination)
    if not route or len(route) < 2:
        return result
    planned_next = route[1]
    recovery_pending = False

    for step in range(MAX_STEPS):
        graph = graphs[step + 1]  # movement occurs after previous planning
        if not graph.has_edge(current, planned_next):
            result['link_breaks'] += 1
            result['delay_ms'] += 5.0  # modeled route-recovery overhead
            if recovery_pending:
                result['failed_recoveries'] += 1
                recovery_pending = False
            if result['recovery_attempts'] >= MAX_RECOVERIES:
                break
            result['recovery_attempts'] += 1
            alternative = route_or_none(route_function, graph, current, destination)
            if not alternative or len(alternative) < 2:
                result['failed_recoveries'] += 1
                break
            planned_next = alternative[1]
            recovery_pending = True
            continue

        link = graph[current][planned_next]
        congestion = link['congestion']
        distance = link['distance']
        loss_probability = min(0.02 + 0.25 * congestion, 0.95)
        result['delay_ms'] += 2.0 + distance / 200.0 + 15.0 * congestion
        result['transmissions'] += 1
        if rng.random() < loss_probability:
            break
        result['hops'] += 1
        current = planned_next
        if recovery_pending:
            result['successful_recoveries'] += 1
            recovery_pending = False
        if current == destination:
            result['delivered'] = 1
            result['dropped'] = 0
            result['direct'] = int(result['hops'] == 1)
            result['multi_hop'] = int(result['hops'] > 1)
            break
        if result['hops'] >= MAX_HOPS:
            break
        next_route = route_or_none(route_function, graph, current, destination)
        if not next_route or len(next_route) < 2:
            break
        planned_next = next_route[1]

    if recovery_pending:
        result['failed_recoveries'] += 1
    return result


def aggregate(rows, vehicle_count, trial, algorithm):
    sent = len(rows)
    delivered_rows = [r for r in rows if r['delivered']]
    delivered = len(delivered_rows)
    attempts = sum(r['recovery_attempts'] for r in rows)
    successes = sum(r['successful_recoveries'] for r in rows)
    return {
        'vehicles': vehicle_count, 'trial': trial, 'algorithm': algorithm,
        'sent': sent, 'delivered': delivered, 'dropped': sent - delivered,
        'pdr_pct': round(100 * delivered / sent, 3),
        'direct_deliveries': sum(r['direct'] for r in rows),
        'multi_hop_deliveries': sum(r['multi_hop'] for r in rows),
        'average_delivered_delay_ms': round(
            sum(r['delay_ms'] for r in delivered_rows) / delivered, 3
        ) if delivered else '',
        'average_delivered_hops': round(
            sum(r['hops'] for r in delivered_rows) / delivered, 3
        ) if delivered else '',
        'hop_transmissions': sum(r['transmissions'] for r in rows),
        'link_breaks': sum(r['link_breaks'] for r in rows),
        'recovery_attempts': attempts,
        'successful_recoveries': successes,
        'failed_recoveries': sum(r['failed_recoveries'] for r in rows),
        'recovery_success_pct': round(100 * successes / attempts, 3) if attempts else '',
    }


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_plots(summaries):
    for key, ylabel, filename in (
        ('pdr_pct', 'Packet delivery ratio (%)', 'stage15_pdr.png'),
        ('average_delivered_delay_ms', 'Average delivered-packet delay (ms)', 'stage15_delay.png'),
    ):
        plt.figure(figsize=(9, 5))
        for algorithm in ALGORITHMS:
            xs, ys = [], []
            for count in VEHICLE_COUNTS:
                samples = [float(row[key]) for row in summaries
                           if row['vehicles'] == count
                           and row['algorithm'] == algorithm
                           and row[key] != '']
                if samples:
                    xs.append(count)
                    ys.append(sum(samples) / len(samples))
            if xs:
                plt.plot(xs, ys, marker='o', label=algorithm)
        plt.xlabel('Number of vehicles')
        plt.ylabel(ylabel)
        plt.title(ylabel + ' vs traffic density')
        plt.xticks(VEHICLE_COUNTS)
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.savefig(RESULTS / filename, dpi=180)
        plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, default=20)
    parser.add_argument('--packets', type=int, default=100)
    args = parser.parse_args()
    if args.trials < 1 or args.packets < 1:
        parser.error('--trials and --packets must be positive')
    RESULTS.mkdir(parents=True, exist_ok=True)
    summaries = []
    packet_rows = []
    for count in VEHICLE_COUNTS:
        for trial in range(1, args.trials + 1):
            outcomes = {name: [] for name in ALGORITHMS}
            for packet in range(1, args.packets + 1):
                pair, graphs, seed = make_scenario(count, trial, packet)
                for name, function in ALGORITHMS.items():
                    result = simulate_packet(graphs, pair, function, seed)
                    outcomes[name].append(result)
                    packet_rows.append({
                        'vehicles': count, 'trial': trial, 'packet': packet,
                        'algorithm': name, 'source': pair[0] if pair else '',
                        'destination': pair[1] if pair else '', **result,
                    })
            for name, rows in outcomes.items():
                summaries.append(aggregate(rows, count, trial, name))
            print(f'Finished {count} vehicles, trial {trial}/{args.trials}', flush=True)
    write_csv(RESULTS / 'stage15_results.csv', summaries)
    write_csv(RESULTS / 'stage15_packet_logs.csv', packet_rows)
    make_plots(summaries)
    print('\nSaved Stage 15 CSV reports and graphs in:', RESULTS)
    for count in VEHICLE_COUNTS:
        print(f'\n{count} vehicles:')
        for name in ALGORITHMS:
            matches = [r for r in summaries if r['vehicles'] == count
                       and r['algorithm'] == name]
            mean_pdr = sum(r['pdr_pct'] for r in matches) / len(matches)
            print(f'  {name}: mean PDR {mean_pdr:.2f}%')
    print('\nNote: selected pairs favor >=3-hop paths when available;'
          ' delay averages include delivered packets only.')


if __name__ == '__main__':
    main()
