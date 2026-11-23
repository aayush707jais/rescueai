"""
Tests for SystemStateManager, Multi-Agency Synchronization, and Replanning.
"""

import pytest
from src.rescue_ai.state_manager import SystemStateManager


@pytest.fixture
def sm():
    manager = SystemStateManager()
    manager.reset_state()
    return manager


def test_initial_state(sm):
    state = sm.load_state()
    assert len(state["ambulances"]) >= 5
    assert len(state["hospitals"]) >= 3
    assert len(state["police_units"]) >= 3
    assert len(state["fire_units"]) >= 2
    assert state["active_incident"] is None


def test_incident_dispatch_assigns_all_agencies(sm):
    incident_input = {
        "incident_location": "E",
        "severity": "HIGH",
        "num_casualties": 4,
        "num_severe": 2,
    }
    state = sm.report_incident(incident_input)

    assert state["active_incident"] is not None
    assert state["active_plan"] is not None

    # Verify at least one ambulance was dispatched
    dispatched_ambs = [a for a in state["ambulances"] if a["status"] == "dispatched"]
    assert len(dispatched_ambs) >= 1
    assert len(dispatched_ambs[0]["current_route"]) >= 2

    # Verify hospital received incoming casualties
    target_hosp = next(h for h in state["hospitals"] if len(h["incoming_patients"]) > 0)
    assert target_hosp is not None
    assert target_hosp["incoming_patients"][0]["casualties"] == 4

    # Verify police was dispatched
    dispatched_police = [p for p in state["police_units"] if p["status"] == "dispatched"]
    assert len(dispatched_police) >= 1

    # Verify fire was dispatched (since severity is HIGH)
    dispatched_fire = [f for f in state["fire_units"] if f["status"] == "dispatched"]
    assert len(dispatched_fire) >= 1


def test_ambulance_breakdown_triggers_auto_reassignment(sm):
    sm.report_incident({
        "incident_location": "E",
        "severity": "HIGH",
        "num_casualties": 3,
        "num_severe": 1,
    })

    state = sm.load_state()
    initial_dispatched = [a["ambulance_id"] for a in state["ambulances"] if a["status"] == "dispatched"]
    assert len(initial_dispatched) >= 1

    failing_id = initial_dispatched[0]

    # Report breakdown
    updated_state = sm.report_ambulance_breakdown(failing_id)

    # Check failing ambulance is marked breakdown
    failing_amb = next(a for a in updated_state["ambulances"] if a["ambulance_id"] == failing_id)
    assert failing_amb["status"] == "breakdown"

    # Plan should be version 2
    assert updated_state["active_plan"]["version"] >= 2


def test_hospital_full_triggers_reroute(sm):
    sm.report_incident({
        "incident_location": "E",
        "severity": "HIGH",
        "num_casualties": 2,
        "num_severe": 1,
    })

    # Declare Central Trauma full
    updated_state = sm.report_hospital_full("HOSP-101")

    hosp = next(h for h in updated_state["hospitals"] if h["hospital_id"] == "HOSP-101")
    assert hosp["status"] == "full"
    assert hosp["available_beds"] == 0

    # New plan hospital should NOT be HOSP-101
    assert updated_state["active_plan"]["selected_hospital"]["hospital_id"] != "HOSP-101"


def test_road_blockage_and_cleared(sm):
    sm.report_incident({
        "incident_location": "E",
        "severity": "MEDIUM",
        "num_casualties": 2,
        "num_severe": 1,
    })

    # Block B-D
    blocked_state = sm.report_road_blockage("B", "D")
    assert "B-D" in blocked_state["blocked_roads"]

    # Clear B-D
    cleared_state = sm.report_road_cleared("B", "D")
    assert "B-D" not in cleared_state["blocked_roads"]
