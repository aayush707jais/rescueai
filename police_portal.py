"""
RESCUE-AI — Police Dispatch & Traffic Enforcement Portal.

Police officer and traffic patrol interface:
- Live dispatch notifications for road traffic accidents
- Route navigation to accident site
- Accident perimeter security and traffic diversion management
- Real-time Road Blockage reporting (triggers automated detour replanning for ambulances)
- Road Cleared reporting to restore transit corridors

Run:
    streamlit run police_portal.py
"""

from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime
from src.rescue_ai.state_manager import SystemStateManager

try:
    st.set_page_config(
        page_title="RESCUE-AI Police Portal",
        page_icon="🚓",
        layout="wide",
    )
except Exception:
    pass

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1200px; }
    .hero-pol {
        background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #3949ab 100%);
        color: white; padding: 1.3rem 1.6rem; border-radius: 14px;
        margin-bottom: 1rem; box-shadow: 0 4px 15px rgba(26,35,126,.25);
    }
    .hero-pol h1 { margin: 0; font-size: 1.8rem; color: white; }
    .hero-pol p  { margin: .2rem 0 0 0; opacity: .92; font-size: .9rem; }
    .card {
        background: #1e1e2f; border: 1px solid #333; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: .8rem;
    }
    .pol-alert {
        background: #1a237e; border: 2px solid #5c6bc0; border-radius: 12px;
        padding: 1.2rem; margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

sm = SystemStateManager()

NODE_COORDS = {
    "A": (28.6239, 77.1990),
    "B": (28.6189, 77.2090),
    "C": (28.6189, 77.2200),
    "D": (28.6089, 77.2090),
    "E": (28.6089, 77.2200),
    "F": (28.6239, 77.1890),
}


def main():
    st.markdown(
        """
        <div class="hero-pol">
            <h1>🚓 RESCUE-AI Police Dispatch Terminal</h1>
            <p>Traffic Control, Scene Perimeter Security & Road Obstruction Enforcement</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    state = sm.load_state()
    police_units = state.get("police_units", [])

    with st.sidebar:
        st.subheader("Select Police Unit")
        unit_ids = [p["unit_id"] for p in police_units]
        selected_id = st.selectbox(
            "Patrol Unit",
            unit_ids,
            format_func=lambda uid: f"{uid} - {next((p['name'] for p in police_units if p['unit_id'] == uid), '')}",
        )
        st.divider()
        if st.button("🔄 Refresh Terminal", use_container_width=True):
            st.rerun()

    render_police_terminal(selected_id)


@st.fragment(run_every="2s")
def render_police_terminal(unit_id: str):
    state = sm.load_state()
    police = next((p for p in state.get("police_units", []) if p["unit_id"] == unit_id), None)
    if not police:
        st.error("Police unit not found.")
        return

    status = police.get("status", "patrol")
    incident = state.get("active_incident")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Unit</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:#fff">{unit_id}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Status</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:{"#4caf50" if status=="patrol" else "#ff9800"}">'
            f'{status.upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Stationed Node</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:#9fa8da">Junction {police["location"]}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Blocked Roads</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:#ef5350">{len(state.get("blocked_roads", []))}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    left_col, right_col = st.columns([3, 2])

    with left_col:
        if status in ("dispatched", "on_scene") and incident:
            st.markdown(
                f"""
                <div class="pol-alert">
                    <span style="font-size:1.2rem;font-weight:800;color:#90caf9;">
                        🚨 DISPATCH: SECURE ACCIDENT SITE ({incident.get('incident_id')})
                    </span>
                    <p style="margin:0.5rem 0 0 0;font-size:0.95rem;">
                        <b>Location:</b> Junction {incident.get('location')} &nbsp;|&nbsp;
                        <b>Severity:</b> {incident.get('severity')} &nbsp;|&nbsp;
                        <b>Casualties:</b> {incident.get('num_casualties')} ({incident.get('num_severe')} severe)<br>
                        <b>Mission Task:</b> {police.get('current_task')}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Map
            p_coords = NODE_COORDS.get(police["location"], (28.615, 77.21))
            inc_coords = NODE_COORDS.get(incident.get("location", "E"), (28.615, 77.21))

            m = folium.Map(location=p_coords, zoom_start=14, tiles="CartoDB dark_matter")
            folium.Marker(p_coords, tooltip=f"🚓 {police['name']}", icon=folium.Icon(color="blue", icon="shield", prefix="fa")).add_to(m)
            folium.Marker(inc_coords, tooltip="Accident Scene", icon=folium.Icon(color="red", icon="exclamation", prefix="fa")).add_to(m)

            route_nodes = police.get("route", [])
            coords = [NODE_COORDS[n] for n in route_nodes if n in NODE_COORDS]
            if len(coords) >= 2:
                folium.PolyLine(coords, color="#3f51b5", weight=5, opacity=0.9).add_to(m)

            st_folium(m, height=360, use_container_width=True)

            if status == "dispatched":
                if st.button("📍 Confirm Arrival on Scene (Perimeter Secured)", type="primary", use_container_width=True):
                    sm.update_police_status(unit_id, "on_scene", location=incident.get("location"))
                    st.success("Perimeter secured! Traffic control activated.")
                    st.rerun()
            elif status == "on_scene":
                if st.button("✅ Incident Cleared ➔ Return to Patrol", use_container_width=True):
                    sm.update_police_status(unit_id, "patrol")
                    st.success("Patrol resumed.")
                    st.rerun()

        else:
            st.info(f"🚓 **{police['name']} is on routine patrol.** Standing by for dispatch instructions.")
            st.caption(f"Current assignment: {police.get('current_task')}")

    with right_col:
        st.subheader("🚧 Road Blockage & Detour Controls")
        with st.container(border=True):
            st.markdown("**Report Road Hazard / Blockage**")
            st.caption(
                "Reporting a road blockage automatically instructs the route engine to mark the road "
                "segment impassable and **triggers instant replanning/rerouting for all ambulances**."
            )
            col_a, col_b = st.columns(2)
            with col_a:
                node_1 = st.selectbox("From Node", list(NODE_COORDS.keys()), index=1)
            with col_b:
                node_2 = st.selectbox("To Node", list(NODE_COORDS.keys()), index=3)

            if st.button("⛔ Report Segment Blocked", type="primary", use_container_width=True):
                if node_1 == node_2:
                    st.error("Please select two distinct nodes.")
                else:
                    sm.report_road_blockage(node_1, node_2)
                    st.toast(f"Road {node_1} ↔ {node_2} marked blocked! Detours broadcasted.")
                    st.rerun()

            st.divider()

            # Active blockages
            blocked = state.get("blocked_roads", [])
            st.markdown(f"**Active Road Blockages ({len(blocked)})**")
            if not blocked:
                st.caption("No road blockages reported.")
            else:
                for b_seg in blocked:
                    c_seg1, c_seg2 = st.columns([3, 2])
                    with c_seg1:
                        st.markdown(f"⛔ **Segment {b_seg}**")
                    with c_seg2:
                        nodes = b_seg.split("-")
                        if st.button("Clear Blockage", key=f"clr_{b_seg}"):
                            sm.report_road_cleared(nodes[0], nodes[1])
                            st.toast(f"Segment {b_seg} reopened!")
                            st.rerun()


if __name__ == "__main__":
    main()
