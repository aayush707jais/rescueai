"""
RESCUE-AI — Unified Multi-Agency Emergency Response System.

Master portal with role-based view switcher:
1. 📝 Citizen Incident Reporting (form.py)
2. 🎛️ Command Center Admin Dashboard (dashboard.py)
3. 🏥 Hospital Emergency Department (hospital_portal.py)
4. 🚑 Ambulance Mobile Terminal (ambulance_portal.py)
5. 🚓 Police Dispatch Terminal (police_portal.py)
6. 🚒 Fire & Rescue Squad (fire_portal.py)

Run:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="RESCUE-AI Multi-Agency Network",
    page_icon="🚨",
    layout="wide",
)

st.sidebar.title("🚨 RESCUE-AI Portals")
st.sidebar.caption("Autonomous Emergency Coordination Network")

role = st.sidebar.radio(
    "Select Operating Role / View:",
    [
        "🎛️ Command Center Admin",
        "🚑 Ambulance Mobile Terminal",
        "🏥 Hospital Emergency Department",
        "🚓 Police Dispatch Terminal",
        "🚒 Fire & Rescue Squad",
        "📝 Citizen Incident Report",
    ],
    index=0,
)

st.sidebar.divider()
st.sidebar.markdown(
    """
    **Independent Execution:**
    Each portal can also run as its own standalone process on distinct monitors:
    - `streamlit run dashboard.py`
    - `streamlit run ambulance_portal.py`
    - `streamlit run hospital_portal.py`
    - `streamlit run police_portal.py`
    - `streamlit run fire_portal.py`
    - `streamlit run form.py`
    """
)

if role == "🎛️ Command Center Admin":
    import dashboard
    dashboard.main()

elif role == "🚑 Ambulance Mobile Terminal":
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

elif role == "📝 Citizen Incident Report":
    import form
    inc_data, img = form.render_form()
    if st.session_state.get("report_submitted", False):
        st.balloons()
        st.success("🚨 Accident report broadcasted to RESCUE-AI Emergency Network!")
        st.info("Responders (Ambulances, Hospitals, Police, Fire) have received your dispatch request.")
