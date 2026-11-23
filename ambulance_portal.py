"""
RESCUE-AI — Ambulance Mobile Data Terminal (MDT) Portal.

Driver and Paramedic interface:
- Live dispatch assignment alerts with incident details
- Real-time turn-by-turn navigation map (Ambulance -> Incident -> Hospital)
- Dynamic rerouting alerts (road blockage detours or hospital diversion)
- Mission progression status updater
- Emergency 'Unable to Reach / Breakdown' trigger that auto-reassigns the nearest replacement ambulance

Run:
    streamlit run ambulance_portal.py
"""

from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime
from src.rescue_ai.state_manager import SystemStateManager

try:
    st.set_page_config(
        page_title="RESCUE-AI Ambulance MDT",
        page_icon="🚑",
        layout="wide",
    )
except Exception:
    pass

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1200px; }
    .hero-amb {
        background: linear-gradient(135deg, #b71c1c 0%, #c62828 50%, #e53935 100%);
        color: white; padding: 1.3rem 1.6rem; border-radius: 14px;
        margin-bottom: 1rem; box-shadow: 0 4px 15px rgba(183,28,28,.25);
    }
    .hero-amb h1 { margin: 0; font-size: 1.8rem; color: white; }
    .hero-amb p  { margin: .2rem 0 0 0; opacity: .92; font-size: .9rem; }
    .dispatch-banner {
        background: #3e2723; border: 2px solid #ff5722; border-radius: 12px;
        padding: 1.2rem 1.4rem; margin-bottom: 1rem;
        box-shadow: 0 4px 12px rgba(255,87,34,.2);
    }
    .status-badge {
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-weight: 700; font-size: 0.85rem; text-transform: uppercase;
    }
    .card {
        background: #1e1e2f; border: 1px solid #333; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: .8rem;
    }
    .step-box {
        background: #263238; border-left: 4px solid #00bcd4; padding: 8px 12px;
        border-radius: 4px; margin-bottom: 6px; font-size: 0.95rem;
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
        <div class="hero-amb">
            <h1>🚑 RESCUE-AI Ambulance Mobile Terminal</h1>
            <p>Field Responder Navigation & Dispatch Command Interface</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    state = sm.load_state()
    ambulances = state.get("ambulances", [])

    with st.sidebar:
        st.subheader("Select Vehicle Unit")
        amb_ids = [a["ambulance_id"] for a in ambulances]
        selected_id = st.selectbox(
            "Ambulance Unit",
            amb_ids,
            format_func=lambda aid: f"{aid} ({next((a['type'] for a in ambulances if a['ambulance_id'] == aid), '')})",
        )
        st.divider()
        if st.button("🔄 Refresh Terminal", use_container_width=True):
            st.rerun()

    amb = next((a for a in ambulances if a["ambulance_id"] == selected_id), None)
    if not amb:
        st.error("Ambulance unit not found.")
        return

    render_ambulance_terminal(selected_id)


@st.fragment(run_every="2s")
def render_ambulance_terminal(ambulance_id: str):
    state = sm.load_state()
    amb = next((a for a in state.get("ambulances", []) if a["ambulance_id"] == ambulance_id), None)
    if not amb:
        return

    status = amb.get("status", "available")
    status_colors = {
        "available": ("#2e7d32", "#a5d6a7"),
        "dispatched": ("#d84315", "#ffab91"),
        "en_route_scene": ("#e65100", "#ffcc80"),
        "at_scene": ("#ad1457", "#f48fb1"),
        "en_route_hospital": ("#1565c0", "#90caf9"),
        "breakdown": ("#b71c1c", "#ef9a9a"),
    }
    bg_c, text_c = status_colors.get(status, ("#37474f", "#cfd8dc"))

    # Top Status Bar
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Unit ID</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:#fff">{ambulance_id} ({amb["type"]})</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Mission Status</div>'
            f'<div style="font-size:1.3rem;font-weight:700;color:{text_c}">{status.upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Current Location</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:#80cbc4">Node {amb["location"]}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        eta_val = amb.get("eta_minutes", 0.0)
        st.markdown(
            f'<div class="card"><div style="color:#aaa;font-size:.8rem;text-transform:uppercase;">Est. Travel Time</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:#ffb74d">{eta_val} min</div></div>',
            unsafe_allow_html=True,
        )

    # Breakdown Alert if in breakdown status
    if status == "breakdown":
        st.error(
            "⚠️ UNIT OUT OF SERVICE: Mechanical breakdown reported. "
            "Incident mission has been transferred to another ambulance."
        )
        if st.button("🔧 Vehicle Repaired & Return to Service", type="primary"):
            sm.update_ambulance_status(ambulance_id, "available")
            st.success("Unit restored to AVAILABLE status!")
            st.rerun()
        return

    # Check if dispatched to an incident
    incident = state.get("active_incident")
    plan = state.get("active_plan")

    is_assigned = (
        status in ("dispatched", "en_route_scene", "at_scene", "en_route_hospital")
        and amb.get("assigned_incident_id")
    )

    if not is_assigned:
        st.info(f"🟢 **{ambulance_id} is Standing By.** Ready for emergency dispatch.")
        # Status log
        st.subheader("📜 Unit Activity Log")
        for line in reversed(amb.get("status_log", [])[-6:]):
            st.caption(f"• {line}")
        return

    # Active Mission Panel
    target_hosp = plan.get("selected_hospital", {}) if plan else {}
    target_hosp_name = target_hosp.get("name", "Nearest Trauma Hospital")

    st.markdown(
        f"""
        <div class="dispatch-banner">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:1.3rem;font-weight:800;color:#ff7043;">
                    🚨 ACTIVE EMERGENCY CALL: {amb.get('assigned_incident_id')}
                </span>
                <span style="background:#b71c1c;padding:4px 12px;border-radius:14px;color:white;font-weight:700;">
                    PRIORITY: {plan.get('dispatch_priority', 'HIGH')}
                </span>
            </div>
            <p style="margin:0.5rem 0 0 0;font-size:1rem;color:#e0e0e0;">
                <b>Accident Location:</b> Junction {amb.get('target_destination')} &nbsp;|&nbsp;
                <b>Destination Hospital:</b> {target_hosp_name} ({target_hosp.get('hospital_id', 'E')})<br>
                <b>Casualties:</b> {incident.get('num_casualties', 1)} ({incident.get('num_severe', 0)} severe)
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.subheader("🗺️ Live GPS Navigation Route")

        amb_loc_coords = NODE_COORDS.get(amb["location"], (28.615, 77.21))
        inc_loc_coords = NODE_COORDS.get(amb.get("target_destination", "E"), (28.615, 77.21))
        hosp_loc_coords = NODE_COORDS.get(target_hosp.get("location", "E"), (28.615, 77.21))

        m = folium.Map(location=amb_loc_coords, zoom_start=14, tiles="CartoDB dark_matter")

        # Ambulance marker
        folium.Marker(
            amb_loc_coords,
            tooltip=f"🚑 {ambulance_id} (Current Position)",
            icon=folium.Icon(color="red", icon="ambulance", prefix="fa"),
        ).add_to(m)

        # Incident marker
        folium.Marker(
            inc_loc_coords,
            tooltip=f"🔴 Incident Location ({amb.get('target_destination')})",
            icon=folium.Icon(color="orange", icon="exclamation-circle", prefix="fa"),
        ).add_to(m)

        # Hospital marker
        folium.Marker(
            hosp_loc_coords,
            tooltip=f"🏥 Destination: {target_hosp_name}",
            icon=folium.Icon(color="blue", icon="hospital-o", prefix="fa"),
        ).add_to(m)

        # Draw route to incident (bright cyan)
        current_route = amb.get("current_route", [])
        route_coords = [NODE_COORDS[n] for n in current_route if n in NODE_COORDS]
        if len(route_coords) >= 2:
            folium.PolyLine(
                route_coords,
                color="#00e5ff",
                weight=5,
                opacity=0.9,
                tooltip=f"Navigation Route to Scene: {' -> '.join(current_route)}",
            ).add_to(m)

        # Draw route from incident to hospital (dashed yellow)
        hosp_route = amb.get("hospital_route", [])
        hosp_coords = [NODE_COORDS[n] for n in hosp_route if n in NODE_COORDS]
        if len(hosp_coords) >= 2:
            folium.PolyLine(
                hosp_coords,
                color="#ffd600",
                weight=4,
                dash_array="8, 8",
                opacity=0.8,
                tooltip=f"Route to Hospital: {' -> '.join(hosp_route)}",
            ).add_to(m)

        st_folium(m, height=360, use_container_width=True)

        st.markdown("**Navigation Waypoints:**")
        st.markdown(
            f'<div class="step-box"><b>1. Scene Route:</b> {" ➔ ".join(current_route)} (~{amb.get("eta_minutes")} min)</div>',
            unsafe_allow_html=True,
        )
        if hosp_route:
            st.markdown(
                f'<div class="step-box"><b>2. Hospital Transfer:</b> {" ➔ ".join(hosp_route)} (~{amb.get("hospital_eta_minutes", 3)} min)</div>',
                unsafe_allow_html=True,
            )

    with right_col:
        st.subheader("⚡ Field Action Controls")

        with st.container(border=True):
            st.markdown("**Mission Stage Progression**")

            if status == "dispatched":
                if st.button("▶️ En Route to Scene", type="primary", use_container_width=True):
                    sm.update_ambulance_status(ambulance_id, "en_route_scene")
                    st.rerun()

            elif status == "en_route_scene":
                dest = amb.get("target_destination", "E")
                if st.button("📍 Arrived at Scene", type="primary", use_container_width=True):
                    sm.update_ambulance_status(ambulance_id, "at_scene", new_location=dest)
                    st.rerun()

            elif status == "at_scene":
                if st.button("🚑 Casualties Loaded ➔ En Route to Hospital", type="primary", use_container_width=True):
                    sm.update_ambulance_status(ambulance_id, "en_route_hospital")
                    st.rerun()

            elif status == "en_route_hospital":
                h_loc = target_hosp.get("location", "E")
                if st.button("🏁 Arrived at Hospital (Complete Mission)", type="primary", use_container_width=True):
                    sm.update_ambulance_status(ambulance_id, "transport_complete", new_location=h_loc)
                    st.balloons()
                    st.success("Patients transferred to emergency department. Unit ready for new calls.")
                    st.rerun()

        st.write("")

        # Emergency Breakdown Trigger (Crucial User Requirement)
        with st.container(border=True):
            st.markdown("🚨 **Emergency Issue / Inability to Reach**")
            st.caption(
                "If this ambulance experiences a mechanical breakdown, collision, or blocked access, "
                "triggering this immediately alerts the Command Center and **automatically dispatches "
                "the next nearest available ambulance** to take over the mission without delay."
            )
            if st.button("⚠️ Report Breakdown / Unable to Reach", type="secondary", use_container_width=True):
                with st.spinner("Broadcasting breakdown & auto-reassigning replacement unit..."):
                    sm.report_ambulance_breakdown(ambulance_id)
                st.error("Breakdown reported! Command Center and replacement ambulance notified.")
                st.rerun()

        # Unit log
        st.markdown("**Unit Transmission Log:**")
        for line in reversed(amb.get("status_log", [])[-4:]):
            st.caption(f"• {line}")


if __name__ == "__main__":
    main()
