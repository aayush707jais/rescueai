"""
RESCUE-AI — Hospital Emergency Department Portal.

Interface for hospital emergency departments:
- Live alert of inbound ambulances with patient severity & ETAs
- Real-time emergency bed capacity management
- One-click 'Declare Full / Divert' trigger for dynamic casualty rerouting
- Patient admission log

Run:
    streamlit run hospital_portal.py
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime
from src.rescue_ai.state_manager import SystemStateManager

try:
    st.set_page_config(
        page_title="RESCUE-AI Hospital Portal",
        page_icon="🏥",
        layout="wide",
    )
except Exception:
    pass

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; max-width: 1200px; }
    .hero-hosp {
        background: linear-gradient(135deg, #0d47a1 0%, #1976d2 60%, #42a5f5 100%);
        color: white; padding: 1.3rem 1.6rem; border-radius: 14px;
        margin-bottom: 1rem; box-shadow: 0 4px 15px rgba(13,71,161,.25);
    }
    .hero-hosp h1 { margin: 0; font-size: 1.8rem; color: white; }
    .hero-hosp p  { margin: .2rem 0 0 0; opacity: .92; font-size: .9rem; }
    .alert-card {
        background: #3e2723; border: 2px solid #ff7043; border-radius: 10px;
        padding: 1rem 1.2rem; margin-bottom: .8rem;
    }
    .card {
        background: #1e1e2f; border: 1px solid #333; border-radius: 12px;
        padding: 1rem 1.2rem; margin-bottom: .8rem;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #64b5f6; }
    .metric-sub { font-size: .85rem; color: #aaa; text-transform: uppercase; }
    </style>
    """,
    unsafe_allow_html=True,
)

sm = SystemStateManager()


def main():
    st.markdown(
        """
        <div class="hero-hosp">
            <h1>🏥 RESCUE-AI Hospital Emergency Department</h1>
            <p>Inbound Casualty Notification & Capacity Coordination Portal</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    state = sm.load_state()
    hospitals = state.get("hospitals", [])

    # Hospital Selector in Sidebar
    with st.sidebar:
        st.subheader("Select Hospital Facility")
        hosp_ids = [h["hospital_id"] for h in hospitals]
        selected_id = st.selectbox(
            "Facility",
            hosp_ids,
            format_func=lambda hid: f"{hid} - {next((h['name'] for h in hospitals if h['hospital_id'] == hid), hid)}",
        )
        st.divider()
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

    hosp = next((h for h in hospitals if h["hospital_id"] == selected_id), None)
    if not hosp:
        st.error("Hospital not found.")
        return

    # Auto-refreshing view fragment
    render_hospital_dashboard(selected_id)


@st.fragment(run_every="3s")
def render_hospital_dashboard(hospital_id: str):
    state = sm.load_state()
    hosp = next((h for h in state.get("hospitals", []) if h["hospital_id"] == hospital_id), None)
    if not hosp:
        return

    # Top Metric Columns
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="card"><div class="metric-sub">Facility Status</div>'
            f'<div class="metric-value" style="color:{"#4caf50" if hosp["status"]=="open" else "#f44336"}">'
            f'{hosp["status"].upper()}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="card"><div class="metric-sub">Available Beds</div>'
            f'<div class="metric-value">{hosp["available_beds"]} / {hosp["total_beds"]}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="card"><div class="metric-sub">Trauma Designation</div>'
            f'<div class="metric-value">Level {hosp["trauma_level"]}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        inbound_count = sum(p.get("casualties", 1) for p in hosp.get("incoming_patients", []))
        st.markdown(
            f'<div class="card"><div class="metric-sub">Inbound Patients</div>'
            f'<div class="metric-value" style="color:{"#ff9800" if inbound_count > 0 else "#90caf9"}">'
            f'{inbound_count}</div></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # Split into Active Alerts and Capacity Controls
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.subheader("🚨 Inbound Ambulances & Patient Triage")
        incoming = hosp.get("incoming_patients", [])
        if not incoming:
            st.info("No incoming emergency transports reported at this time.")
        else:
            for idx, item in enumerate(incoming):
                sev = item.get("severity", "MEDIUM")
                sev_color = {"CRITICAL": "#ef5350", "HIGH": "#ff7043", "MEDIUM": "#ffa726", "LOW": "#66bb6a"}.get(sev, "#fff")
                st.markdown(
                    f"""
                    <div class="alert-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:1.15rem;font-weight:700;color:{sev_color};">
                                🚨 Incident {item.get('incident_id')} — {sev} SEVERITY
                            </span>
                            <span style="background:#5d4037;padding:3px 10px;border-radius:12px;font-size:0.8rem;">
                                ETA: ~{item.get('eta_minutes', '?')} min
                            </span>
                        </div>
                        <p style="margin:0.5rem 0 0.2rem 0;font-size:0.95rem;">
                            <b>Ambulance(s):</b> {', '.join(item.get('ambulances', []))}<br>
                            <b>Expected Casualties:</b> {item.get('casualties', 0)} ({item.get('severe', 0)} severe)
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"✅ Admit Casualties (Incident {item.get('incident_id')[-6:]})", key=f"admit_{idx}"):
                        # Deduct beds
                        new_beds = max(0, hosp["available_beds"] - item.get("casualties", 1))
                        hosp["available_beds"] = new_beds
                        incoming.pop(idx)
                        hosp["status_log"].append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Admitted {item.get('casualties')} patients from {item.get('incident_id')}"
                        )
                        sm.save_state(state)
                        st.toast("Patients admitted and emergency beds updated!")
                        st.rerun()

        # Operational Status Log
        st.subheader("📜 Facility Activity Log")
        log_items = hosp.get("status_log", [])[-8:]
        for line in reversed(log_items):
            st.caption(f"• {line}")

    with right_col:
        st.subheader("⚙️ Bed Capacity & Diversion")
        with st.container(border=True):
            st.markdown("**Adjust Emergency Bed Availability**")
            new_beds_val = st.number_input(
                "Currently Available Beds",
                min_value=0,
                max_value=hosp["total_beds"],
                value=hosp["available_beds"],
                step=1,
            )
            if st.button("Update Bed Count", use_container_width=True):
                sm.update_hospital_beds(hospital_id, new_beds_val)
                st.toast(f"Updated available beds to {new_beds_val}")
                st.rerun()

            st.divider()

            st.markdown("**Emergency Diversion Trigger**")
            st.caption(
                "If the emergency department is overwhelmed, declaring full will automatically "
                "trigger the **Replanning Controller** to reroute all incoming ambulances to the next trauma hospital."
            )
            if st.button("🛑 Declare Full / Divert Inbound", type="primary", use_container_width=True):
                with st.spinner("Initiating system-wide replanning & rerouting..."):
                    sm.report_hospital_full(hospital_id)
                st.error("Hospital declared FULL. Automatic reroute broadcasted to all ambulances!")
                st.rerun()

            if hosp["status"] == "full":
                if st.button("🟢 Reopen Facility / Cancel Diversion", use_container_width=True):
                    sm.update_hospital_beds(hospital_id, 3)
                    st.success("Facility reopened!")
                    st.rerun()

        # Hospital Capabilities
        with st.container(border=True):
            st.markdown(f"**Facility Info: {hosp['name']}**")
            st.write(f"- **Location Node:** `{hosp['location']}`")
            st.write(f"- **Designation:** Trauma Level {hosp['trauma_level']}")
            st.write(f"- **Capabilities:** {', '.join(hosp.get('capabilities', []))}")


if __name__ == "__main__":
    main()
