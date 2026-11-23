"""
RESCUE-AI — Fire & Rescue / Heavy Extrication Portal.

Fire brigade and technical rescue squad interface:
- Dispatch alerts for severe vehicular entrapment, fires, and hazardous fuel spills
- Route navigation to accident site
- Extrication & hydraulic rescue progression reporting
- Hazardous material mitigation status

Run:
    streamlit run fire_portal.py
"""

from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime
from src.rescue_ai.state_manager import SystemStateManager

try:
    st.set_page_config(
        page_title="RESCUE-AI Fire & Rescue MDT",
        page_icon="🚒",
        layout="wide",
    )
except Exception:
    pass

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1200px; }
    .hero-fire {
        background: linear-gradient(135deg, #e65100 0%, #f57c00 50%, #ff9800 100%);
        color: white; padding: 1.3rem 1.6rem; border-radius: 14px;
        margin-bottom: 1rem; box-shadow: 0 4px 15px rgba(230,81,0,.25);
    }
    .hero-fire h1 { margin: 0; font-size: 1.8rem; color: white; }
    .hero-fire p  { margin: .2rem 0 0 0; opacity: .92; font-size: .9rem; }
    .card {
        background: #1e1e2f; border: 1px solid #333; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: .8rem;
    }
    .fire-alert {
        background: #3e2723; border: 2px solid #ff9800; border-radius: 12px;
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
        <div class="hero-fire">
            <h1>🚒 RESCUE-AI Fire & Rescue Mobile Terminal</h1>
            <p>Vehicle Extrication, Heavy Rescue & Hazmat Containment Squad</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    state = sm.load_state()
    fire_units = state.get("fire_units", [])

    with st.sidebar:
        st.subheader("Select Fire Unit")
        unit_ids = [f["unit_id"] for f in fire_units]
        selected_id = st.selectbox(
            "Squad Unit",
            unit_ids,
            format_func=lambda uid: f"{uid} - {next((f['name'] for f in fire_units if f['unit_id'] == uid), '')}",
        )
        st.divider()
        if st.button("🔄 Refresh Terminal", use_container_width=True):
            st.rerun()

    render_fire_terminal(selected_id)


@st.fragment(run_every="2s")
def render_fire_terminal(unit_id: str):
    state = sm.load_state()
    fire = next((f for f in state.get("fire_units", []) if f["unit_id"] == unit_id), None)
    if not fire:
        st.error("Fire squad not found.")
        return

    status = fire.get("status", "available")
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
            f'<div style="font-size:1.4rem;font-weight:700;color:{"#4caf50" if status=="available" else "#ff9800"}">'
            f'{status.upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Station</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:#ffb74d">Junction {fire["location"]}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Capabilities</div>'
            f'<div style="font-size:1rem;font-weight:700;color:#81c784">{", ".join(fire.get("capabilities", []))}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    left_col, right_col = st.columns([3, 2])

    with left_col:
        if status in ("dispatched", "on_scene") and incident:
            st.markdown(
                f"""
                <div class="fire-alert">
                    <span style="font-size:1.2rem;font-weight:800;color:#ffb74d;">
                        🚒 FIRE/RESCUE DISPATCH: EXTRICATION OPERATION ({incident.get('incident_id')})
                    </span>
                    <p style="margin:0.5rem 0 0 0;font-size:0.95rem;">
                        <b>Accident Scene:</b> Junction {incident.get('location')} &nbsp;|&nbsp;
                        <b>Severity:</b> {incident.get('severity')}<br>
                        <b>Entrapped Casualties:</b> {incident.get('num_severe', 1)} severe of {incident.get('num_casualties', 1)} total<br>
                        <b>Squad Objective:</b> {fire.get('current_task')}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Map
            f_coords = NODE_COORDS.get(fire["location"], (28.615, 77.21))
            inc_coords = NODE_COORDS.get(incident.get("location", "E"), (28.615, 77.21))

            m = folium.Map(location=f_coords, zoom_start=14, tiles="CartoDB dark_matter")
            folium.Marker(f_coords, tooltip=f"🚒 {fire['name']}", icon=folium.Icon(color="orange", icon="fire-extinguisher", prefix="fa")).add_to(m)
            folium.Marker(inc_coords, tooltip="Accident Scene", icon=folium.Icon(color="red", icon="exclamation", prefix="fa")).add_to(m)

            route_nodes = fire.get("route", [])
            coords = [NODE_COORDS[n] for n in route_nodes if n in NODE_COORDS]
            if len(coords) >= 2:
                folium.PolyLine(coords, color="#ff9800", weight=5, opacity=0.9).add_to(m)

            st_folium(m, height=360, use_container_width=True)

            if status == "dispatched":
                if st.button("📍 Confirm Arrival (Begin Hydraulic Extrication)", type="primary", use_container_width=True):
                    sm.update_fire_status(unit_id, "on_scene", location=incident.get("location"))
                    st.success("On scene. Hydraulic cutters and foam deployment underway.")
                    st.rerun()
            elif status == "on_scene":
                if st.button("✅ Extrication Complete & Scene Secured", use_container_width=True):
                    sm.update_fire_status(unit_id, "available")
                    st.success("Extrication complete. Casualties handed to ALS paramedics.")
                    st.rerun()

        else:
            st.info(f"🚒 **{fire['name']} is Available.** On standby at station.")
            st.caption(f"Current task: {fire.get('current_task')}")

    with right_col:
        st.subheader("🛠️ Technical Squad Equipment")
        with st.container(border=True):
            st.markdown("**Hydraulic Rescue Tools**")
            st.write("✓ Spreader & Cutter Combis")
            st.write("✓ Ram jacks & stabilization struts")
            st.markdown("**Fire Suppression & Hazmat**")
            st.write("✓ Class B foam inductor (hydrocarbon spills)")
            st.write("✓ Thermal imaging camera")
            st.write("✓ Absorbent containment booms")


if __name__ == "__main__":
    main()
