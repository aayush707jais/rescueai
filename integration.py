"""
RESCUE-AI — Integration Controller

Connects:
    form.py   -> Incident reporting frontend
    vision.py -> Accident/person/wound detection

Run:
    streamlit run integration.py
"""

import streamlit as st

import form
import vision
from coordinator import CoordinatorAgent


# ============================================================
# LOAD VISION MODELS
# ============================================================

@st.cache_resource
def get_coordinator():
    return CoordinatorAgent(
        vision_loader=vision.load_models,
    )


# ============================================================
# PROCESS INCIDENT
# ============================================================

def process_incident(incident_data, image_bytes):
    return get_coordinator().process_incident(incident_data, image_bytes)


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():

    # --------------------------------------------------------
    # PREVENT FORM FROM REAPPEARING AFTER SUBMISSION
    # --------------------------------------------------------

    if st.session_state.get("report_submitted", False):

        if st.session_state.get("pipeline_failed", False):
            st.error("Report submitted, but emergency analysis failed.")
            st.caption(
                st.session_state.get("pipeline_error", "Unknown error")
            )
            return

        if st.session_state.get("analysis_complete", False):

            st.markdown(
                """
                <style>
                .success-container {
                    min-height: 75vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    text-align: center;
                }

                .success-card {
                    padding: 45px 55px;
                    border-radius: 18px;
                    background: #123c2b;
                    border: 1px solid #23734c;
                    max-width: 650px;
                    width: 90%;
                }

                .success-icon {
                    font-size: 65px;
                    margin-bottom: 15px;
                }

                .success-title {
                    color: #4ade80;
                    font-size: 28px;
                    font-weight: 700;
                    margin-bottom: 12px;
                }

                .success-message {
                    color: #ffffff;
                    font-size: 19px;
                }
                </style>

                <div class="success-container">
                    <div class="success-card">
                        <div class="success-icon">🚑</div>
                        <div class="success-title">
                            Report Submitted Successfully!
                        </div>
                        <div class="success-message">
                            Help is on the way.
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        else:
            st.info("Your report has been submitted. Analysis is in progress.")
        return

    # --------------------------------------------------------
    # RENDER INCIDENT FORM
    # --------------------------------------------------------

    incident_data, image_bytes = form.render_form()

    if incident_data is None or image_bytes is None:
        return

    # --------------------------------------------------------
    # RUN VISION PIPELINE
    # --------------------------------------------------------

    try:

        with st.spinner(
            "RESCUE-AI is analysing the accident..."
        ):

            result, json_path = process_incident(
                incident_data,
                image_bytes
            )

        # Mark analysis as completed
        st.session_state["analysis_complete"] = True

        # Hide form and show success message
        st.rerun()

    except Exception as error:

        st.session_state["pipeline_failed"] = True
        st.session_state["pipeline_error"] = str(error)

        st.rerun()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    main()