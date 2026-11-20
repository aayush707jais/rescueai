"""
RESCUE-AI — Command Center Dashboard.

A Streamlit application that visualises the entire RESCUE-AI system:
incident location, ambulances, hospitals, routes, response plan,
and dynamic replanning.

Run:
    streamlit run dashboard.py
"""

from __future__ import annotations

import json
from datetime import datetime

import folium
import streamlit as st
from streamlit_folium import st_folium

from main_pipeline import RescueAIPipeline
from src.rescue_ai.resource_search_agent import AMBULANCES, HOSPITALS


# ================================================================
# PAGE CONFIG
# ================================================================

st.set_page_config(
    page_title="RESCUE-AI Command Center",
    page_icon="🚑",
    layout="wide",
)


# ================================================================
# STYLING
# ================================================================

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1200px; }
    .hero {
        background: linear-gradient(135deg, #b71c1c 0%, #e53935 55%, #ff7043 100%);
        color: white; padding: 1.4rem 1.6rem; border-radius: 16px;
        margin-bottom: 1rem; box-shadow: 0 6px 18px rgba(183,28,28,.25);
    }
    .hero h1 { margin: 0; font-size: 1.8rem; color: white; }
    .hero p  { margin: .3rem 0 0 0; opacity: .92; font-size: .9rem; }
    .metric-card {
        background: #1e1e2f; border-radius: 12px; padding: 1rem 1.2rem;
        text-align: center; border: 1px solid #333;
    }
    .metric-label { color: #aaa; font-size: .8rem; text-transform: uppercase; }
    .metric-value { color: white; font-size: 1.6rem; font-weight: 700; }
    .change-card {
        background: #2d1a1a; border: 1px solid #c62828; border-radius: 10px;
        padding: .8rem 1rem; margin-top: .5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ================================================================
# PIPELINE INSTANCE (cached)
# ================================================================

@st.cache_resource
def get_pipeline():
    return RescueAIPipeline()


pipeline = get_pipeline()


# ================================================================
# SESSION STATE
# ================================================================

ss = st.session_state
ss.setdefault("plan", None)
ss.setdefault("plan_history", [])
ss.setdefault("incident_processed", False)


# ================================================================
# NODE COORDINATES (for map display)
# ================================================================

NODE_COORDS = {
    "A": (28.6239, 77.1990),
    "B": (28.6189, 77.2090),
    "C": (28.6189, 77.2200),
    "D": (28.6089, 77.2090),
    "E": (28.6089, 77.2200),
    "F": (28.6239, 77.1890),
}


# ================================================================
# HERO HEADER
# ================================================================

st.markdown(
    """
    <div class="hero">
        <h1>🚑 RESCUE-AI Command Center</h1>
        <p>Autonomous Non-LLM Multi-Agent Emergency Response Coordination</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ================================================================
# SIDEBAR — CONTROLS
# ================================================================

with st.sidebar:
    st.header("🎮 Emergency Controls")

    st.subheader("New Incident")
    incident_location = st.selectbox(
        "Incident Location",
        list(NODE_COORDS.keys()),
        format_func=lambda n: f"{n} — ({NODE_COORDS[n][0]:.4f}, {NODE_COORDS[n][1]:.4f})",
        index=4,  # default to E
    )
    severity = st.selectbox("Severity", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], index=2)
    num_casualties = st.slider("Total Casualties", 1, 12, 4)
    num_severe = st.slider("Severe Casualties", 0, num_casualties, min(2, num_casualties))

    if st.button("🚨 Process Incident", type="primary", use_container_width=True):
        # Reset ambulances/hospitals for fresh run
        for a in AMBULANCES:
            if a["ambulance_id"] != "AMB-103":
                a["status"] = "available"
        for h in HOSPITALS:
            if h["hospital_id"] == "HOSP-101":
                h["available_beds"] = 5
            elif h["hospital_id"] == "HOSP-102":
                h["available_beds"] = 3
            elif h["hospital_id"] == "HOSP-103":
                h["available_beds"] = 0

        with st.spinner("Processing incident..."):
            result = pipeline.process_incident({
                "incident_location": incident_location,
                "severity": severity,
                "num_casualties": num_casualties,
                "num_severe": num_severe,
                "num_non_severe": num_casualties - num_severe,
            })
        ss.plan = result
        ss.plan_history = [result]
        ss.incident_processed = True
        st.rerun()

    if ss.incident_processed:
        st.divider()
        st.subheader("⚡ Dynamic Events")

        if st.button("🔧 Ambulance Breakdown", use_container_width=True):
            dispatched = ss.plan.get("dispatched_ambulances", [])
            if dispatched:
                failed_id = dispatched[0]["ambulance_id"]
                with st.spinner("Replanning..."):
                    updated = pipeline.handle_dynamic_event(
                        "AMBULANCE_UNAVAILABLE",
                        {"ambulance_id": failed_id},
                    )
                ss.plan = updated
                ss.plan_history.append(updated)
                st.rerun()

        if st.button("🚧 Road Blockage (B↔D)", use_container_width=True):
            with st.spinner("Replanning..."):
                updated = pipeline.handle_dynamic_event(
                    "ROAD_BLOCKED",
                    {"node_a": "B", "node_b": "D"},
                )
            ss.plan = updated
            ss.plan_history.append(updated)
            st.rerun()

        if st.button("🏥 Hospital Full", use_container_width=True):
            hosp = ss.plan.get("selected_hospital", {})
            hosp_id = hosp.get("hospital_id", "HOSP-101")
            with st.spinner("Replanning..."):
                updated = pipeline.handle_dynamic_event(
                    "HOSPITAL_FULL",
                    {"hospital_id": hosp_id},
                )
            ss.plan = updated
            ss.plan_history.append(updated)
            st.rerun()


# ================================================================
# MAIN CONTENT
# ================================================================

if not ss.incident_processed:
    st.info("👈 Use the sidebar to configure and process an incident.")
    st.stop()

plan = ss.plan

# ---- Metric Cards ----
c1, c2, c3, c4 = st.columns(4)
with c1:
    pri = plan.get("dispatch_priority", "N/A")
    color = {"CRITICAL": "#ef5350", "HIGH": "#ff7043", "MEDIUM": "#ffa726", "LOW": "#66bb6a"}.get(pri, "#aaa")
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Priority</div>'
        f'<div class="metric-value" style="color:{color}">{pri}</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Casualties</div>'
        f'<div class="metric-value">{plan.get("num_casualties", 0)}</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    n_amb = len(plan.get("dispatched_ambulances", []))
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Ambulances</div>'
        f'<div class="metric-value">{n_amb}</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    hosp_name = plan.get("selected_hospital", {}).get("name", "N/A")
    hosp_eta = plan.get("selected_hospital", {}).get("eta_minutes", "?")
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Hospital</div>'
        f'<div class="metric-value" style="font-size:1rem">{hosp_name}<br>'
        f'<span style="font-size:.8rem;color:#aaa">ETA: {hosp_eta} min</span></div></div>',
        unsafe_allow_html=True,
    )

st.write("")

# ---- Map and Details ----
map_col, detail_col = st.columns([3, 2])

with map_col:
    st.subheader("🗺️ Incident Map")

    inc_loc = plan.get("incident_location", "E")
    center = NODE_COORDS.get(inc_loc, (28.615, 77.21))
    m = folium.Map(location=center, zoom_start=14, tiles="CartoDB dark_matter")

    # Incident marker
    folium.Marker(
        center,
        tooltip=f"🔴 INCIDENT — {inc_loc}",
        icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
    ).add_to(m)

    # Ambulance markers
    dispatched_ids = {a["ambulance_id"] for a in plan.get("dispatched_ambulances", [])}
    for amb in AMBULANCES:
        loc = NODE_COORDS.get(amb["location"])
        if loc is None:
            continue
        if amb["ambulance_id"] in dispatched_ids:
            color, icon_name = "red", "ambulance"
            status = "DISPATCHED"
        elif amb["status"] == "available":
            color, icon_name = "green", "ambulance"
            status = "AVAILABLE"
        else:
            color, icon_name = "gray", "ambulance"
            status = amb["status"].upper()

        folium.Marker(
            loc,
            tooltip=f"🚑 {amb['ambulance_id']} — {status}",
            icon=folium.Icon(color=color, icon=icon_name, prefix="fa"),
        ).add_to(m)

    # Hospital markers
    for hosp in HOSPITALS:
        loc = NODE_COORDS.get(hosp["location"])
        if loc is None:
            continue
        beds = hosp["available_beds"]
        h_color = "blue" if beds > 0 else "gray"
        folium.Marker(
            loc,
            tooltip=f"🏥 {hosp['name']} — {beds} beds",
            icon=folium.Icon(color=h_color, icon="hospital-o", prefix="fa"),
        ).add_to(m)

    # Draw routes for dispatched ambulances
    for amb_route in plan.get("routes", {}).get("ambulance_routes", []):
        path_nodes = amb_route.get("route", [])
        coords = [NODE_COORDS[n] for n in path_nodes if n in NODE_COORDS]
        if len(coords) >= 2:
            folium.PolyLine(coords, color="#42a5f5", weight=4, opacity=0.8,
                            tooltip=f"Ambulance route: {amb_route.get('ambulance_id')}").add_to(m)

    st_folium(m, height=420, use_container_width=True)

with detail_col:
    st.subheader("📋 Response Plan")

    # Dispatched ambulances table
    st.markdown("**Dispatched Ambulances:**")
    for a in plan.get("dispatched_ambulances", []):
        st.markdown(
            f"- **{a['ambulance_id']}** ({a.get('ambulance_type', '?')}) "
            f"— ETA: {a.get('eta_minutes', '?')} min"
        )

    st.markdown(f"**Hospital:** {plan.get('selected_hospital', {}).get('name', 'N/A')}")
    st.markdown(f"**Decision Method:** `{plan.get('decision_method', 'unknown')}`")
    st.markdown(f"**Confidence:** {plan.get('confidence', 0):.0%}")

    st.markdown("**Response Actions:**")
    for action in plan.get("response_actions", []):
        st.markdown(f"- {action}")

    # Replan history
    history = plan.get("replan_history", [])
    if history:
        st.divider()
        st.markdown(f"**Replanning History** ({len(history)} event(s)):")
        for event in history:
            st.markdown(
                f'<div class="change-card">'
                f'⚡ <b>{event.get("event_type", "?")}</b> '
                f'(v{event.get("version", "?")})<br>'
                f'<small>{event.get("timestamp", "")}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Plan changes
    changes = plan.get("plan_changes")
    if changes:
        st.divider()
        st.markdown("**Latest Changes:**")
        for c in changes.get("changes", []):
            st.markdown(f"- {c}")


# ---- Resource Overview ----
st.divider()
st.subheader("📊 Resource Overview")

res_col1, res_col2 = st.columns(2)

with res_col1:
    st.markdown("**Ambulance Fleet**")
    amb_data = []
    for a in AMBULANCES:
        status = "🔴 Dispatched" if a["ambulance_id"] in dispatched_ids else (
            "🟢 Available" if a["status"] == "available" else "⚫ " + a["status"].title()
        )
        amb_data.append({
            "ID": a["ambulance_id"],
            "Type": "ALS" if "ALS" in a["capabilities"] else "BLS",
            "Location": a["location"],
            "Status": status,
        })
    st.dataframe(amb_data, use_container_width=True, hide_index=True)

with res_col2:
    st.markdown("**Hospitals**")
    hosp_data = []
    for h in HOSPITALS:
        hosp_data.append({
            "ID": h["hospital_id"],
            "Name": h["name"],
            "Location": h["location"],
            "Beds": h["available_beds"],
            "Capabilities": ", ".join(h["capabilities"]),
        })
    st.dataframe(hosp_data, use_container_width=True, hide_index=True)


# ---- JSON export ----
with st.expander("📄 Full Response Plan (JSON)"):
    st.json(plan)

# ---- Version ----
st.divider()
st.caption(
    f"RESCUE-AI v0.1 — Plan v{plan.get('version', 1)} — "
    f"Generated at {plan.get('created_at', 'N/A')} — "
    f"Synthetic road network — Prototype only, not for real dispatch."
)
