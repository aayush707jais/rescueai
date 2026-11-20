"""
Tests for Coordinator Agent, Replanning Controller, and Pipeline.
"""

import pytest
from src.rescue_ai.coordinator_agent import CoordinatorDecisionAgent
from src.rescue_ai.replanning_controller import ReplanningController, ResponsePlan
from main_pipeline import RescueAIPipeline
from src.rescue_ai.resource_search_agent import AMBULANCES, HOSPITALS


@pytest.fixture
def coordinator():
    return CoordinatorDecisionAgent()


@pytest.fixture
def replanner():
    return ReplanningController()


@pytest.fixture
def pipeline():
    return RescueAIPipeline()


def test_coordinator_loads_ml_or_fallback(coordinator):
    state = {
        "severity": "HIGH",
        "num_casualties": 3,
        "num_severe": 1,
        "num_non_severe": 2,
        "resource_requirements": {"ALS_ambulances": 1, "BLS_ambulances": 1},
        "candidate_ambulances": [
            {"ambulance_id": "AMB-101", "type": "ALS", "eta_minutes": 3.5},
            {"ambulance_id": "AMB-102", "type": "BLS", "eta_minutes": 5.0},
        ],
        "candidate_hospitals": [
            {"hospital_id": "HOSP-101", "name": "Central Hospital", "trauma_level": 1, "available_capacity": 5, "eta_minutes": 4.0}
        ],
    }
    decision = coordinator.make_decision(state)

    assert decision["dispatch_priority"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert len(decision["dispatched_ambulances"]) >= 1
    assert decision["selected_hospital"]["hospital_id"] == "HOSP-101"
    assert len(decision["response_actions"]) > 0
    assert decision["decision_method"] in ["ml_model", "rule_based"]


def test_replanning_controller_handles_ambulance_breakdown(replanner):
    plan = ResponsePlan(
        incident_id="INC-TEST",
        incident_location="E",
        severity="HIGH",
        num_casualties=2,
        num_severe=1,
        num_non_severe=1,
        dispatch_priority="HIGH",
        dispatched_ambulances=[{"ambulance_id": "AMB-101", "type": "ALS"}],
        selected_hospital={"hospital_id": "HOSP-101", "name": "Central"},
    )

    # Register mock coordinator callback
    def mock_coordinator(p, env, **kwargs):
        return {
            "dispatch_priority": "HIGH",
            "dispatched_ambulances": [{"ambulance_id": "AMB-102", "type": "BLS"}],
            "selected_hospital": {"hospital_id": "HOSP-101", "name": "Central"},
            "response_actions": ["Dispatch replacement"],
            "decision_method": "rule_based",
            "confidence": 1.0,
        }

    replanner.register_agent("coordinator", mock_coordinator)

    updated_plan = replanner.handle_event(
        "AMBULANCE_UNAVAILABLE",
        {"ambulance_id": "AMB-101"},
        plan,
        environment=None,
    )

    assert updated_plan.version == 2
    assert len(updated_plan.replan_history) == 1
    assert updated_plan.replan_history[0]["event_type"] == "AMBULANCE_UNAVAILABLE"
    assert updated_plan.dispatched_ambulances[0]["ambulance_id"] == "AMB-102"


def test_pipeline_end_to_end(pipeline):
    incident = {
        "incident_location": "E",
        "severity": "MEDIUM",
        "num_casualties": 2,
        "num_severe": 1,
        "num_non_severe": 1,
    }
    result = pipeline.process_incident(incident)

    assert result["incident_location"] == "E"
    assert result["dispatch_priority"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert len(result["dispatched_ambulances"]) >= 1
    assert "hospital_id" in result["selected_hospital"]
    assert result["version"] == 1
