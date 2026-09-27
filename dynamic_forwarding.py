
import math
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

RESULTS = Path(__file__).parent / "results"

ROUTING_ALGORITHMS = {
    "Shortest Distance": shortest_distance_route,
    "Congestion Aware": congestion_aware_route,
    "Delivery Aware": delivery_aware_route
}

st.title("Congestion-Aware V2V Routing")
st.caption(
    "Interactive Multi-Hop Network Simulation "
    "in Dense Traffic"
)


# ==========================================
# 2. SIDEBAR CONTROLS
# ==========================================

st.sidebar.header("Simulation Controls")

num_vehicles = st.sidebar.slider(
    "Number of Vehicles",
    min_value=10,
    max_value=100,
    value=60,
    step=10
)

communication_range = st.sidebar.slider(
    "Communication Range (m)",
    min_value=50,
    max_value=300,
    value=180,
    step=10
)

algorithm = st.sidebar.selectbox(
    "Routing Algorithm",
    list(ROUTING_ALGORITHMS.keys())
)

time_step = st.sidebar.slider(
    "Movement per Step (seconds)",
    min_value=0.1,
    max_value=5.0,
    value=1.0,
    step=0.1
)

# A new configuration resets the animation.
configuration = (
    num_vehicles,
    communication_range
)

if (
    "configuration" not in st.session_state
    or st.session_state.configuration != configuration
):

    st.session_state.configuration = configuration

    st.session_state.simulation = VehicleSimulation(
        num_vehicles=num_vehicles,
        communication_range=communication_range,
        seed=42
    )

    st.session_state.step_count = 0


simulation = st.session_state.simulation


# ==========================================
# 3. SIMULATION BUTTONS
# ==========================================

st.header("Live V2V Network")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button(
        "Move Vehicles",
        use_container_width=True
    ):
        simulation.move_vehicles(time_step)
        st.session_state.step_count += 1

with col2:
    if st.button(
        "Move 10 Steps",
        use_container_width=True
    ):
        for _ in range(10):
            simulation.move_vehicles(time_step)

        st.session_state.step_count += 10

with col3:
    if st.button(
        "Reset Simulation",
        use_container_width=True
    ):
        st.session_state.simulation = VehicleSimulation(
            num_vehicles=num_vehicles,
            communication_range=communication_range,
            seed=42
        )

        st.session_state.step_count = 0
        st.rerun()


# ==========================================
# 4. CREATE CURRENT NETWORK
# ==========================================

G = simulation.create_network()

ordered = sorted(
    simulation.vehicles,
    key=lambda v: simulation.vehicles[v]["x"]
)

source = ordered[0]
destination = ordered[-1]

routing_function = ROUTING_ALGORITHMS[algorithm]

route = routing_function(
    G,
    source,
    destination
)


# ==========================================
# 5. NETWORK METRICS
# ==========================================

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
    "Simulation Steps",
    st.session_state.step_count
)

m4.metric(
    "Route Hops",
    len(route) - 1 if route else "No route"
)


# ==========================================
# 6. DRAW WIRELESS CONNECTIONS
# ==========================================

fig = go.Figure()

edge_x = []
edge_y = []

for u, v in G.edges():

    x1 = simulation.vehicles[u]["x"]
    y1 = simulation.vehicles[u]["y"]

    x2 = simulation.vehicles[v]["x"]
    y2 = simulation.vehicles[v]["y"]

    edge_x.extend([x1, x2, None])
    edge_y.extend([y1, y2, None])

fig.add_trace(
    go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(
            color="rgba(120,120,120,0.25)",
            width=1
        ),
        name="Wireless Links",
        hoverinfo="skip"
    )
)


# ==========================================
# 7. HIGHLIGHT SELECTED ROUTE
# ==========================================

if route:

    route_x = []
    route_y = []

    for u, v in zip(
        route[:-1],
        route[1:]
    ):

        route_x.extend([
            simulation.vehicles[u]["x"],
            simulation.vehicles[v]["x"],
            None
        ])

        route_y.extend([
            simulation.vehicles[u]["y"],
            simulation.vehicles[v]["y"],
            None
        ])

    fig.add_trace(
        go.Scatter(
            x=route_x,
            y=route_y,
            mode="lines",
            line=dict(
                color="#22c55e",
                width=5
            ),
            name="Selected Route",
            hoverinfo="skip"
        )
    )


# ==========================================
# 8. DRAW VEHICLES
# ==========================================

vehicle_ids = list(simulation.vehicles)

vehicle_x = [
    simulation.vehicles[v]["x"]
    for v in vehicle_ids
]

vehicle_y = [
    simulation.vehicles[v]["y"]
    for v in vehicle_ids
]

congestion = [
    simulation.vehicles[v]["congestion"]
    for v in vehicle_ids
]

vehicle_colors = []

for vehicle in vehicle_ids:

    if vehicle == source:
        vehicle_colors.append("#16a34a")

    elif vehicle == destination:
        vehicle_colors.append("#ef4444")

    else:
        vehicle_colors.append("#38bdf8")


hover_text = [
    (
        f"Vehicle {v}<br>"
        f"Speed: {simulation.vehicles[v]['speed']:.2f} m/s<br>"
        f"Congestion: "
        f"{simulation.vehicles[v]['congestion']:.2f}"
    )
    for v in vehicle_ids
]

fig.add_trace(
    go.Scatter(
        x=vehicle_x,
        y=vehicle_y,
        mode="markers+text",
        text=[
            str(v) for v in vehicle_ids
        ],
        textposition="top center",
        marker=dict(
            size=13,
            color=vehicle_colors,
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


# ==========================================
# 9. ROAD AND CHART SETTINGS
# ==========================================

fig.update_layout(
    title=f"{algorithm} - Current Network",
    xaxis=dict(
        title="Road Position (m)",
        range=[0, 1000]
    ),
    yaxis=dict(
        title="Road Lane",
        range=[0, 100]
    ),
    height=550,
    hovermode="closest",
    showlegend=True
)

for lane in simulation.lanes:

    fig.add_hline(
        y=lane,
        line_dash="dot",
        line_color="rgba(150,150,150,0.35)"
    )

st.plotly_chart(
    fig,
    use_container_width=True
)


# ==========================================
# 10. ROUTE INFORMATION
# ==========================================

st.subheader("Selected Route")

st.write("Source Vehicle:", source)
st.write("Destination Vehicle:", destination)

if route:

    st.success(
        "Route: "
        + " → ".join(
            str(v) for v in route
        )
    )

    st.write(
        "Number of Hops:",
        len(route) - 1
    )

    route_distance = sum(
        G[u][v]["distance"]
        for u, v in zip(
            route[:-1],
            route[1:]
        )
    )

    st.write(
        f"Total Route Distance: "
        f"{route_distance:.2f} m"
    )

else:
    st.error(
        "No connected route is currently available."
    )


# ==========================================
# 11. EXISTING PERFORMANCE RESULTS
# ==========================================

st.divider()

st.header("Performance Evaluation")

summary_file = RESULTS / "dynamic_summary.csv"

if summary_file.exists():

    df = pd.read_csv(summary_file)

    st.dataframe(
        df,
        use_container_width=True
    )

    c1, c2 = st.columns(2)

    with c1:

        pdr_fig = px.bar(
            df,
            x="algorithm",
            y="pdr",
            color="algorithm",
            title="Packet Delivery Ratio (%)"
        )

        st.plotly_chart(
            pdr_fig,
            use_container_width=True
        )

    with c2:

        delay_fig = px.bar(
            df,
            x="algorithm",
            y="delay_ms",
            color="algorithm",
            title="Average End-to-End Delay (ms)"
        )

        st.plotly_chart(
            delay_fig,
            use_container_width=True
        )

    c3, c4 = st.columns(2)

    with c3:

        breaks_fig = px.bar(
            df,
            x="algorithm",
            y="link_breaks",
            color="algorithm",
            title="Detected Link Failures"
        )

        st.plotly_chart(
            breaks_fig,
            use_container_width=True
        )

    with c4:

        recovery_fig = px.bar(
            df,
            x="algorithm",
            y="recovery_success_rate",
            color="algorithm",
            title="Route Recovery Success Rate (%)"
        )

        st.plotly_chart(
            recovery_fig,
            use_container_width=True
        )

else:

    st.warning(
        "Run dynamic_forwarding.py "
        "to generate performance results."
    )


# ==========================================
# 12. PROJECT INFORMATION
# ==========================================

st.divider()

st.caption(
    "Educational V2V network simulation. "
    "Vehicle mobility and congestion are modeled "
    "using simplified mathematical assumptions."
)