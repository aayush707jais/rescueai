"""
RESCUE-AI — Central Real-Time State Manager.

Synchronizes system state across all roles and portals:
1. Citizen / Client Reporting (form.py)
2. Command Center Dashboard (dashboard.py)
3. Hospital Emergency Departments (hospital_portal.py)
4. Ambulance Fleet Terminals (ambulance_portal.py)
5. Police Dispatch Terminals (police_portal.py)
6. Fire & Rescue Terminals (fire_portal.py)

State is persistently stored in JSON format with thread-safe file access.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from main_pipeline import RescueAIPipeline
from src.rescue_ai.route_agent import RouteAgent
from src.rescue_ai.synthetic_map import create_synthetic_map

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = DATA_DIR / "live_state.json"

_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Default Initial State
# ---------------------------------------------------------------------------

def get_initial_state() -> Dict[str, Any]:
    """Return a pristine initial state for the emergency simulation."""
    return {
        "active_incident": None,
        "incident_history": [],
        "active_plan": None,
        "plan_history": [],
        "ambulances": [
            {
                "ambulance_id": "AMB-101",
                "type": "ALS",
                "capabilities": ["ALS", "oxygen", "monitor", "defibrillator"],
                "location": "A",
                "status": "available",  # available, dispatched, en_route_scene, at_scene, en_route_hospital, breakdown
                "assigned_incident_id": None,
                "current_route": [],
                "target_destination": None,
                "eta_minutes": 0.0,
                "distance_m": 0,
                "status_log": ["AMB-101 is standing by at North Junction (A)"],
            },
            {
                "ambulance_id": "AMB-102",
                "type": "BLS",
                "capabilities": ["BLS", "oxygen", "first_aid"],
                "location": "B",
                "status": "available",
                "assigned_incident_id": None,
                "current_route": [],
                "target_destination": None,
                "eta_minutes": 0.0,
                "distance_m": 0,
                "status_log": ["AMB-102 is standing by at Central Junction (B)"],
            },
            {
                "ambulance_id": "AMB-103",
                "type": "ALS",
                "capabilities": ["ALS", "oxygen", "monitor"],
                "location": "F",
                "status": "available",
                "assigned_incident_id": None,
                "current_route": [],
                "target_destination": None,
                "eta_minutes": 0.0,
                "distance_m": 0,
                "status_log": ["AMB-103 is standing by at West Junction (F)"],
            },
            {
                "ambulance_id": "AMB-104",
                "type": "ALS",
                "capabilities": ["ALS", "oxygen", "monitor", "ventilator"],
                "location": "D",
                "status": "available",
                "assigned_incident_id": None,
                "current_route": [],
                "target_destination": None,
                "eta_minutes": 0.0,
                "distance_m": 0,
                "status_log": ["AMB-104 is standing by at South Junction (D)"],
            },
            {
                "ambulance_id": "AMB-105",
                "type": "BLS",
                "capabilities": ["BLS", "oxygen", "stretcher"],
                "location": "C",
                "status": "available",
                "assigned_incident_id": None,
                "current_route": [],
                "target_destination": None,
                "eta_minutes": 0.0,
                "distance_m": 0,
                "status_log": ["AMB-105 is standing by at East Junction (C)"],
            },
        ],
        "hospitals": [
            {
                "hospital_id": "HOSP-101",
                "name": "Central Trauma Hospital",
                "location": "E",
                "trauma_level": 1,
                "total_beds": 40,
                "available_beds": 5,
                "status": "open",  # open, full, diverting
                "capabilities": ["EMERGENCY", "TRAUMA", "SURGERY", "ICU"],
                "incoming_patients": [],
                "status_log": ["Central Trauma Hospital operational (5 beds available)"],
            },
            {
                "hospital_id": "HOSP-102",
                "name": "Community Hospital",
                "location": "C",
                "trauma_level": 3,
                "total_beds": 25,
                "available_beds": 3,
                "status": "open",
                "capabilities": ["EMERGENCY", "FIRST_AID"],
                "incoming_patients": [],
                "status_log": ["Community Hospital operational (3 beds available)"],
            },
            {
                "hospital_id": "HOSP-103",
                "name": "South Medical Center",
                "location": "D",
                "trauma_level": 2,
                "total_beds": 35,
                "available_beds": 2,
                "status": "open",
                "capabilities": ["EMERGENCY", "TRAUMA"],
                "incoming_patients": [],
                "status_log": ["South Medical Center operational (2 beds available)"],
            },
        ],
        "police_units": [
            {
                "unit_id": "POL-201",
                "name": "Traffic Patrol Alpha",
                "location": "B",
                "status": "patrol",  # patrol, dispatched, on_scene
                "assigned_incident_id": None,
                "route": [],
                "eta_minutes": 0.0,
                "current_task": "Routine patrol at Central Junction (B)",
            },
            {
                "unit_id": "POL-202",
                "name": "Rapid Response Bravo",
                "location": "F",
                "status": "patrol",
                "assigned_incident_id": None,
                "route": [],
                "eta_minutes": 0.0,
                "current_task": "Patrolling West Sector (F)",
            },
            {
                "unit_id": "POL-203",
                "name": "Highway Patrol Charlie",
                "location": "A",
                "status": "patrol",
                "assigned_incident_id": None,
                "route": [],
                "eta_minutes": 0.0,
                "current_task": "Stationed at North Junction (A)",
            },
        ],
        "fire_units": [
            {
                "unit_id": "FIRE-301",
                "name": "Heavy Rescue & Extrication Unit",
                "location": "D",
                "capabilities": ["extrication", "hydraulic_cutters", "stabilization"],
                "status": "available",  # available, dispatched, on_scene
                "assigned_incident_id": None,
                "route": [],
                "eta_minutes": 0.0,
                "current_task": "Stationed at Fire Station South (D)",
            },
            {
                "unit_id": "FIRE-302",
                "name": "Rapid Pumper & Hazmat Squad",
                "location": "C",
                "capabilities": ["fire_suppression", "hazmat", "foam"],
                "status": "available",
                "assigned_incident_id": None,
                "route": [],
                "eta_minutes": 0.0,
                "current_task": "Stationed at Fire Station East (C)",
            },
        ],
        "blocked_roads": [],  # list of e.g. ["B-D"]
        "notifications": [
            {
                "id": "NOTIF-INIT",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "target_role": "all",
                "target_id": None,
                "title": "System Initialized",
                "message": "RESCUE-AI multi-agency coordination network is active.",
                "level": "info",
            }
        ],
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# State Manager Class
# ---------------------------------------------------------------------------

class SystemStateManager:
    """Manages thread-safe, persistent synchronization across all interfaces."""

    _instance: Optional[SystemStateManager] = None

    def __new__(cls) -> SystemStateManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not STATE_FILE.is_file():
            self.reset_state()
        self.pipeline = RescueAIPipeline()
        self.route_agent = RouteAgent()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_state(self) -> Dict[str, Any]:
        """Read state from JSON file with lock."""
        with _LOCK:
            if not STATE_FILE.is_file():
                initial = get_initial_state()
                STATE_FILE.write_text(json.dumps(initial, indent=2), encoding="utf-8")
                return initial
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                return data
            except Exception:
                initial = get_initial_state()
                STATE_FILE.write_text(json.dumps(initial, indent=2), encoding="utf-8")
                return initial

    def save_state(self, state: Dict[str, Any]) -> None:
        """Write state to JSON file with lock."""
        with _LOCK:
            state["last_updated"] = datetime.now().isoformat(timespec="seconds")
            STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def reset_state(self) -> Dict[str, Any]:
        """Reset the system back to clean state."""
        state = get_initial_state()
        self.save_state(state)
        # Reset in-memory pipeline entities
        self.pipeline = RescueAIPipeline()
        self.route_agent = RouteAgent()
        return state

    # ------------------------------------------------------------------
    # Incident Processing & Dispatch
    # ------------------------------------------------------------------

    def report_incident(self, incident_input: Dict[str, Any]) -> Dict[str, Any]:
        """Process a newly reported incident from client form or command center.

        Runs the ML coordinator pipeline and assigns all required responders.
        """
        state = self.load_state()

        incident_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        location = incident_input.get("incident_location", "E")
        severity = incident_input.get("severity", "MEDIUM")
        num_casualties = int(incident_input.get("num_casualties", 2))
        num_severe = int(incident_input.get("num_severe", 1))
        num_non_severe = max(0, num_casualties - num_severe)

        incident_record = {
            "incident_id": incident_id,
            "location": location,
            "severity": severity,
            "num_casualties": num_casualties,
            "num_severe": num_severe,
            "num_non_severe": num_non_severe,
            "incident_type": incident_input.get("incident_type", "vehicle_collision"),
            "description": incident_input.get("additional_information", "Accident reported"),
            "reported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "dispatched",
            "reported_by": incident_input.get("reported_by", "Citizen Reporting Form"),
        }
        state["active_incident"] = incident_record
        state["incident_history"].append(incident_record)

        # Sync pipeline resources with state
        self._sync_pipeline_resources(state)

        # Run pipeline
        plan = self.pipeline.process_incident({
            "incident_location": location,
            "severity": severity,
            "num_casualties": num_casualties,
            "num_severe": num_severe,
            "num_non_severe": num_non_severe,
            "incident_type": incident_record["incident_type"],
            "additional_information": incident_record["description"],
        })
        state["active_plan"] = plan
        state["plan_history"].append(plan)

        # 1. Dispatch Ambulances
        dispatched_amb_ids = {a["ambulance_id"] for a in plan.get("dispatched_ambulances", [])}
        target_hospital = plan.get("selected_hospital", {})

        for amb in state["ambulances"]:
            if amb["ambulance_id"] in dispatched_amb_ids:
                amb["status"] = "dispatched"
                amb["assigned_incident_id"] = incident_id
                amb["target_destination"] = location

                # Calculate route from amb location -> incident
                try:
                    r1 = self.route_agent.calculate_route(amb["location"], location)
                    amb["current_route"] = r1["route"]
                    amb["eta_minutes"] = r1["eta_minutes"]
                    amb["distance_m"] = r1["distance_m"]
                except Exception:
                    amb["current_route"] = [amb["location"], location]
                    amb["eta_minutes"] = 5.0
                    amb["distance_m"] = 1000

                # Calculate subsequent route to hospital
                hosp_loc = target_hospital.get("location", "E")
                try:
                    r2 = self.route_agent.calculate_route(location, hosp_loc)
                    amb["hospital_route"] = r2["route"]
                    amb["hospital_eta_minutes"] = r2["eta_minutes"]
                except Exception:
                    amb["hospital_route"] = [location, hosp_loc]
                    amb["hospital_eta_minutes"] = 4.0

                amb["status_log"].append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] DISPATCHED to {location} "
                    f"({severity} emergency, {num_casualties} casualties)"
                )

                self._add_notification(
                    state,
                    target_role="ambulance",
                    target_id=amb["ambulance_id"],
                    title="🚨 EMERGENCY DISPATCH ASSIGNMENT",
                    message=(
                        f"Incident {incident_id} at Junction {location}: "
                        f"{severity} severity, {num_casualties} casualties. Route: {' -> '.join(amb['current_route'])}."
                    ),
                    level="warning",
                )

        # 2. Notify Destination Hospital
        hosp_id = target_hospital.get("hospital_id")
        for hosp in state["hospitals"]:
            if hosp["hospital_id"] == hosp_id:
                incoming_entry = {
                    "incident_id": incident_id,
                    "ambulances": list(dispatched_amb_ids),
                    "casualties": num_casualties,
                    "severe": num_severe,
                    "severity": severity,
                    "eta_minutes": target_hospital.get("eta_minutes", 5.0),
                    "dispatched_at": datetime.now().strftime("%H:%M:%S"),
                }
                hosp["incoming_patients"].append(incoming_entry)
                hosp["status_log"].append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] ALERT: Incoming {num_casualties} casualties "
                    f"via {', '.join(dispatched_amb_ids)} (ETA ~{target_hospital.get('eta_minutes')}m)"
                )
                self._add_notification(
                    state,
                    target_role="hospital",
                    target_id=hosp["hospital_id"],
                    title="🏥 INCOMING CASUALTY ALERT",
                    message=(
                        f"{hosp['name']}: {num_casualties} casualties incoming from Junction {location}. "
                        f"Trauma Team on standby!"
                    ),
                    level="warning",
                )

        # 3. Dispatch Nearest Police Unit (Traffic control & perimeter)
        closest_police = None
        min_police_time = 9999.0
        for p in state["police_units"]:
            if p["status"] == "patrol":
                try:
                    r = self.route_agent.calculate_route(p["location"], location)
                    if r["eta_minutes"] < min_police_time:
                        min_police_time = r["eta_minutes"]
                        closest_police = p
                except Exception:
                    pass

        if closest_police:
            closest_police["status"] = "dispatched"
            closest_police["assigned_incident_id"] = incident_id
            r = self.route_agent.calculate_route(closest_police["location"], location)
            closest_police["route"] = r["route"]
            closest_police["eta_minutes"] = r["eta_minutes"]
            closest_police["current_task"] = f"Secure perimeter & divert traffic at Junction {location}"

            self._add_notification(
                state,
                target_role="police",
                target_id=closest_police["unit_id"],
                title="🚓 POLICE DISPATCH: ACCIDENT PERIMETER",
                message=(
                    f"Proceed immediately to Junction {location} for traffic control and "
                    f"scene security. Route: {' -> '.join(r['route'])}."
                ),
                level="warning",
            )

        # 4. Dispatch Fire/Rescue Unit if High/Critical or Extrication required
        if severity in ("HIGH", "CRITICAL") or num_severe > 1:
            closest_fire = None
            min_fire_time = 9999.0
            for f in state["fire_units"]:
                if f["status"] == "available":
                    try:
                        r = self.route_agent.calculate_route(f["location"], location)
                        if r["eta_minutes"] < min_fire_time:
                            min_fire_time = r["eta_minutes"]
                            closest_fire = f
                    except Exception:
                        pass

            if closest_fire:
                closest_fire["status"] = "dispatched"
                closest_fire["assigned_incident_id"] = incident_id
                r = self.route_agent.calculate_route(closest_fire["location"], location)
                closest_fire["route"] = r["route"]
                closest_fire["eta_minutes"] = r["eta_minutes"]
                closest_fire["current_task"] = f"Heavy extrication & fire suppression at Junction {location}"

                self._add_notification(
                    state,
                    target_role="fire",
                    target_id=closest_fire["unit_id"],
                    title="🚒 FIRE & RESCUE DISPATCH: EXTRICATION",
                    message=(
                        f"{closest_fire['name']}: Deploy to Junction {location}. "
                        f"Severe entrapment/hazard reported. Route: {' -> '.join(r['route'])}."
                    ),
                    level="error",
                )

        # Broadcast admin notification
        self._add_notification(
            state,
            target_role="admin",
            target_id=None,
            title=f"Incident {incident_id} Active",
            message=f"Dispatched {len(dispatched_amb_ids)} ambulance(s) and response units to Junction {location}.",
            level="success",
        )

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Dynamic Replanning Triggers
    # ------------------------------------------------------------------

    def report_ambulance_breakdown(self, ambulance_id: str) -> Dict[str, Any]:
        """Triggered when an ambulance reports breakdown / unable to reach scene.

        Instantly initiates replanning, assigns next closest available ambulance,
        and notifies both vehicles and the command center.
        """
        state = self.load_state()

        # Find the failing ambulance
        failing_amb = next((a for a in state["ambulances"] if a["ambulance_id"] == ambulance_id), None)
        if not failing_amb:
            return state

        failing_amb["status"] = "breakdown"
        failing_amb["current_route"] = []
        failing_amb["status_log"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ MECHANICAL BREAKDOWN reported! Out of service."
        )

        # Mutate pipeline resource pool
        self.pipeline.set_ambulance_unavailable(ambulance_id)

        # Run replanning
        if state.get("active_plan"):
            updated_plan = self.pipeline.handle_dynamic_event(
                "AMBULANCE_UNAVAILABLE",
                {"ambulance_id": ambulance_id},
            )
            state["active_plan"] = updated_plan
            state["plan_history"].append(updated_plan)

            # Identify newly dispatched ambulance(s)
            old_dispatched = {a["ambulance_id"] for a in state["active_plan"].get("dispatched_ambulances", [])}
            new_dispatched = {a["ambulance_id"] for a in updated_plan.get("dispatched_ambulances", [])}
            added_ambs = new_dispatched - {ambulance_id}

            incident_loc = updated_plan.get("incident_location", "E")
            target_hosp = updated_plan.get("selected_hospital", {})

            for amb in state["ambulances"]:
                if amb["ambulance_id"] in added_ambs and amb["status"] == "available":
                    amb["status"] = "dispatched"
                    amb["assigned_incident_id"] = updated_plan.get("incident_id")
                    amb["target_destination"] = incident_loc
                    r = self.route_agent.calculate_route(amb["location"], incident_loc)
                    amb["current_route"] = r["route"]
                    amb["eta_minutes"] = r["eta_minutes"]
                    amb["distance_m"] = r["distance_m"]

                    amb["status_log"].append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ REASSIGNED to replace broken down {ambulance_id}"
                    )

                    self._add_notification(
                        state,
                        target_role="ambulance",
                        target_id=amb["ambulance_id"],
                        title="⚡ URGENT REPLANNING: REPLACEMENT ASSIGNED",
                        message=(
                            f"You have been reassigned to Junction {incident_loc} to replace {ambulance_id}. "
                            f"Proceed immediately! Route: {' -> '.join(r['route'])}."
                        ),
                        level="warning",
                    )

            # Notify Hospital of ambulance substitution
            hosp_id = target_hosp.get("hospital_id")
            for h in state["hospitals"]:
                if h["hospital_id"] == hosp_id:
                    h["status_log"].append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] REPLAN NOTICE: {ambulance_id} broke down; replaced by {', '.join(added_ambs)}"
                    )

            self._add_notification(
                state,
                target_role="all",
                target_id=None,
                title="⚠️ Dynamic Replanning Triggered",
                message=f"Ambulance {ambulance_id} reported breakdown. Auto-dispatched replacement {', '.join(added_ambs)}.",
                level="error",
            )

        self.save_state(state)
        return state

    def report_hospital_full(self, hospital_id: str) -> Dict[str, Any]:
        """Triggered when a hospital marks itself full or diverting."""
        state = self.load_state()

        hosp = next((h for h in state["hospitals"] if h["hospital_id"] == hospital_id), None)
        if hosp:
            hosp["status"] = "full"
            hosp["available_beds"] = 0
            hosp["status_log"].append(f"[{datetime.now().strftime('%H:%M:%S')}] Marked FULL / DIVERTING")

        self.pipeline.set_hospital_full(hospital_id)

        if state.get("active_plan"):
            updated_plan = self.pipeline.handle_dynamic_event(
                "HOSPITAL_FULL",
                {"hospital_id": hospital_id},
            )
            state["active_plan"] = updated_plan
            state["plan_history"].append(updated_plan)

            new_hosp = updated_plan.get("selected_hospital", {})
            new_hosp_id = new_hosp.get("hospital_id")
            new_hosp_name = new_hosp.get("name", "Alternative Hospital")

            # Update en-route ambulances with new hospital destination & route
            for amb in state["ambulances"]:
                if amb["status"] in ("dispatched", "en_route_scene", "at_scene"):
                    inc_loc = updated_plan.get("incident_location", "E")
                    new_hosp_loc = new_hosp.get("location", "C")
                    try:
                        r = self.route_agent.calculate_route(inc_loc, new_hosp_loc)
                        amb["hospital_route"] = r["route"]
                        amb["hospital_eta_minutes"] = r["eta_minutes"]
                    except Exception:
                        pass
                    amb["status_log"].append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] REROUTE ALERT: Destination changed to {new_hosp_name} ({new_hosp_id})"
                    )
                    self._add_notification(
                        state,
                        target_role="ambulance",
                        target_id=amb["ambulance_id"],
                        title="🔄 HOSPITAL REROUTE NOTICE",
                        message=f"{hospital_id} is FULL. Divert all casualties to {new_hosp_name} ({new_hosp_id})!",
                        level="warning",
                    )

            self._add_notification(
                state,
                target_role="all",
                target_id=None,
                title="🏥 Hospital Diversion In Effect",
                message=f"Hospital {hospital_id} at capacity. Casualty transport diverted to {new_hosp_name}.",
                level="warning",
            )

        self.save_state(state)
        return state

    def report_road_blockage(self, node_a: str, node_b: str) -> Dict[str, Any]:
        """Triggered by police or command center when a road segment is blocked."""
        state = self.load_state()

        road_key = f"{min(node_a, node_b)}-{max(node_a, node_b)}"
        if road_key not in state["blocked_roads"]:
            state["blocked_roads"].append(road_key)

        self.route_agent.block_road(node_a, node_b)
        self.pipeline.add_road_blockage(node_a, node_b)

        # Recalculate routes for all active units
        for amb in state["ambulances"]:
            if amb["status"] in ("dispatched", "en_route_scene"):
                try:
                    r = self.route_agent.calculate_route(amb["location"], amb["target_destination"])
                    amb["current_route"] = r["route"]
                    amb["eta_minutes"] = r["eta_minutes"]
                    amb["status_log"].append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] 🚧 Road {node_a}↔{node_b} blocked! Rerouted: {' -> '.join(r['route'])}"
                    )
                    self._add_notification(
                        state,
                        target_role="ambulance",
                        target_id=amb["ambulance_id"],
                        title="🚧 ROAD BLOCKAGE: DETOUR CALCULATED",
                        message=f"Segment {node_a}↔{node_b} impassable. Detour route: {' -> '.join(r['route'])}.",
                        level="error",
                    )
                except Exception:
                    pass

        self._add_notification(
            state,
            target_role="all",
            target_id=None,
            title="🚧 Road Blockage Active",
            message=f"Road segment {node_a} ↔ {node_b} is impassable. All units have been rerouted.",
            level="error",
        )

        self.save_state(state)
        return state

    def report_road_cleared(self, node_a: str, node_b: str) -> Dict[str, Any]:
        """Triggered by police when road blockage is cleared."""
        state = self.load_state()

        road_key = f"{min(node_a, node_b)}-{max(node_a, node_b)}"
        if road_key in state["blocked_roads"]:
            state["blocked_roads"].remove(road_key)

        self.route_agent.unblock_road(node_a, node_b)
        self.pipeline.remove_road_blockage(node_a, node_b)

        self._add_notification(
            state,
            target_role="all",
            target_id=None,
            title="✅ Road Cleared",
            message=f"Road segment {node_a} ↔ {node_b} reopened for emergency traffic.",
            level="success",
        )

        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Status Updates From Field Units
    # ------------------------------------------------------------------

    def update_ambulance_status(
        self,
        ambulance_id: str,
        new_status: str,
        new_location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update ambulance status along its mission lifecycle."""
        state = self.load_state()
        amb = next((a for a in state["ambulances"] if a["ambulance_id"] == ambulance_id), None)
        if not amb:
            return state

        old_status = amb["status"]
        amb["status"] = new_status
        if new_location:
            amb["location"] = new_location

        amb["status_log"].append(
            f"[{datetime.now().strftime('%H:%M:%S')}] Status updated: {old_status} → {new_status}"
            + (f" at Junction {new_location}" if new_location else "")
        )

        # Handle arrival at hospital
        if new_status == "transport_complete":
            amb["status"] = "available"
            amb["assigned_incident_id"] = None
            amb["current_route"] = []
            amb["status_log"].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Casualties delivered to hospital. Unit now AVAILABLE."
            )
            self._add_notification(
                state,
                target_role="admin",
                target_id=None,
                title="✅ Patient Delivery Complete",
                message=f"{ambulance_id} has delivered patients to hospital and is now available.",
                level="success",
            )

        self.save_state(state)
        return state

    def update_hospital_beds(self, hospital_id: str, available_beds: int) -> Dict[str, Any]:
        """Hospital staff updating available emergency bed capacity."""
        state = self.load_state()
        hosp = next((h for h in state["hospitals"] if h["hospital_id"] == hospital_id), None)
        if hosp:
            hosp["available_beds"] = max(0, available_beds)
            hosp["status"] = "full" if available_beds <= 0 else "open"
            hosp["status_log"].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Beds updated to {available_beds} ({hosp['status']})"
            )
            if available_beds <= 0:
                self.save_state(state)
                return self.report_hospital_full(hospital_id)

        self.save_state(state)
        return state

    def update_police_status(self, unit_id: str, status: str, location: Optional[str] = None) -> Dict[str, Any]:
        """Police unit updating field status."""
        state = self.load_state()
        pol = next((p for p in state["police_units"] if p["unit_id"] == unit_id), None)
        if pol:
            pol["status"] = status
            if location:
                pol["location"] = location
            if status == "on_scene":
                pol["current_task"] = "Perimeter secured, traffic diversion active"
        self.save_state(state)
        return state

    def update_fire_status(self, unit_id: str, status: str, location: Optional[str] = None) -> Dict[str, Any]:
        """Fire unit updating field status."""
        state = self.load_state()
        fire = next((f for f in state["fire_units"] if f["unit_id"] == unit_id), None)
        if fire:
            fire["status"] = status
            if location:
                fire["location"] = location
            if status == "on_scene":
                fire["current_task"] = "Active extrication & spill containment in progress"
        self.save_state(state)
        return state

    def resolve_incident(self, incident_id: str) -> Dict[str, Any]:
        """Command center marks an active incident as resolved/closed."""
        state = self.load_state()
        if state.get("active_incident") and state["active_incident"].get("incident_id") == incident_id:
            state["active_incident"]["status"] = "resolved"
            state["active_incident"]["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for inc in state.get("incident_history", []):
            if inc.get("incident_id") == incident_id:
                inc["status"] = "resolved"

        for amb in state.get("ambulances", []):
            if amb.get("assigned_incident_id") == incident_id:
                amb["status"] = "available"
                amb["assigned_incident_id"] = None
                amb["current_route"] = []
                amb["target_destination"] = None
                amb["status_log"].append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Incident {incident_id} RESOLVED. Unit returned to service."
                )

        for pol in state.get("police_units", []):
            if pol.get("assigned_incident_id") == incident_id:
                pol["status"] = "patrol"
                pol["assigned_incident_id"] = None
                pol["route"] = []
                pol["current_task"] = f"Routine patrol at Junction {pol['location']}"

        for fire in state.get("fire_units", []):
            if fire.get("assigned_incident_id") == incident_id:
                fire["status"] = "available"
                fire["assigned_incident_id"] = None
                fire["route"] = []
                fire["current_task"] = "On standby at station"

        self._add_notification(
            state,
            target_role="all",
            target_id=None,
            title="🏁 Incident Resolved",
            message=f"Incident {incident_id} marked RESOLVED. All units standing by.",
            level="success",
        )
        self.save_state(state)
        return state

    def manual_replan(self, reason: str = "Command Center Manual Replan") -> Dict[str, Any]:
        """Command center forcing an automated replanning pass."""
        state = self.load_state()
        inc = state.get("active_incident")
        if not inc or inc.get("status") == "resolved":
            return state

        plan = self.pipeline.process_incident({
            "incident_location": inc.get("location", "E"),
            "severity": inc.get("severity", "HIGH"),
            "num_casualties": inc.get("num_casualties", 2),
            "num_severe": inc.get("num_severe", 1),
            "num_non_severe": inc.get("num_non_severe", 1),
            "incident_type": inc.get("incident_type", "vehicle_collision"),
            "additional_information": f"Manual replan: {reason}",
        })
        state["active_plan"] = plan
        state["plan_history"].append(plan)

        self._add_notification(
            state,
            target_role="all",
            target_id=None,
            title="⚡ Manual Replanning Triggered",
            message=f"Command Center initiated global replan: {reason}",
            level="warning",
        )
        self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Notification Helper
    # ------------------------------------------------------------------

    def _add_notification(
        self,
        state: Dict[str, Any],
        target_role: str,
        target_id: Optional[str],
        title: str,
        message: str,
        level: str = "info",
    ) -> None:
        notif = {
            "id": f"NOTIF-{datetime.now().strftime('%H%M%S%f')[:10]}",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "target_role": target_role,
            "target_id": target_id,
            "title": title,
            "message": message,
            "level": level,
        }
        state["notifications"].insert(0, notif)
        if len(state["notifications"]) > 50:
            state["notifications"] = state["notifications"][:50]

    def _sync_pipeline_resources(self, state: Dict[str, Any]) -> None:
        """Sync AMBULANCES and HOSPITALS lists with state."""
        from src.rescue_ai.resource_search_agent import AMBULANCES, HOSPITALS

        # Match ambulances
        for state_amb in state["ambulances"]:
            for amb in AMBULANCES:
                if amb["ambulance_id"] == state_amb["ambulance_id"]:
                    amb["status"] = "available" if state_amb["status"] == "available" else "unavailable"
                    amb["location"] = state_amb["location"]

        # Match hospitals
        for state_hosp in state["hospitals"]:
            for hosp in HOSPITALS:
                if hosp["hospital_id"] == state_hosp["hospital_id"]:
                    hosp["available_beds"] = state_hosp["available_beds"]
                    hosp["status"] = state_hosp["status"]
