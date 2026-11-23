"""
RESCUE-AI — Command Center Admin Dashboard (CAD).

Central command and control interface for emergency dispatch administrators:
- View incoming citizen accident reports
- Monitor active response plans in action
- Real-time telemetry and situational map of en-route units and road conditions
- Problem management: manual replanning override, road closure management, and incident resolution

Run:
    streamlit run dashboard.py
"""

from __future__ import annotations

import json
from datetime import datetime

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.rescue_ai.state_manager import SystemStateManager

# ================================================================
# PAGE CONFIG
# ================================================================

try:
    st.set_page_config(
        page_title="RESCUE-AI Command Center Admin",
        page_icon="🎛️",
        layout="wide",
    )
except Exception:
    pass

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1350px; }
    .hero-admin {
        background: linear-gradient(135deg, #1b263b 0%, #0d1b2a 100%);
        border-left: 5px solid #e63946;
        color: white; padding: 1.2rem 1.6rem; border-radius: 12px;
        margin-bottom: 1rem; box-shadow: 0 4px 16px rgba(0,0,0,.35);
    }
    .hero-admin h1 { margin: 0; font-size: 1.8rem; color: #f1faee; }
    .hero-admin p  { margin: .2rem 0 0 0; opacity: .88; font-size: .88rem; color: #a8dadc; }
    .metric-card {
        background: #111a2e; border-radius: 10px; padding: 0.9rem 1.1rem;
        text-align: center; border: 1px solid #1e2d4a;
    }
    .metric-label { color: #8d99ae; font-size: .78rem; text-transform: uppercase; font-weight: 600; }
    .metric-value { color: #edf2f4; font-size: 1.55rem; font-weight: 700; }
    .report-card {
        background: #162238; border: 1px solid #233554; border-radius: 10px;
        padding: 1rem 1.2rem; margin-bottom: 0.8rem;
    }
    .change-card {
        background: #2b1d1d; border-left: 4px solid #e63946; border-radius: 6px;
        padding: .7rem .9rem; margin-top: .4rem; font-size: 0.88rem;
    }
    .status-badge {
        display: inline-block; padding: 3px 10px; border-radius: 14px;
        font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
    }
    .log-row {
        background: #0f172a; border-left: 3px solid #38bdf8; padding: 6px 10px;
        border-radius: 4px; margin-bottom: 5px; font-size: 0.85rem; font-family: monospace;
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
        <div class="hero-admin">
            <h1>🎛️ RESCUE-AI Central Command Center</h1>
            <p>Computer-Aided Dispatch (CAD) • Operational Reports • Active Response Plans & Telemetry Management</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    state = sm.load_state()

    # ============================================================
    # SIDEBAR: INCIDENT QUEUE & COMMAND CONTROLS
    # ============================================================
    with st.sidebar:
        st.header("🗂️ Incident Queue")

        incident_history = state.get("incident_history", [])
        active_incident = state.get("active_incident")

        if not incident_history and not active_incident:
            st.info("No citizen accident reports submitted yet. Standing by for incoming calls.")
        else:
            inc_options = []
            if active_incident and active_incident.get("status") != "resolved":
                inc_options.append(f"🔴 ACTIVE: {active_incident['incident_id']} (Junction {active_incident['location']})")

            for inc in reversed(incident_history):
                opt = f"{'🟢' if inc.get('status')=='resolved' else '🟡'} {inc['incident_id']} - Jct {inc['location']} ({inc['severity']})"
                if opt not in inc_options:
                    inc_options.append(opt)

            st.selectbox("Select Incident Record", inc_options, index=0)

        st.divider()

        # Command Management Actions (Only administrative intervention)
        st.subheader("⚙️ Command Management")
        st.caption("Administrative interventions when field problems or complications occur:")

        # Manual Replan Override
        if active_incident and active_incident.get("status") != "resolved":
            if st.button("⚡ Trigger Emergency Replan", use_container_width=True):
                with st.spinner("Executing dynamic replanning optimization..."):
                    sm.manual_replan(reason="Command Center administrative re-assessment")
                st.toast("Dynamic replanning executed! Updated routes broadcasted.")
                st.rerun()

            # Mark Incident Resolved
            if st.button("🏁 Mark Incident Resolved", type="primary", use_container_width=True):
                sm.resolve_incident(active_incident["incident_id"])
                st.success(f"Incident {active_incident['incident_id']} resolved. Fleet released.")
                st.rerun()

        # Road Network Management
        st.divider()
        st.subheader("🚧 Road Network Control")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            u_node = st.selectbox("Node A", list(NODE_COORDS.keys()), index=1)
        with col_r2:
            v_node = st.selectbox("Node B", list(NODE_COORDS.keys()), index=3)

        if st.button("⛔ Close Road Segment", use_container_width=True):
            if u_node != v_node:
                sm.report_road_blockage(u_node, v_node)
                st.warning(f"Road {u_node}↔{v_node} closed! Detours calculated.")
                st.rerun()

        blocked = state.get("blocked_roads", [])
        if blocked:
            st.markdown(f"**Blocked Segments ({len(blocked)}):**")
            for b_seg in blocked:
                c1_b, c2_b = st.columns([3, 2])
                with c1_b:
                    st.write(f"⛔ {b_seg}")
                with c2_b:
                    if st.button("Clear", key=f"cmd_clr_{b_seg}"):
                        nds = b_seg.split("-")
                        sm.report_road_cleared(nds[0], nds[1])
                        st.toast(f"Segment {b_seg} reopened!")
                        st.rerun()

        st.divider()
        if st.button("🔄 Refresh Telemetry", use_container_width=True):
            st.rerun()

    # Render Main Command Center View
    render_operations_board()


@st.fragment(run_every="2s")
def render_operations_board():
    state = sm.load_state()
    incident = state.get("active_incident")
    plan = state.get("active_plan")

    if not incident or incident.get("status") == "resolved":
        st.info("🟢 **All Clear / Standing By.** No active emergency calls in progress. Waiting for citizen reports via `form.py`.")
        render_system_readiness_summary(state)
        return

    # ============================================================
    # TOP INCIDENT REPORT BANNER
    # ============================================================
    sev = incident.get("severity", "MEDIUM")
    sev_color = {"CRITICAL": "#ef5350", "HIGH": "#ff7043", "MEDIUM": "#ffa726", "LOW": "#66bb6a"}.get(sev, "#fff")

    st.markdown(
        f"""
        <div class="report-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="font-size:1.35rem;font-weight:800;color:{sev_color};">
                        🚨 INCIDENT REPORT: {incident.get('incident_id')}
                    </span>
                    <span style="margin-left:12px;background:#b71c1c;padding:3px 10px;border-radius:12px;color:white;font-weight:700;font-size:0.8rem;">
                        {sev} PRIORITY
                    </span>
                    <span style="margin-left:8px;background:#233554;padding:3px 10px;border-radius:12px;color:#a8dadc;font-size:0.8rem;">
                        Reported via {incident.get('reported_by', 'Citizen Form')}
                    </span>
                </div>
                <div style="font-size:0.88rem;color:#8d99ae;">
                    Time Reported: <b>{incident.get('reported_at', 'Just now')}</b>
                </div>
            </div>
            <div style="margin-top:0.6rem;font-size:0.95rem;color:#cbd5e1;">
                <b>Accident Location:</b> Junction {incident.get('location')} &nbsp;|&nbsp;
                <b>Reported Casualties:</b> {incident.get('num_casualties', 1)} total ({incident.get('num_severe', 0)} severe, {incident.get('num_non_severe', 0)} non-severe) &nbsp;|&nbsp;
                <b>Incident Type:</b> {incident.get('incident_type', 'vehicle_collision')}<br>
                <b>Caller Description:</b> <i>"{incident.get('description', 'Accident reported.')}"</i>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ============================================================
    # KEY METRICS CARDS
    # ============================================================
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Dispatch Status</div>'
            f'<div class="metric-value" style="color:#4ade80">{incident.get("status", "ACTIVE").upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        num_amb = len(plan.get("dispatched_ambulances", [])) if plan else 0
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Ambulances Dispatched</div>'
            f'<div class="metric-value" style="color:#60a5fa">{num_amb} Units</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        hosp_info = plan.get("selected_hospital", {}) if plan else {}
        hosp_name = hosp_info.get("name", "N/A")
        hosp_eta = hosp_info.get("eta_minutes", "?")
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Assigned Medical Facility</div>'
            f'<div class="metric-value" style="font-size:1.1rem">{hosp_name}<br>'
            f'<span style="font-size:0.8rem;color:#94a3b8">ETA: {hosp_eta} min</span></div></div>',
            unsafe_allow_html=True,
        )
    with m4:
        method = plan.get("decision_method", "ml_model") if plan else "N/A"
        conf = plan.get("confidence", 0.95) if plan else 0.0
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Coordination Engine</div>'
            f'<div class="metric-value" style="font-size:1.1rem;color:#facc15">{method}<br>'
            f'<span style="font-size:0.8rem;color:#94a3b8">Confidence: {conf:.0%}</span></div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # ============================================================
    # SITUATION MAP & ACTIVE PLAN DETAILS
    # ============================================================
    map_col, plan_col = st.columns([3, 2])

    with map_col:
        st.subheader("🗺️ Live Operational Map")

        inc_loc = incident.get("location", "E")
        center = NODE_COORDS.get(inc_loc, (28.615, 77.21))
        m = folium.Map(location=center, zoom_start=14, tiles="CartoDB dark_matter")

        # Incident marker
        folium.Marker(
            center,
            tooltip=f"🔴 ACCIDENT SCENE: Junction {inc_loc}",
            icon=folium.Icon(color="red", icon="exclamation-triangle", prefix="fa"),
        ).add_to(m)

        # Ambulances
        dispatched_ids = {a["ambulance_id"] for a in plan.get("dispatched_ambulances", [])} if plan else set()
        for amb in state.get("ambulances", []):
            loc = NODE_COORDS.get(amb["location"])
            if not loc:
                continue
            status = amb.get("status", "available")
            if status == "breakdown":
                color, icon = "black", "wrench"
            elif amb["ambulance_id"] in dispatched_ids:
                color, icon = "red", "ambulance"
            elif status == "available":
                color, icon = "green", "ambulance"
            else:
                color, icon = "gray", "ambulance"

            folium.Marker(
                loc,
                tooltip=f"🚑 {amb['ambulance_id']} ({amb['type']}) — {status.upper()}",
                icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            ).add_to(m)

        # Hospitals
        for hosp in state.get("hospitals", []):
            loc = NODE_COORDS.get(hosp["location"])
            if loc:
                beds = hosp.get("available_beds", 0)
                h_color = "blue" if beds > 0 else "gray"
                folium.Marker(
                    loc,
                    tooltip=f"🏥 {hosp['name']} — {beds} beds",
                    icon=folium.Icon(color=h_color, icon="hospital-o", prefix="fa"),
                ).add_to(m)

        # Police
        for pol in state.get("police_units", []):
            loc = NODE_COORDS.get(pol["location"])
            if loc:
                folium.Marker(
                    loc,
                    tooltip=f"🚓 {pol['name']} — {pol.get('status').upper()}",
                    icon=folium.Icon(color="darkblue", icon="shield", prefix="fa"),
                ).add_to(m)

        # Fire
        for fire in state.get("fire_units", []):
            loc = NODE_COORDS.get(fire["location"])
            if loc:
                folium.Marker(
                    loc,
                    tooltip=f"🚒 {fire['name']} — {fire.get('status').upper()}",
                    icon=folium.Icon(color="orange", icon="fire-extinguisher", prefix="fa"),
                ).add_to(m)

        # Blocked road segments
        for b_seg in state.get("blocked_roads", []):
            u, v = b_seg.split("-")
            if u in NODE_COORDS and v in NODE_COORDS:
                folium.PolyLine(
                    [NODE_COORDS[u], NODE_COORDS[v]],
                    color="#f43f5e",
                    weight=6,
                    dash_array="6, 6",
                    tooltip=f"⛔ ROAD BLOCKED: {u} ↔ {v}",
                ).add_to(m)

        # Dispatched ambulance routes to scene
        for amb in state.get("ambulances", []):
            if amb["ambulance_id"] in dispatched_ids:
                r_nodes = amb.get("current_route", [])
                coords = [NODE_COORDS[n] for n in r_nodes if n in NODE_COORDS]
                if len(coords) >= 2:
                    folium.PolyLine(
                        coords,
                        color="#38bdf8",
                        weight=5,
                        opacity=0.85,
                        tooltip=f"En-route: {amb['ambulance_id']}",
                    ).add_to(m)

        st_folium(m, height=430, use_container_width=True)

    with plan_col:
        st.subheader(f"📋 Plan in Action (v{plan.get('version', 1) if plan else 1})")

        st.markdown("**Dispatched Fleet & Real-Time Status:**")
        for amb in state.get("ambulances", []):
            if amb["ambulance_id"] in dispatched_ids:
                status_str = amb.get("status", "dispatched").upper()
                st.markdown(
                    f"- 🚑 **{amb['ambulance_id']}** ({amb['type']}) "
                    f"&nbsp;•&nbsp; Status: `{status_str}` "
                    f"&nbsp;•&nbsp; ETA: **{amb.get('eta_minutes', '?')} min**"
                )

        st.write("")
        st.markdown(f"**Destination Facility:** {hosp_name}")
        st.markdown(f"**Facility Capacity:** {hosp_info.get('available_beds', 'N/A')} available beds")

        st.markdown("**Automated Directives:**")
        for action in plan.get("response_actions", []) if plan else []:
            st.markdown(f"✓ {action}")

        # Replanning history
        history = plan.get("replan_history", []) if plan else []
        if history:
            st.divider()
            st.markdown(f"**Dynamic Replanning Log ({len(history)} events):**")
            for h in history:
                st.markdown(
                    f'<div class="change-card">'
                    f'⚡ <b>{h.get("event_type", "?")}</b> (v{h.get("version", "?")})<br>'
                    f'<small>Re-evaluated: {", ".join(h.get("agents_rerun", []))} | {h.get("timestamp")}</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ============================================================
    # REAL-TIME AUDIT & TRANSMISSION FEED PER REPORT
    # ============================================================
    st.divider()
    st.subheader("📢 Real-Time Transmission & Audit Feed")
    notifs = state.get("notifications", [])[:12]
    for n in notifs:
        st.markdown(
            f'<div class="log-row">[{n.get("timestamp")}] <b>[{n.get("target_role").upper()}] {n.get("title")}</b>: {n.get("message")}</div>',
            unsafe_allow_html=True,
        )


def render_system_readiness_summary(state: dict):
    """Shown when no incident is active."""
    st.write("")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        avail_ambs = sum(1 for a in state.get("ambulances", []) if a.get("status") == "available")
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Ambulance Readiness</div>'
            f'<div class="metric-value" style="color:#4ade80">{avail_ambs} Available</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        open_hosps = sum(1 for h in state.get("hospitals", []) if h.get("status") == "open")
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Hospitals Operational</div>'
            f'<div class="metric-value" style="color:#60a5fa">{open_hosps} / 3</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        pol_count = len(state.get("police_units", []))
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Police Patrols</div>'
            f'<div class="metric-value">{pol_count} Units</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        fire_count = len(state.get("fire_units", []))
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Fire & Rescue Squads</div>'
            f'<div class="metric-value">{fire_count} Squads</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")
    st.subheader("📜 Recent Resolved Incident History")
    history = state.get("incident_history", [])
    if not history:
        st.caption("No past incidents in session history.")
    else:
        for inc in reversed(history[-5:]):
            st.markdown(
                f"- **{inc['incident_id']}** &nbsp;•&nbsp; Location: Junction {inc['location']} "
                f"&nbsp;•&nbsp; Severity: `{inc['severity']}` &nbsp;•&nbsp; Casualties: {inc['num_casualties']} "
                f"&nbsp;•&nbsp; Status: `{inc.get('status', 'resolved').upper()}`"
            )


if __name__ == "__main__":
    main()
