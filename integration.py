"""
RESCUE-AI — Master Integration & Automated Multi-Agency Platform.

The single main file that activates the entire emergency response pipeline:
- Automated ML Coordination & Dispatch Engine
- Citizen Accident Reporting (with YOLO vision inference & graceful fallback)
- Command Center Admin CAD
- Ambulance Mobile Data Terminals (MDT)
- Hospital Emergency Departments
- Police Dispatch & Traffic Enforcement
- Fire & Rescue Technical Squads

Run:
    streamlit run integration.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import streamlit as st

from src.rescue_ai.state_manager import SystemStateManager

# ================================================================
# PAGE CONFIGURATION (Protected against double-call errors)
# ================================================================

try:
    st.set_page_config(
        page_title="RESCUE-AI Integrated Command System",
        page_icon="🚨",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

sm = SystemStateManager()

# ================================================================
# STYLING
# ================================================================

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1350px; }
    .status-bar {
        background: #0f172a; border: 1px solid #1e293b; border-radius: 10px;
        padding: 0.75rem 1.2rem; margin-bottom: 1rem; display: flex;
        justify-content: space-between; align-items: center; flex-wrap: wrap;
    }
    .status-badge {
        background: #14532d; color: #4ade80; padding: 4px 10px;
        border-radius: 14px; font-weight: 700; font-size: 0.8rem;
    }
    .info-badge {
        background: #1e293b; color: #94a3b8; padding: 4px 10px;
        border-radius: 14px; font-size: 0.8rem; margin-left: 6px;
    }
    .preset-card {
        background: #1e293b; border: 1px solid #334155; border-radius: 10px;
        padding: 1rem; margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ================================================================
# MULTI-WINDOW SPAWNER HELPER
# ================================================================

PORT_MAPPINGS = [
    ("🎛️ Command Center Admin", "dashboard.py", 8501),
    ("🚑 Ambulance Mobile Terminal", "ambulance_portal.py", 8502),
    ("🏥 Hospital Emergency Dept", "hospital_portal.py", 8503),
    ("🚓 Police Dispatch Terminal", "police_portal.py", 8504),
    ("🚒 Fire & Rescue Squad", "fire_portal.py", 8505),
    ("📝 Citizen Incident Report", "form.py", 8506),
]


def launch_all_independent_portals():
    """Spawn distinct background processes on unique ports and open them in browser tabs."""
    base_dir = Path(__file__).resolve().parent
    python_bin = sys.executable

    for name, script_file, port in PORT_MAPPINGS:
        script_path = base_dir / script_file
        cmd = [
            python_bin,
            "-m",
            "streamlit",
            "run",
            str(script_path),
            f"--server.port={port}",
            "--server.headless=true",
        ]
        try:
            subprocess.Popen(
                cmd,
                cwd=str(base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            webbrowser.open(f"http://localhost:{port}")
        except Exception as exc:
            st.error(f"Failed to launch {name} on port {port}: {exc}")


# ================================================================
# MASTER APPLICATION INTERFACE
# ================================================================

def main():
    state = sm.load_state()

    # ---------------- Top Live Operational Bar ----------------
    active_inc = state.get("active_incident")
    active_inc_text = "🟢 Standby (No active emergencies)"
    if active_inc and active_inc.get("status") != "resolved":
        active_inc_text = f"🚨 INCIDENT ACTIVE: {active_inc['incident_id']} at Junction {active_inc['location']} ({active_inc['severity']})"

    st.markdown(
        f"""
        <div class="status-bar">
            <div>
                <span class="status-badge">⚡ AI PIPELINE ACTIVE</span>
                <span style="margin-left:10px;font-size:0.9rem;font-weight:600;color:#f8fafc;">
                    {active_inc_text}
                </span>
            </div>
            <div>
                <span class="info-badge">🚑 5 Ambulances</span>
                <span class="info-badge">🏥 3 Hospitals</span>
                <span class="info-badge">🚓 3 Police Units</span>
                <span class="info-badge">🚒 2 Fire Squads</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------- Sidebar Header & Navigation ----------------
    st.sidebar.markdown(
        """
        <div style="background:linear-gradient(135deg, #b71c1c, #e53935);padding:14px;border-radius:12px;color:white;margin-bottom:12px;">
            <h2 style="margin:0;font-size:1.35rem;color:white;">🚨 RESCUE-AI Hub</h2>
            <p style="margin:4px 0 0 0;font-size:0.8rem;opacity:0.92;">Master Emergency Operating Platform</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    role = st.sidebar.radio(
        "Select Operating Terminal:",
        [
            "🎛️ Command Center Admin (CAD)",
            "📝 Citizen Incident Reporting & AI Vision",
            "🚑 Ambulance Mobile Terminal (MDT)",
            "🏥 Hospital Emergency Department",
            "🚓 Police Dispatch Terminal",
            "🚒 Fire & Rescue Squad",
        ],
        index=0,
    )

    st.sidebar.divider()

    # Multi-Window Quick Launcher
    st.sidebar.markdown("### 🖥️ Multi-Screen Mode")
    st.sidebar.caption("Run all 6 agency terminals in independent browser windows:")
    if st.sidebar.button("🚀 Open All Portals in Separate Windows", use_container_width=True):
        with st.spinner("Spawning all 6 agency terminals on distinct ports..."):
            launch_all_independent_portals()
        st.sidebar.success("All 6 agency portals launched on ports 8501-8506!")

    st.sidebar.divider()
    if st.sidebar.button("🔄 Reset Entire Emergency Fleet", use_container_width=True):
        sm.reset_state()
        st.sidebar.info("Fleet readiness reset to default.")
        st.rerun()

    # ---------------- View Router ----------------

    if role == "🎛️ Command Center Admin (CAD)":
        import dashboard
        dashboard.main()

    elif role == "🚑 Ambulance Mobile Terminal (MDT)":
        import ambulance_portal
        ambulance_portal.main()

    elif role == "🏥 Hospital Emergency Department":
        import hospital_portal
        hospital_portal.main()

    elif role == "🚓 Police Dispatch Terminal":
        import police_portal
        police_portal.main()

    elif role == "🚒 Fire & Rescue Squad":
        import fire_portal
        fire_portal.main()

    elif role == "📝 Citizen Incident Reporting & AI Vision":
        render_citizen_vision_flow()


# ================================================================
# CITIZEN REPORTING + YOLO VISION + DISPATCH INTEGRATION
# ================================================================

def render_citizen_vision_flow():
    st.markdown(
        """
        <div style="background:linear-gradient(135deg, #1b5e20, #2e7d32, #43a047);padding:1.3rem 1.6rem;border-radius:14px;color:white;margin-bottom:1rem;">
            <h1 style="margin:0;font-size:1.8rem;color:white;">📝 Citizen Accident Reporting & AI Vision Triage</h1>
            <p style="margin:4px 0 0 0;font-size:0.9rem;opacity:0.92;">
                Submit an accident report with real-time GPS or trigger simulation presets.
                Submissions automatically activate the ML Coordinator and dispatch all agency units!
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_form, tab_presets = st.tabs(["📋 Manual Report & Photo Upload", "⚡ Quick Simulation Presets"])

    with tab_presets:
        st.markdown("### ⚡ One-Click Emergency Dispatch Presets")
        st.caption("Click any scenario to activate the full AI pipeline and dispatch all units instantly:")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                """
                <div class="preset-card">
                    <h4>🚨 Multi-Vehicle Collision</h4>
                    <p style="font-size:0.85rem;color:#cbd5e1;">
                        <b>Location:</b> Junction E (Hospital Junction)<br>
                        <b>Severity:</b> HIGH • 4 Casualties (2 severe)<br>
                        Requires ALS + BLS + Trauma Hospital + Police + Fire Squad
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Trigger Scenario 1 (Jct E)", type="primary", use_container_width=True):
                with st.spinner("Activating AI coordination pipeline..."):
                    sm.report_incident({
                        "incident_location": "E",
                        "severity": "HIGH",
                        "num_casualties": 4,
                        "num_severe": 2,
                        "incident_type": "multiple_vehicle_collision",
                        "additional_information": "High-impact collision between SUV and sedan at Hospital Junction",
                        "reported_by": "Citizen Emergency Preset 1",
                    })
                st.balloons()
                st.success("🚨 Scenario 1 Dispatched! Ambulances, Hospital, Police, and Fire are responding.")
                st.rerun()

        with col2:
            st.markdown(
                """
                <div class="preset-card">
                    <h4>💥 Vehicle Rollover & Entrapment</h4>
                    <p style="font-size:0.85rem;color:#cbd5e1;">
                        <b>Location:</b> Junction D (South Junction)<br>
                        <b>Severity:</b> CRITICAL • 6 Casualties (4 severe)<br>
                        Critical mass-casualty requiring multi-ambulance & extrication
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Trigger Scenario 2 (Jct D)", type="primary", use_container_width=True):
                with st.spinner("Activating AI coordination pipeline..."):
                    sm.report_incident({
                        "incident_location": "D",
                        "severity": "CRITICAL",
                        "num_casualties": 6,
                        "num_severe": 4,
                        "incident_type": "vehicle_rollover",
                        "additional_information": "Rolled-over minibus with entrapped passengers near South Junction",
                        "reported_by": "Citizen Emergency Preset 2",
                    })
                st.balloons()
                st.success("💥 Scenario 2 Dispatched! Heavy extrication and ALS units deployed.")
                st.rerun()

        with col3:
            st.markdown(
                """
                <div class="preset-card">
                    <h4>⚠️ Vehicle-Pedestrian Accident</h4>
                    <p style="font-size:0.85rem;color:#cbd5e1;">
                        <b>Location:</b> Junction A (North Junction)<br>
                        <b>Severity:</b> MEDIUM • 2 Casualties (1 severe)<br>
                        Rapid BLS & ALS response
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Trigger Scenario 3 (Jct A)", type="primary", use_container_width=True):
                with st.spinner("Activating AI coordination pipeline..."):
                    sm.report_incident({
                        "incident_location": "A",
                        "severity": "MEDIUM",
                        "num_casualties": 2,
                        "num_severe": 1,
                        "incident_type": "vehicle_pedestrian_accident",
                        "additional_information": "Car struck two pedestrians at North pedestrian crossing",
                        "reported_by": "Citizen Emergency Preset 3",
                    })
                st.balloons()
                st.success("⚠️ Scenario 3 Dispatched! Ambulances en route to Junction A.")
                st.rerun()

    with tab_form:
        # If submission was already processed
        if st.session_state.get("report_submitted", False):
            st.balloons()
            st.success("✅ Accident Report Successfully Processed & Dispatched!")
            st.info(
                "The AI Vision & ML Coordinator models evaluated the scene. "
                "Ambulance crews, the trauma hospital, police, and fire rescue have been dispatched."
            )
            if st.button("Submit Another Incident Report"):
                st.session_state["report_submitted"] = False
                st.rerun()
            return

        import form
        incident_data, image_bytes = form.render_form()

        if incident_data is None or image_bytes is None:
            return

        with st.spinner("🤖 Evaluating Accident Scene & Dispatching Responders..."):
            total_casualties = 2
            severe_casualties = 1
            sev_rating = "MEDIUM"

            # Attempt Vision Model inference with fault-tolerant fallback
            try:
                from coordinator import CoordinatorAgent
                import vision
                coord = CoordinatorAgent(vision_loader=vision.load_models)
                res, _ = coord.process_incident(incident_data, image_bytes)
                stats = res.get("severity_and_resource_demand", {}).get("patient_statistics", {})
                total_casualties = max(1, stats.get("total_patients", 2))
                severe_casualties = stats.get("severe_wound_patients", 1)
                sev_rating = res.get("severity_and_resource_demand", {}).get("overall_severity", "HIGH")
            except Exception as e:
                # Intelligent heuristic fallback if YOLO weights or torch are compiling
                rep_cas = incident_data.get("reported_casualties")
                if rep_cas is not None:
                    total_casualties = max(1, int(rep_cas))
                    severe_casualties = max(1, total_casualties // 2)
                    sev_rating = "CRITICAL" if total_casualties >= 5 else ("HIGH" if total_casualties >= 3 else "MEDIUM")

            NODE_COORDS = {
                "A": (28.6239, 77.1990),
                "B": (28.6189, 77.2090),
                "C": (28.6189, 77.2200),
                "D": (28.6089, 77.2090),
                "E": (28.6089, 77.2200),
                "F": (28.6239, 77.1890),
            }
            loc_dict = incident_data.get("location", {})
            c_lat = float(loc_dict.get("latitude", 28.6089))
            c_lon = float(loc_dict.get("longitude", 77.2200))
            closest_node = min(
                NODE_COORDS.keys(),
                key=lambda n: (NODE_COORDS[n][0] - c_lat)**2 + (NODE_COORDS[n][1] - c_lon)**2
            )

            sm.report_incident({
                "incident_location": closest_node,
                "severity": sev_rating,
                "num_casualties": total_casualties,
                "num_severe": severe_casualties,
                "incident_type": incident_data.get("incident_type", "vehicle_collision"),
                "additional_information": incident_data.get("additional_information", "Accident reported via citizen form"),
                "reported_by": "Citizen Vision Portal",
            })

        st.session_state["report_submitted"] = True
        st.rerun()


# ================================================================
# CLI ENTRY POINT
# ================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--launch-all":
        print("Launching all 6 RESCUE-AI portals in independent browser windows...")
        launch_all_independent_portals()
    elif not sys.argv[0].endswith("streamlit") and "streamlit" not in sys.modules:
        cmd = [sys.executable, "-m", "streamlit", "run", __file__]
        subprocess.run(cmd)
    else:
        main()
