
import random
import math
import networkx as nx


class VehicleSimulation:

    # ==========================================
    # 1. INITIALIZE SIMULATION
    # ==========================================

    def __init__(
        self,
        num_vehicles=30,
        communication_range=180,
        seed=42
    ):

        self.num_vehicles = num_vehicles
        self.communication_range = communication_range

        # Road configuration
        self.road_length = 1000
        self.lanes = [20, 50, 80]

        self.vehicles = {}

        # Each trial uses its own random generator.
        # Different seeds produce different traffic.
        self.rng = random.Random(seed)

        # Generate vehicles
        for i in range(num_vehicles):

            self.vehicles[i] = {

                "x": self.rng.uniform(
                    0,
                    self.road_length
                ),

                "y": self.rng.choice(
                    self.lanes
                ),

                "speed": self.rng.uniform(
                    10,
                    25
                ),

                "congestion": 0.0
            }

        # Calculate initial congestion
        self.update_congestion()

    # ==========================================
    # 2. MOVE VEHICLES
    # ==========================================

    def move_vehicles(self, dt=1):

        for vehicle in self.vehicles.values():

            vehicle["x"] = (
                vehicle["x"]
                + vehicle["speed"] * dt
            ) % self.road_length

        # Update congestion after movement
        self.update_congestion()

    # ==========================================
    # 3. CALCULATE DISTANCE
    # ==========================================

    def distance_between(
        self,
        vehicle_a,
        vehicle_b
    ):

        return math.dist(

            (
                vehicle_a["x"],
                vehicle_a["y"]
            ),

            (
                vehicle_b["x"],
                vehicle_b["y"]
            )
        )

    # ==========================================
    # 4. CALCULATE DYNAMIC CONGESTION
    # ==========================================

    def update_congestion(self):

        vehicle_ids = list(
            self.vehicles.keys()
        )

        for vehicle_id in vehicle_ids:

            vehicle = self.vehicles[
                vehicle_id
            ]

            nearby_count = 0
            nearby_speeds = []

            # Find neighbouring vehicles
            for other_id in vehicle_ids:

                if other_id == vehicle_id:
                    continue

                other = self.vehicles[
                    other_id
                ]

                distance = self.distance_between(
                    vehicle,
                    other
                )

                if distance <= self.communication_range:

                    nearby_count += 1

                    nearby_speeds.append(
                        other["speed"]
                    )

            # ----------------------------------
            # VEHICLE DENSITY FACTOR
            # ----------------------------------

            density_factor = min(
                nearby_count / 8.0,
                1.0
            )

            # ----------------------------------
            # VEHICLE SPEED FACTOR
            # ----------------------------------

            if nearby_speeds:

                average_speed = (
                    sum(nearby_speeds)
                    / len(nearby_speeds)
                )

                speed_factor = max(
                    0.0,
                    1.0 - (
                        average_speed / 25.0
                    )
                )

            else:

                speed_factor = 0.0

            # ----------------------------------
            # FINAL CONGESTION VALUE
            # ----------------------------------

            congestion = (
                0.7 * density_factor
                + 0.3 * speed_factor
            )

            congestion = max(
                0.0,
                min(congestion, 1.0)
            )

            vehicle["congestion"] = congestion

    # ==========================================
    # 5. CREATE V2V NETWORK
    # ==========================================

    def create_network(self):

        # Update congestion before building graph
        self.update_congestion()

        G = nx.Graph()

        # ----------------------------------
        # ADD VEHICLES AS NODES
        # ----------------------------------

        for vehicle_id, vehicle in self.vehicles.items():

            G.add_node(

                vehicle_id,

                pos=(
                    vehicle["x"],
                    vehicle["y"]
                ),

                speed=vehicle["speed"],

                congestion=vehicle["congestion"]
            )

        vehicle_ids = list(
            self.vehicles.keys()
        )

        # ----------------------------------
        # ESTABLISH WIRELESS V2V LINKS
        # ----------------------------------

        for i, u in enumerate(vehicle_ids):

            for v in vehicle_ids[i + 1:]:

                vehicle_u = self.vehicles[u]
                vehicle_v = self.vehicles[v]

                distance = self.distance_between(
                    vehicle_u,
                    vehicle_v
                )

                # Vehicles can communicate only
                # within the communication range.
                if distance <= self.communication_range:

                    congestion = (
                        vehicle_u["congestion"]
                        + vehicle_v["congestion"]
                    ) / 2

                    # Congestion-aware routing cost
                    cost = (
                        distance
                        * (1 + 3 * congestion)
                    )

                    G.add_edge(

                        u,
                        v,

                        distance=distance,

                        congestion=congestion,

                        cost=cost
                    )

        return G