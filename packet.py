
import random


class PacketSimulator:
    def __init__(self, graph, seed=42):
        self.graph = graph
        self.rng = random.Random(seed)

    def transmit(self, route, num_packets=100, packet_size=1024):
        if not route:
            return None

        delivered = 0
        dropped = 0
        total_delay = 0.0
        total_transmissions = 0

        for packet_id in range(num_packets):
            packet_delivered = True
            packet_delay = 0.0

            # Forward through each hop
            for u, v in zip(route, route[1:]):
                link = self.graph[u][v]

                congestion = link["congestion"]
                distance = link["distance"]

                # Simplified packet loss model:
                # Higher congestion means higher loss.
                loss_probability = min(
                    0.02 + 0.25 * congestion,
                    0.95
                )

                # Simplified per-hop delay in milliseconds
                hop_delay = (
                    2.0
                    + distance / 200.0
                    + 15.0 * congestion
                )

                packet_delay += hop_delay
                total_transmissions += 1

                if self.rng.random() < loss_probability:
                    packet_delivered = False
                    break

            if packet_delivered:
                delivered += 1
                total_delay += packet_delay
            else:
                dropped += 1

        pdr = 100 * delivered / num_packets

        average_delay = (
            total_delay / delivered
            if delivered > 0 else 0.0
        )

        # This is useful delivered data per unit
        # of accumulated successful-packet delay,
        # NOT measured network throughput.
        delivered_bytes = delivered * packet_size

        return {
            "sent": num_packets,
            "delivered": delivered,
            "dropped": dropped,
            "pdr": pdr,
            "average_delay_ms": average_delay,
            "transmissions": total_transmissions,
            "delivered_bytes": delivered_bytes
        }