
import random
from pathlib import Path

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from simulation import VehicleSimulation
from routing import (
    shortest_distance_route,
    congestion_aware_route,
    delivery_aware_route
)


# ==========================================
# 1. DASHBOARD CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Congestion-Aware V2V",
    page_icon="🚗",
    layout="wide"
)

RESULTS_DIR = Path(__file__).parent / "results"

ALGORITHMS = {
    "Shortest Distance": shortest_distance_route,
    "Congestion Aware": congestion_aware_route,
    "Delivery Aware": delivery_aware_route
}

st.title("Congestion-Aware V2V Routing")

st.caption(
    "Live Multi-Hop Network Simulation "
    "in Dense Traffic"
)


# ==========================================
# 2. SIMULATION SETTINGS
# ==========================================

st.sidebar.header("Simulation Controls")

num_vehicles = st.sidebar.slider(
    "Number of Vehicles",
    10, 100, 60, 10
)

communication_range = st.sidebar.slider(
    "Communication Range (m)",
    50, 300, 120, 10
)

algorithm = st.sidebar.selectbox(
    "Routing Algorithm",
    list(ALGORITHMS.keys())
)

movement_step = st.sidebar.slider(
    "Vehicle Movement per Frame (seconds)",
    0.1, 2.0, 0.5, 0.1
)


# ==========================================
# 3. FIND MULTI-HOP VEHICLE PAIR
# ==========================================

def find_multihop_pair(G, minimum_hops=3):

    """
    Find a connected source-destination pair
    with at least three shortest-path hops.

    If no such pair exists, return the pair
    with the longest available shortest path.
    """

    best_pair = None
    best_hops = -1

    for source, paths in nx.all_pairs_shortest_path(G):

        for destination, path in paths.items():

            if source == destination:
                continue

            hops = len(path) - 1

            if hops >= minimum_hops:
                return source, destination

            if hops > best_hops:

                best_pair = (
                    source,
                    destination
                )

                best_hops = hops

    return best_pair


# ==========================================
# 4. INITIALIZE SIMULATION
# ==========================================

def reset_simulation():

    simulation = VehicleSimulation(
        num_vehicles=num_vehicles,
        communication_range=communication_range,
        seed=42
    )

    st.session_state.simulation = simulation

    G = simulation.create_network()

    pair = find_multihop_pair(
        G,
        minimum_hops=3
    )

    if pair is None:

        ids = sorted(simulation.vehicles)

        pair = (
            ids[0],
            ids[-1]
        )

    st.session_state.auto_pair = pair

    st.session_state.source = pair[0]
    st.session_state.destination = pair[1]

    st.session_state.running = False
    st.session_state.frame = 0

    # Packet state

    st.session_state.packet_active = False
    st.session_state.packet_position = pair[0]

    st.session_state.packet_history = [
        pair[0]
    ]

    st.session_state.planned_next_hop = None
    st.session_state.packet_hops = 0

    st.session_state.packet_algorithm = None

    # Statistics

    st.session_state.sent = 0
    st.session_state.delivered = 0
    st.session_state.dropped = 0

    st.session_state.link_breaks = 0
    st.session_state.recoveries = 0
    st.session_state.failed_recoveries = 0

    st.session_state.packet_rng = (
        random.Random(123)
    )

    st.session_state.message = (
        "Simulation initialized."
    )


configuration = (
    num_vehicles,
    communication_range
)

if (
    "simulation" not in st.session_state
    or st.session_state.get("configuration")
    != configuration
):

    st.session_state.configuration = configuration

    reset_simulation()


# ==========================================
# 5. SOURCE AND DESTINATION SELECTION
# ==========================================

st.sidebar.divider()

st.sidebar.header("Vehicle Selection")

selection_mode = st.sidebar.radio(
    "Selection Mode",
    [
        "Automatic Multi-Hop",
        "Manual"
    ]
)

simulation = st.session_state.simulation

vehicle_ids = sorted(
    simulation.vehicles.keys()
)

if selection_mode == "Automatic Multi-Hop":

    if st.sidebar.button(
        "Find Multi-Hop Pair"
    ):

        G = simulation.create_network()

        pair = find_multihop_pair(
            G,
            minimum_hops=3
        )

        if pair is not None:

            st.session_state.auto_pair = pair

    selected_source, selected_destination = (
        st.session_state.auto_pair
    )

    st.sidebar.write(
        f"Source: {selected_source}"
    )

    st.sidebar.write(
        f"Destination: {selected_destination}"
    )

else:

    selected_source = st.sidebar.selectbox(
        "Source Vehicle",
        vehicle_ids,
        index=vehicle_ids.index(
            st.session_state.source
        )
    )

    destination_options = [
        v for v in vehicle_ids
        if v != selected_source
    ]

    selected_destination = st.sidebar.selectbox(
        "Destination Vehicle",
        destination_options,
        index=(
            destination_options.index(
                st.session_state.destination
            )
            if st.session_state.destination
            in destination_options
            else 0
        )
    )


# Update source and destination only
# when the selection actually changes.

new_pair = (
    selected_source,
    selected_destination
)

old_pair = (
    st.session_state.source,
    st.session_state.destination
)

if new_pair != old_pair:

    st.session_state.source = selected_source
    st.session_state.destination = selected_destination

    st.session_state.packet_active = False

    st.session_state.packet_position = (
        selected_source
    )

    st.session_state.packet_history = [
        selected_source
    ]

    st.session_state.planned_next_hop = None
    st.session_state.packet_hops = 0

    st.session_state.message = (
        "Source and destination updated."
    )


# ==========================================
# 6. PACKET ROUTING FUNCTION
# ==========================================

def calculate_route(
    G,
    source,
    destination,
    routing_name
):

    if source == destination:
        return [source]

    route_function = ALGORITHMS[
        routing_name
    ]

    try:

        route = route_function(
            G,
            source,
            destination
        )

    except (
        nx.NetworkXNoPath,
        nx.NodeNotFound
    ):

        return None

    if not route:
        return None

    # Validate the returned route.

    if (
        route[0] != source
        or route[-1] != destination
    ):
        return None

    if any(
        not G.has_edge(u, v)
        for u, v in zip(
            route[:-1],
            route[1:]
        )
    ):
        return None

    return route


# ==========================================
# 7. ANIMATION CONTROLS
# ==========================================

st.header("Animation Controls")

c1, c2, c3, c4 = st.columns(4)

with c1:

    if st.button(
        "▶ Play",
        use_container_width=True
    ):

        st.session_state.running = True


with c2:

    if st.button(
        "⏸ Pause",
        use_container_width=True
    ):

        st.session_state.running = False


with c3:

    if st.button(
        "↻ Reset",
        use_container_width=True
    ):

        reset_simulation()

        st.rerun()


with c4:

    if st.button(
        "📦 Send Packet",
        use_container_width=True,
        disabled=st.session_state.packet_active
    ):

        st.session_state.sent += 1

        st.session_state.packet_active = True

        st.session_state.packet_position = (
            st.session_state.source
        )

        st.session_state.packet_history = [
            st.session_state.source
        ]

        st.session_state.packet_hops = 0

        # Keep the same algorithm throughout
        # this packet's journey.

        st.session_state.packet_algorithm = (
            algorithm
        )

        # Plan the first hop before movement.

        G = simulation.create_network()

        route = calculate_route(
            G,
            st.session_state.source,
            st.session_state.destination,
            algorithm
        )

        if route and len(route) >= 2:

            st.session_state.planned_next_hop = (
                route[1]
            )

            st.session_state.message = (
                "Packet created. Press Play."
            )

        else:

            st.session_state.packet_active = False

            st.session_state.planned_next_hop = None

            st.session_state.dropped += 1

            st.session_state.message = (
                "Packet dropped: no route available."
            )


# ==========================================
# 8. PACKET FORWARDING
# ==========================================

def advance_packet(G):

    if not st.session_state.packet_active:
        return

    current = (
        st.session_state.packet_position
    )

    destination = (
        st.session_state.destination
    )

    routing_name = (
        st.session_state.packet_algorithm
    )

    next_hop = (
        st.session_state.planned_next_hop
    )

    # --------------------------------------
    # SELECT NEXT HOP
    # --------------------------------------

    if next_hop is None:

        route = calculate_route(
            G,
            current,
            destination,
            routing_name
        )

        if not route or len(route) < 2:

            st.session_state.packet_active = False

            st.session_state.dropped += 1

            st.session_state.message = (
                "Packet dropped: no available route."
            )

            return

        next_hop = route[1]

    # --------------------------------------
    # LINK-BREAK DETECTION
    # --------------------------------------

    if not G.has_edge(
        current,
        next_hop
    ):

        st.session_state.link_breaks += 1

        alternative = calculate_route(
            G,
            current,
            destination,
            routing_name
        )

        if (
            alternative is None
            or len(alternative) < 2
        ):

            st.session_state.packet_active = False

            st.session_state.dropped += 1

            st.session_state.failed_recoveries += 1

            st.session_state.planned_next_hop = None

            st.session_state.message = (
                f"Link {current} → {next_hop} broken. "
                "Route recovery failed."
            )

            return

        st.session_state.recoveries += 1

        st.session_state.planned_next_hop = (
            alternative[1]
        )

        st.session_state.message = (
            f"Link {current} → {next_hop} broken. "
            f"Alternative next hop: "
            f"{alternative[1]}"
        )

        return

    # --------------------------------------
    # SIMULATE PACKET TRANSMISSION
    # --------------------------------------

    congestion = G[current][next_hop][
        "congestion"
    ]

    loss_probability = min(
        0.02 + 0.25 * congestion,
        0.95
    )

    st.session_state.packet_hops += 1

    if (
        st.session_state.packet_rng.random()
        < loss_probability
    ):

        st.session_state.packet_active = False

        st.session_state.dropped += 1

        st.session_state.planned_next_hop = None

        st.session_state.message = (
            f"Packet lost: {current} → {next_hop}"
        )

        return

    # Successful forwarding

    st.session_state.packet_position = (
        next_hop
    )

    st.session_state.packet_history.append(
        next_hop
    )

    # --------------------------------------
    # DESTINATION REACHED
    # --------------------------------------

    if next_hop == destination:

        st.session_state.packet_active = False

        st.session_state.delivered += 1

        st.session_state.planned_next_hop = None

        st.session_state.message = (
            "Packet successfully delivered!"
        )

        return

    # --------------------------------------
    # PLAN NEXT HOP BEFORE MOVEMENT
    # --------------------------------------

    new_route = calculate_route(
        G,
        next_hop,
        destination,
        routing_name
    )

    st.session_state.planned_next_hop = (
        new_route[1]
        if new_route and len(new_route) >= 2
        else None
    )

    st.session_state.message = (
        f"Packet forwarded: "
        f"{current} → {next_hop}"
    )


# ==========================================
# 9. LIVE NETWORK ANIMATION
# ==========================================

@st.fragment(run_every=1)
def live_network():

    simulation = (
        st.session_state.simulation
    )

    # Move vehicles

    if st.session_state.running:

        simulation.move_vehicles(
            movement_step
        )

        st.session_state.frame += 1

    G = simulation.create_network()

    source = st.session_state.source

    destination = (
        st.session_state.destination
    )

    # Calculate selected route

    route = calculate_route(
        G,
        source,
        destination,
        algorithm
    )

    # Forward packet

    if (
        st.session_state.running
        and st.session_state.packet_active
    ):

        advance_packet(G)

    # ======================================
    # NETWORK STATISTICS
    # ======================================

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Vehicles",
        G.number_of_nodes()
    )

    m2.metric(
        "Wireless Links",
        G.number_of_edges()
    )

    m3.metric(
        "Animation Frames",
        st.session_state.frame
    )

    m4.metric(
        "Selected Route Hops",
        len(route) - 1
        if route else "No Route"
    )

    # ======================================
    # CREATE NETWORK GRAPH
    # ======================================

    fig = go.Figure()

    # --------------------------------------
    # CONGESTION-COLORED LINKS
    # --------------------------------------

    congestion_levels = {
        "Low": {
            "x": [],
            "y": [],
            "color": "#22c55e"
        },
        "Medium": {
            "x": [],
            "y": [],
            "color": "#eab308"
        },
        "High": {
            "x": [],
            "y": [],
            "color": "#ef4444"
        }
    }

    for u, v, data in G.edges(
        data=True
    ):

        congestion = data[
            "congestion"
        ]

        if congestion < 0.35:

            level = "Low"

        elif congestion < 0.70:

            level = "Medium"

        else:

            level = "High"

        p1 = simulation.vehicles[u]
        p2 = simulation.vehicles[v]

        congestion_levels[level]["x"].extend(
            [
                p1["x"],
                p2["x"],
                None
            ]
        )

        congestion_levels[level]["y"].extend(
            [
                p1["y"],
                p2["y"],
                None
            ]
        )

    for level, data in congestion_levels.items():

        fig.add_trace(
            go.Scatter(
                x=data["x"],
                y=data["y"],
                mode="lines",
                line=dict(
                    color=data["color"],
                    width=1
                ),
                opacity=0.30,
                name=f"{level} Congestion",
                hoverinfo="skip"
            )
        )

    # --------------------------------------
    # HIGHLIGHT SELECTED ROUTE
    # --------------------------------------

    if route:

        route_x = []
        route_y = []

        for u, v in zip(
            route[:-1],
            route[1:]
        ):

            route_x.extend(
                [
                    simulation.vehicles[u]["x"],
                    simulation.vehicles[v]["x"],
                    None
                ]
            )

            route_y.extend(
                [
                    simulation.vehicles[u]["y"],
                    simulation.vehicles[v]["y"],
                    None
                ]
            )

        fig.add_trace(
            go.Scatter(
                x=route_x,
                y=route_y,
                mode="lines",
                line=dict(
                    color="#00ff88",
                    width=5
                ),
                name="Selected Route",
                hoverinfo="skip"
            )
        )

    # --------------------------------------
    # DRAW VEHICLES
    # --------------------------------------

    vehicle_ids = list(
        simulation.vehicles.keys()
    )

    vehicle_x = [
        simulation.vehicles[v]["x"]
        for v in vehicle_ids
    ]

    vehicle_y = [
        simulation.vehicles[v]["y"]
        for v in vehicle_ids
    ]

    colors = []

    for vehicle in vehicle_ids:

        if vehicle == source:

            colors.append("#16a34a")

        elif vehicle == destination:

            colors.append("#ef4444")

        else:

            colors.append("#38bdf8")

    hover_text = []

    for vehicle in vehicle_ids:

        data = simulation.vehicles[
            vehicle
        ]

        hover_text.append(
            f"Vehicle: {vehicle}<br>"
            f"Speed: {data['speed']:.2f} m/s<br>"
            f"Congestion: "
            f"{data['congestion']:.2f}"
        )

    fig.add_trace(
        go.Scatter(
            x=vehicle_x,
            y=vehicle_y,
            mode="markers+text",
            text=[
                str(v)
                for v in vehicle_ids
            ],
            textposition="top center",
            marker=dict(
                size=13,
                color=colors,
                line=dict(
                    color="white",
                    width=1
                )
            ),
            hovertext=hover_text,
            hoverinfo="text",
            name="Vehicles"
        )
    )

    # --------------------------------------
    # HIGHLIGHT CURRENT PACKET
    # --------------------------------------

    if st.session_state.packet_active:

        packet_vehicle = (
            st.session_state.packet_position
        )

        packet_data = simulation.vehicles[
            packet_vehicle
        ]

        fig.add_trace(
            go.Scatter(
                x=[
                    packet_data["x"]
                ],
                y=[
                    packet_data["y"]
                ],
                mode="markers",
                marker=dict(
                    size=25,
                    color="#facc15",
                    symbol="star",
                    line=dict(
                        color="white",
                        width=2
                    )
                ),
                name="Current Packet"
            )
        )

    # --------------------------------------
    # DRAW ROAD LANES
    # --------------------------------------

    for lane in simulation.lanes:

        fig.add_hline(
            y=lane,
            line_dash="dot",
            line_color="rgba(150,150,150,0.35)"
        )

    fig.update_layout(
        title=(
            f"{algorithm} - Live V2V Network"
        ),
        xaxis=dict(
            title="Road Position (m)",
            range=[0, 1000]
        ),
        yaxis=dict(
            title="Road Lane",
            range=[0, 100]
        ),
        height=600,
        hovermode="closest",
        showlegend=True
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    # ======================================
    # ROUTE INFORMATION
    # ======================================

    st.subheader(
        "Current Route Information"
    )

    st.write(
        f"Source: {source}"
    )

    st.write(
        f"Destination: {destination}"
    )

    if route:

        st.success(
            "Selected Route: "
            + " → ".join(
                map(str, route)
            )
        )

        st.write(
            f"Number of Hops: "
            f"{len(route) - 1}"
        )

        distance = sum(
            G[u][v]["distance"]
            for u, v in zip(
                route[:-1],
                route[1:]
            )
        )

        st.write(
            f"Total Route Distance: "
            f"{distance:.2f} m"
        )

    else:

        st.warning(
            "No connected route available."
        )

    # ======================================
    # PACKET STATUS
    # ======================================

    st.info(
        st.session_state.message
    )

    st.write(
        "Packet Forwarding Path:",
        " → ".join(
            map(
                str,
                st.session_state.packet_history
            )
        )
    )

    # ======================================
    # LIVE PACKET STATISTICS
    # ======================================

    st.subheader(
        "Live Packet Statistics"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Packets Sent",
        st.session_state.sent
    )

    c2.metric(
        "Packets Delivered",
        st.session_state.delivered
    )

    c3.metric(
        "Packets Dropped",
        st.session_state.dropped
    )

    c4.metric(
        "Link Breaks",
        st.session_state.link_breaks
    )

    c5, c6, c7 = st.columns(3)

    c5.metric(
        "Recovery Routes Found",
        st.session_state.recoveries
    )

    c6.metric(
        "Failed Recoveries",
        st.session_state.failed_recoveries
    )

    c7.metric(
        "Current Packet Hops",
        st.session_state.packet_hops
    )

    if st.session_state.sent > 0:

        live_pdr = (
            100
            * st.session_state.delivered
            / st.session_state.sent
        )

        st.metric(
            "Live Packet Delivery Ratio",
            f"{live_pdr:.2f}%"
        )

    st.caption(
        "Live statistics are separate from "
        "the saved experiment results."
    )


live_network()


# ==========================================
# 10. PERFORMANCE EVALUATION
# ==========================================

st.divider()

st.header(
    "Routing Algorithm Performance"
)

summary_file = (
    RESULTS_DIR / "dynamic_summary.csv"
)

if summary_file.exists():

    df = pd.read_csv(
        summary_file
    )

    st.dataframe(
        df,
        use_container_width=True
    )

    left, right = st.columns(2)

    with left:

        fig = px.bar(
            df,
            x="algorithm",
            y="pdr",
            color="algorithm",
            title="Packet Delivery Ratio (%)"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right:

        fig = px.bar(
            df,
            x="algorithm",
            y="delay_ms",
            color="algorithm",
            title="Average End-to-End Delay"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    left2, right2 = st.columns(2)

    with left2:

        fig = px.bar(
            df,
            x="algorithm",
            y="link_breaks",
            color="algorithm",
            title="Link Failures"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right2:

        fig = px.bar(
            df,
            x="algorithm",
            y="recovery_success_rate",
            color="algorithm",
            title="Route Recovery Success Rate"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

else:

    st.warning(
        "Run dynamic_forwarding.py "
        "to generate experiment results."
    )


# ==========================================
# 11. STAGE 15 EXPERIMENT ANALYSIS
# ==========================================

st.divider()
st.header("Stage 15 — Automated Experiment Analysis")
st.caption(
    "Compare the saved multi-trial experiments. These results are "
    "separate from the live animation and earlier dynamic experiment."
)

stage15_file = RESULTS_DIR / "stage15_results.csv"
packet_log_file = RESULTS_DIR / "stage15_packet_logs.csv"

if stage15_file.exists():
    try:
        stage15 = pd.read_csv(stage15_file)
        required = {
            "vehicles", "trial", "algorithm", "sent", "delivered",
            "pdr_pct", "average_delivered_delay_ms"
        }
        missing = required - set(stage15.columns)
        if missing:
            st.error("Stage 15 results are missing columns: " + ", ".join(sorted(missing)))
        elif stage15.empty:
            st.warning("Stage 15 results file is empty. Run stage15_experiment.py.")
        else:
            stage15["vehicles"] = pd.to_numeric(stage15["vehicles"], errors="coerce")
            stage15["trial"] = pd.to_numeric(stage15["trial"], errors="coerce")
            for column in ["sent", "delivered", "pdr_pct", "average_delivered_delay_ms"]:
                stage15[column] = pd.to_numeric(stage15[column], errors="coerce")
            stage15 = stage15.dropna(subset=["vehicles", "trial", "sent", "delivered"])
            vehicle_choices = sorted(stage15["vehicles"].astype(int).unique().tolist())
            selected_counts = st.multiselect(
                "Vehicle counts to compare", vehicle_choices,
                default=vehicle_choices, key="stage15_vehicle_filter"
            )
            filtered = stage15[stage15["vehicles"].isin(selected_counts)].copy()

            if filtered.empty:
                st.info("Select at least one vehicle count to view experiment results.")
            else:
                # Overall PDR is total delivered / total sent. Mean delay is
                # weighted by delivered packets; dropped packets have no
                # completed end-to-end delay in this experiment.
                filtered["delay_weight"] = (
                    filtered["average_delivered_delay_ms"].fillna(0)
                    * filtered["delivered"]
                )
                grouped = filtered.groupby("algorithm", as_index=False).agg(
                    sent=("sent", "sum"),
                    delivered=("delivered", "sum"),
                    delay_weight=("delay_weight", "sum"),
                    trials=("trial", "count")
                )
                grouped["PDR (%)"] = (
                    100 * grouped["delivered"] / grouped["sent"].replace(0, float("nan"))
                )
                grouped["Average delivered delay (ms)"] = (
                    grouped["delay_weight"]
                    / grouped["delivered"].replace(0, float("nan"))
                )
                st.subheader("Combined results for selected vehicle counts")
                st.dataframe(
                    grouped[["algorithm", "trials", "sent", "delivered",
                             "PDR (%)", "Average delivered delay (ms)"]]
                    .rename(columns={"algorithm": "Algorithm", "trials": "Trial rows",
                                     "sent": "Packets sent", "delivered": "Delivered"})
                    .round(2),
                    use_container_width=True, hide_index=True
                )
                left_stage, right_stage = st.columns(2)
                with left_stage:
                    fig_pdr = px.bar(
                        grouped, x="algorithm", y="PDR (%)", color="algorithm",
                        title="Packet Delivery Ratio — Selected Vehicle Counts",
                        labels={"algorithm": "Routing algorithm"},
                        range_y=[0, 100]
                    )
                    fig_pdr.update_layout(showlegend=False)
                    st.plotly_chart(fig_pdr, use_container_width=True)
                with right_stage:
                    delay_data = grouped.dropna(subset=["Average delivered delay (ms)"])
                    if delay_data.empty:
                        st.info("No delivered packets to calculate delay.")
                    else:
                        fig_delay = px.bar(
                            delay_data, x="algorithm", y="Average delivered delay (ms)",
                            color="algorithm", title="Delay of Delivered Packets",
                            labels={"algorithm": "Routing algorithm"}
                        )
                        fig_delay.update_layout(showlegend=False)
                        st.plotly_chart(fig_delay, use_container_width=True)

                by_count = filtered.groupby(["vehicles", "algorithm"], as_index=False).agg(
                    sent=("sent", "sum"), delivered=("delivered", "sum"),
                    delay_weight=("delay_weight", "sum")
                )
                by_count["PDR (%)"] = (
                    100 * by_count["delivered"] / by_count["sent"].replace(0, float("nan"))
                )
                by_count["Average delay (ms)"] = (
                    by_count["delay_weight"] / by_count["delivered"].replace(0, float("nan"))
                )
                st.subheader("Effect of Traffic Density")
                left_density, right_density = st.columns(2)
                with left_density:
                    fig = px.line(
                        by_count, x="vehicles", y="PDR (%)", color="algorithm",
                        markers=True, title="PDR by Number of Vehicles",
                        labels={"vehicles": "Vehicles", "algorithm": "Routing algorithm"}
                    )
                    fig.update_yaxes(range=[0, 100])
                    st.plotly_chart(fig, use_container_width=True)
                with right_density:
                    valid_delay = by_count.dropna(subset=["Average delay (ms)"])
                    if not valid_delay.empty:
                        fig = px.line(
                            valid_delay, x="vehicles", y="Average delay (ms)",
                            color="algorithm", markers=True,
                            title="Delivered-Packet Delay by Number of Vehicles",
                            labels={"vehicles": "Vehicles", "algorithm": "Routing algorithm"}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No delivered packets in the selected scenarios.")

                with st.expander("View individual trial results"):
                    st.dataframe(
                        filtered.drop(columns=["delay_weight"]).sort_values(
                            ["vehicles", "trial", "algorithm"]
                        ), use_container_width=True, hide_index=True
                    )
                st.download_button(
                    "Download filtered Stage 15 results (CSV)",
                    data=filtered.drop(columns=["delay_weight"]).to_csv(index=False).encode("utf-8"),
                    file_name="stage15_filtered_results.csv", mime="text/csv"
                )
                if packet_log_file.exists():
                    with st.expander("View packet-level logs"):
                        packet_logs = pd.read_csv(packet_log_file)
                        if "vehicles" in packet_logs.columns:
                            packet_logs = packet_logs[
                                packet_logs["vehicles"].isin(selected_counts)
                            ]
                        st.dataframe(packet_logs, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Download packet logs (CSV)",
                            data=packet_logs.to_csv(index=False).encode("utf-8"),
                            file_name="stage15_packet_logs_filtered.csv", mime="text/csv"
                        )
                st.caption(
                    "PDR = total delivered / total sent for the selected trials. "
                    "Delay averages include delivered packets only. "
                    "Scenarios favor connected multi-hop pairs when available."
                )
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"Could not read Stage 15 results: {exc}")
else:
    st.warning(
        "Stage 15 results not found. Run `python stage15_experiment.py` "
        "from your project folder, then refresh this dashboard."
    )


# ==========================================
# 12. PROJECT INFORMATION
# ==========================================

st.divider()

st.header("About the Project")

st.write(
    "Congestion-Aware Route Selection for "
    "V2V Multi-Hop Networks in Dense Traffic"
)

st.write(
    "This project demonstrates vehicle mobility, "
    "dynamic wireless connections, congestion-aware "
    "routing, packet forwarding, link-break detection "
    "and alternative-route discovery."
)

st.caption(
    "Educational Python simulation. "
    "The network uses simplified mobility, "
    "congestion and packet-loss models."
)