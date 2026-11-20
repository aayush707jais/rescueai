"""
RESCUE-AI — Main Pipeline.

Connects every component of the system into a single end-to-end pipeline::

    User Input + Image
         │
         ▼
    Vision Agent  (existing — accident / person / wound YOLO models)
         │
         ▼
    Severity & Resource Demand Agent  (existing — rule-based)
         │
         ▼
    Resource Search Agent  ──→  Route Agent
         │                        │
         └────────┬───────────────┘
                  ▼
    Coordinator Agent  (trained ML or rule-based fallback)
                  │
                  ▼
           Response Plan
                  │
                  ▼
     Replanning Controller  (event-driven)
                  │
                  ▼
        Updated Response Plan

Run:
    python main_pipeline.py          # demo mode
    python main_pipeline.py --json   # print JSON output
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Local imports
from src.rescue_ai.synthetic_map import create_synthetic_map
from src.rescue_ai.route_agent import RouteAgent
from src.rescue_ai.resource_search_agent import ResourceSearchAgent, AMBULANCES, HOSPITALS
from src.rescue_ai.coordinator_agent import CoordinatorDecisionAgent
from src.rescue_ai.replanning_controller import (
    ReplanningController,
    ResponsePlan,
)


class RescueAIPipeline:
    """Full RESCUE-AI pipeline: from incident to response plan."""

    def __init__(self) -> None:
        self.route_agent = RouteAgent()
        self.resource_agent = ResourceSearchAgent()
        self.coordinator = CoordinatorDecisionAgent()
        self.replanner = ReplanningController()
        self._current_plan: Optional[ResponsePlan] = None

        # Register agent callbacks for replanning
        self.replanner.register_agent("resource_search", self._replan_resource_search)
        self.replanner.register_agent("route", self._replan_route)
        self.replanner.register_agent("coordinator", self._replan_coordinator)

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def process_incident(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the full pipeline on an incident and return a response plan.

        Parameters
        ----------
        incident_data : dict with keys

            - incident_location : str (node id on the synthetic map, e.g. "E")
            - severity : str (LOW / MEDIUM / HIGH / CRITICAL)
            - num_casualties : int
            - num_severe : int (optional, derived if missing)
            - num_non_severe : int (optional, derived if missing)
            - incident_type : str (optional)
            - additional_information : str (optional)

        Returns
        -------
        dict — the full response plan.
        """
        location = incident_data.get("incident_location", "E")
        severity = incident_data.get("severity", "MEDIUM")
        num_casualties = incident_data.get("num_casualties", 1)
        num_severe = incident_data.get("num_severe", 0)
        num_non_severe = incident_data.get("num_non_severe", num_casualties - num_severe)

        # Resource requirements (from Severity & Resource Demand rules)
        als_required = num_severe
        bls_required = math.ceil(num_non_severe / 2) if num_non_severe else 0
        resource_requirements = {
            "ALS_ambulances": als_required,
            "BLS_ambulances": bls_required,
            "paramedic_teams": math.ceil(num_casualties / 10) if num_casualties else 0,
            "police_required": True,
        }

        print("\n" + "=" * 60)
        print("RESCUE-AI PIPELINE — PROCESSING INCIDENT")
        print("=" * 60)
        print(f"Location     : {location}")
        print(f"Severity     : {severity}")
        print(f"Casualties   : {num_casualties} ({num_severe} severe)")
        print(f"ALS needed   : {als_required}")
        print(f"BLS needed   : {bls_required}")

        # ---- Step 1: Resource Search ----
        print("\n[1/3] Searching for available resources...")
        als_caps = ["ALS"] if als_required > 0 else []
        ambulance_candidates = self.resource_agent.search_ambulances(
            location, als_caps,
        )
        # Also search for BLS
        bls_candidates = self.resource_agent.search_ambulances(
            location, ["BLS"],
        )
        # Merge and deduplicate
        seen_ids = set()
        all_candidates = []
        for a in ambulance_candidates + bls_candidates:
            if a["ambulance_id"] not in seen_ids:
                seen_ids.add(a["ambulance_id"])
                all_candidates.append(a)

        hospital_candidates = self.resource_agent.search_hospitals(
            location, ["TRAUMA"] if severity in ("HIGH", "CRITICAL") else ["EMERGENCY"],
        )
        # Fallback: if TRAUMA search yielded nothing, search EMERGENCY
        if not hospital_candidates and severity in ("HIGH", "CRITICAL"):
            hospital_candidates = self.resource_agent.search_hospitals(
                location, ["EMERGENCY"],
            )

        print(f"  Ambulances found : {len(all_candidates)}")
        print(f"  Hospitals found  : {len(hospital_candidates)}")

        # ---- Step 2: Enrich candidates with route info ----
        print("\n[2/3] Calculating routes and ETAs...")
        for a in all_candidates:
            a["type"] = "ALS" if "ALS" in a.get("capabilities", []) else "BLS"
        for h in hospital_candidates:
            h["trauma_level"] = 1 if "TRAUMA" in h.get("capabilities", []) else 3
            h["available_capacity"] = h.get("available_beds", 0)

        # ---- Step 3: Coordinator Decision ----
        print("\n[3/3] Coordinator making dispatch decision...")
        incident_state = {
            "severity": severity,
            "num_casualties": num_casualties,
            "num_severe": num_severe,
            "num_non_severe": num_non_severe,
            "resource_requirements": resource_requirements,
            "candidate_ambulances": all_candidates,
            "candidate_hospitals": hospital_candidates,
            "road_conditions": {},
        }

        decision = self.coordinator.make_decision(incident_state)

        # ---- Build Response Plan ----
        plan = ResponsePlan(
            incident_id=f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            incident_location=location,
            severity=severity,
            num_casualties=num_casualties,
            num_severe=num_severe,
            num_non_severe=num_non_severe,
            resource_requirements=resource_requirements,
            dispatch_priority=decision["dispatch_priority"],
            dispatched_ambulances=decision["dispatched_ambulances"],
            selected_hospital=decision["selected_hospital"],
            response_actions=decision["response_actions"],
            routes={
                "ambulance_routes": [
                    {
                        "ambulance_id": a.get("ambulance_id"),
                        "route": a.get("route", []),
                        "eta_minutes": a.get("eta_minutes", 0),
                    }
                    for a in all_candidates
                    if a["ambulance_id"] in {d["ambulance_id"] for d in decision["dispatched_ambulances"]}
                ],
                "hospital_route": {
                    "hospital_id": decision["selected_hospital"].get("hospital_id"),
                    "eta_minutes": decision["selected_hospital"].get("eta_minutes", 0),
                },
            },
            decision_method=decision["decision_method"],
            confidence=decision["confidence"],
        )

        self._current_plan = plan

        print("\n" + plan.summary())
        return plan.to_dict()

    # ------------------------------------------------------------------
    # Dynamic replanning
    # ------------------------------------------------------------------

    def handle_dynamic_event(
        self,
        event_type: str,
        event_details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle a dynamic event and return the updated plan."""
        if self._current_plan is None:
            raise RuntimeError("No active plan — process an incident first.")

        old_plan = self._current_plan
        new_plan = self.replanner.handle_event(
            event_type, event_details, old_plan, self,
        )
        self._current_plan = new_plan

        changes = self.replanner.detect_plan_changes(old_plan, new_plan)
        print("\n--- Plan Changes ---")
        for c in changes["changes"]:
            print(f"  • {c}")
        print("\n" + new_plan.summary())

        result = new_plan.to_dict()
        result["plan_changes"] = changes
        return result

    # ------------------------------------------------------------------
    # Replanning callbacks
    # ------------------------------------------------------------------

    def _replan_resource_search(self, plan, env, **kwargs):
        """Re-search resources after an event."""
        location = plan.incident_location
        severity = plan.severity
        als_caps = ["ALS"] if plan.num_severe > 0 else []
        ambs = self.resource_agent.search_ambulances(location, als_caps)
        bls = self.resource_agent.search_ambulances(location, ["BLS"])
        seen = set()
        all_ambs = []
        for a in ambs + bls:
            if a["ambulance_id"] not in seen:
                seen.add(a["ambulance_id"])
                a["type"] = "ALS" if "ALS" in a.get("capabilities", []) else "BLS"
                all_ambs.append(a)

        hosps = self.resource_agent.search_hospitals(
            location,
            ["TRAUMA"] if severity in ("HIGH", "CRITICAL") else ["EMERGENCY"],
        )
        if not hosps and severity in ("HIGH", "CRITICAL"):
            hosps = self.resource_agent.search_hospitals(location, ["EMERGENCY"])
        for h in hosps:
            h["trauma_level"] = 1 if "TRAUMA" in h.get("capabilities", []) else 3
            h["available_capacity"] = h.get("available_beds", 0)

        return {
            "candidate_ambulances": all_ambs,
            "candidate_hospitals": hosps,
        }

    def _replan_route(self, plan, env, **kwargs):
        """Recalculate routes (already embedded in search results)."""
        partial = kwargs.get("partial_results", {})
        return partial.get("resource_search", {})

    def _replan_coordinator(self, plan, env, **kwargs):
        """Re-run coordinator with updated resource info."""
        partial = kwargs.get("partial_results", {})
        resource_info = partial.get("resource_search", partial.get("route", {}))
        ambs = resource_info.get("candidate_ambulances", plan.dispatched_ambulances)
        hosps = resource_info.get("candidate_hospitals", [plan.selected_hospital])

        incident_state = {
            "severity": plan.severity,
            "num_casualties": plan.num_casualties,
            "num_severe": plan.num_severe,
            "num_non_severe": plan.num_non_severe,
            "resource_requirements": plan.resource_requirements,
            "candidate_ambulances": ambs,
            "candidate_hospitals": hosps,
            "road_conditions": {},
        }
        return self.coordinator.make_decision(incident_state)

    # ------------------------------------------------------------------
    # Environment mutation helpers (called by ReplanningController)
    # ------------------------------------------------------------------

    def set_ambulance_unavailable(self, ambulance_id: str) -> None:
        """Mark an ambulance as unavailable in the resource pool."""
        for a in AMBULANCES:
            if a["ambulance_id"] == ambulance_id:
                a["status"] = "unavailable"
                print(f"[Event] Ambulance {ambulance_id} marked unavailable")
                return

    def set_hospital_full(self, hospital_id: str) -> None:
        """Set a hospital's available beds to 0."""
        for h in HOSPITALS:
            if h["hospital_id"] == hospital_id:
                h["available_beds"] = 0
                print(f"[Event] Hospital {hospital_id} marked full")
                return

    # ------------------------------------------------------------------
    # Demo
    # ------------------------------------------------------------------

    def run_demo(self, json_output: bool = False) -> None:
        """Run a complete demonstration of the RESCUE-AI pipeline."""
        print("=" * 60)
        print("   RESCUE-AI: Autonomous Emergency Response Coordination")
        print("   Demo Mode — Synthetic Road Network")
        print("=" * 60)

        # Reset ambulance/hospital state for demo
        for a in AMBULANCES:
            if a["ambulance_id"] != "AMB-103":
                a["status"] = "available"
        for h in HOSPITALS:
            if h["hospital_id"] == "HOSP-101":
                h["available_beds"] = 5
            elif h["hospital_id"] == "HOSP-102":
                h["available_beds"] = 3

        # ---- Process initial incident ----
        incident = {
            "incident_location": "E",
            "severity": "HIGH",
            "num_casualties": 4,
            "num_severe": 2,
            "num_non_severe": 2,
            "incident_type": "vehicle_collision",
            "additional_information": "Multi-vehicle collision at Hospital Junction",
        }

        result = self.process_incident(incident)

        if json_output:
            print("\n--- Initial Plan JSON ---")
            print(json.dumps(result, indent=2))

        # ---- Simulate dynamic event: ambulance breakdown ----
        print("\n" + "=" * 60)
        print("DYNAMIC EVENT: Ambulance Breakdown")
        print("=" * 60)

        dispatched = result.get("dispatched_ambulances", [])
        if dispatched:
            failed_id = dispatched[0].get("ambulance_id", "AMB-101")
        else:
            failed_id = "AMB-101"

        updated = self.handle_dynamic_event(
            "AMBULANCE_UNAVAILABLE",
            {"ambulance_id": failed_id},
        )

        if json_output:
            print("\n--- Updated Plan JSON ---")
            print(json.dumps(updated, indent=2))

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)

        return result, updated


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    json_flag = "--json" in sys.argv
    pipeline = RescueAIPipeline()
    pipeline.run_demo(json_output=json_flag)
