
import networkx as nx
import math


# ==========================================
# 1. SHORTEST-DISTANCE ROUTING
# ==========================================

def shortest_distance_route(G, source, destination):
    """
    Find the shortest route based on
    the physical distance between vehicles.
    """

    try:
        route = nx.shortest_path(
            G,
            source=source,
            target=destination,
            weight="distance"
        )

        return route

    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ==========================================
# 2. CONGESTION-AWARE ROUTING
# ==========================================

def congestion_aware_route(G, source, destination):
    """
    Find a route using both distance
    and congestion information.
    """

    # Calculate congestion-aware link costs
    for u, v, data in G.edges(data=True):

        distance = data["distance"]
        congestion = data["congestion"]

        # Congestion-aware routing formula
        cost = distance * (1 + 3 * congestion)

        data["cost"] = cost

    try:
        route = nx.shortest_path(
            G,
            source=source,
            target=destination,
            weight="cost"
        )

        return route

    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ==========================================
# 3. DELIVERY-AWARE ROUTING
# ==========================================

def delivery_aware_route(G, source, destination):
    """
    Find the route with the highest modeled
    end-to-end packet delivery probability.

    Uses the same packet-loss model as packet.py.
    """

    for u, v, data in G.edges(data=True):

        congestion = data["congestion"]

        # Estimate packet-loss probability
        loss_probability = min(
            0.02 + 0.25 * congestion,
            0.95
        )

        # Probability of successful delivery
        delivery_probability = (
            1.0 - loss_probability
        )

        # Convert probability into additive cost
        delivery_cost = -math.log(
            delivery_probability
        )

        data["delivery_cost"] = delivery_cost

    try:
        route = nx.shortest_path(
            G,
            source=source,
            target=destination,
            weight="delivery_cost"
        )

        return route

    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


# ==========================================
# 4. CALCULATE ROUTE COST
# ==========================================

def calculate_route_cost(G, route):
    """
    Calculate the total congestion-aware
    cost of a selected route.
    """

    if route is None:
        return float("inf")

    if len(route) < 2:
        return 0.0

    total_cost = 0.0

    for i in range(len(route) - 1):

        u = route[i]
        v = route[i + 1]

        distance = G[u][v]["distance"]
        congestion = G[u][v]["congestion"]

        cost = distance * (1 + 3 * congestion)

        total_cost += cost

    return total_cost