"""
RESCUE-AI — Event-Driven Replanning Controller.

Implements dynamic replanning per the RESCUE-AI architecture (PDF §16).
When an environmental change occurs (ambulance breakdown, road blockage,
hospital at capacity, new casualties), this controller:

1. Looks up which agents are affected via the EVENT_DEPENDENCY_MAP.
2. Applies the event to the simulated environment.
3. Re-runs the affected agents in dependency order.
4. Produces an updated ResponsePlan.

Usage::

    from src.rescue_ai.replanning_controller import ReplanningController, ResponsePlan

    controller = ReplanningController()
    controller.register_agent("resource_search", my_resource_callback)
    updated_plan = controller.handle_event("AMBULANCE_UNAVAILABLE", details, plan, env)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Event ⟶ Agent dependency mapping  (from PDF §16)
# ---------------------------------------------------------------------------

EVENT_DEPENDENCY_MAP: Dict[str, List[str]] = {
    "AMBULANCE_UNAVAILABLE": ["resource_search", "route", "coordinator"],
    "ROAD_BLOCKED":          ["route", "coordinator"],
    "HOSPITAL_FULL":         ["resource_search", "route", "coordinator"],
    "CASUALTIES_INCREASED":  ["severity", "resource_demand", "resource_search", "route", "coordinator"],
    "ROAD_CLEARED":          ["route", "coordinator"],
}


# ---------------------------------------------------------------------------
# Response Plan
# ---------------------------------------------------------------------------

@dataclass
class ResponsePlan:
    """Holds the current emergency response plan."""

    incident_id: str = ""
    incident_location: str = ""
    dispatch_priority: str = "LOW"
    dispatched_ambulances: List[Dict[str, Any]] = field(default_factory=list)
    selected_hospital: Dict[str, Any] = field(default_factory=dict)
    response_actions: List[str] = field(default_factory=list)
    routes: Dict[str, Any] = field(default_factory=dict)
    severity: str = "LOW"
    num_casualties: int = 0
    num_severe: int = 0
    num_non_severe: int = 0
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    version: int = 1
    replan_history: List[Dict[str, Any]] = field(default_factory=list)
    decision_method: str = "rule_based"
    confidence: float = 1.0

    # -- helpers --

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "incident_id": self.incident_id,
            "incident_location": self.incident_location,
            "dispatch_priority": self.dispatch_priority,
            "dispatched_ambulances": self.dispatched_ambulances,
            "selected_hospital": self.selected_hospital,
            "response_actions": self.response_actions,
            "routes": self.routes,
            "severity": self.severity,
            "num_casualties": self.num_casualties,
            "num_severe": self.num_severe,
            "num_non_severe": self.num_non_severe,
            "resource_requirements": self.resource_requirements,
            "created_at": self.created_at,
            "version": self.version,
            "replan_history": self.replan_history,
            "decision_method": self.decision_method,
            "confidence": self.confidence,
        }

    def summary(self) -> str:
        """Human-readable one-paragraph summary."""
        amb_ids = [a.get("ambulance_id", "?") for a in self.dispatched_ambulances]
        hosp = self.selected_hospital.get("name", "N/A")
        lines = [
            f"=== Response Plan v{self.version} ===",
            f"Priority   : {self.dispatch_priority}",
            f"Severity   : {self.severity}",
            f"Casualties : {self.num_casualties} ({self.num_severe} severe)",
            f"Ambulances : {', '.join(amb_ids) or 'none'}",
            f"Hospital   : {hosp}",
            f"Actions    : {'; '.join(self.response_actions)}",
            f"Method     : {self.decision_method} (confidence {self.confidence:.2f})",
            f"Replans    : {len(self.replan_history)}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Replanning Controller
# ---------------------------------------------------------------------------

class ReplanningController:
    """Event-driven replanning controller.

    Register agent callbacks, then call ``handle_event()`` whenever the
    environment changes.  The controller re-runs only the agents that
    are affected by the event type, in dependency order.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, Callable[..., Any]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_agent(self, name: str, callback: Callable[..., Any]) -> None:
        """Register a callable for an agent name.

        Expected callback signature::

            callback(current_plan, environment, **kwargs) -> partial_result_dict
        """
        self._agents[name] = callback

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(
        self,
        event_type: str,
        event_details: Dict[str, Any],
        current_plan: ResponsePlan,
        environment: Any,
    ) -> ResponsePlan:
        """Process a dynamic event and return an updated plan.

        Parameters
        ----------
        event_type : one of the keys in EVENT_DEPENDENCY_MAP.
        event_details : dict of event-specific information.
        current_plan : the current ResponsePlan to update.
        environment : the SimulationEnvironment or similar object.

        Returns the updated ``ResponsePlan`` with incremented version.
        """
        if event_type not in EVENT_DEPENDENCY_MAP:
            warnings.warn(
                f"[Replanning] Unknown event type '{event_type}'; plan unchanged."
            )
            return current_plan

        affected = EVENT_DEPENDENCY_MAP[event_type]
        print(f"\n[Replanning] Event: {event_type}")
        print(f"[Replanning] Re-running agents: {affected}")

        # 1. Apply the event to the environment
        self._apply_event(event_type, event_details, environment)

        # 2. Re-run affected agents in order
        partial_results: Dict[str, Any] = {}
        for agent_name in affected:
            if agent_name not in self._agents:
                warnings.warn(
                    f"[Replanning] Agent '{agent_name}' not registered — skipping."
                )
                continue
            try:
                result = self._agents[agent_name](
                    current_plan, environment, event_type=event_type,
                    event_details=event_details, partial_results=partial_results,
                )
                partial_results[agent_name] = result
                print(f"[Replanning]   ✓ {agent_name}")
            except Exception as exc:
                warnings.warn(f"[Replanning] Agent '{agent_name}' failed: {exc}")

        # 3. Build updated plan
        new_plan = ResponsePlan(
            incident_id=current_plan.incident_id,
            incident_location=current_plan.incident_location,
            severity=partial_results.get("severity", {}).get("severity", current_plan.severity),
            num_casualties=partial_results.get("severity", {}).get(
                "num_casualties", current_plan.num_casualties),
            num_severe=partial_results.get("severity", {}).get(
                "num_severe", current_plan.num_severe),
            num_non_severe=partial_results.get("severity", {}).get(
                "num_non_severe", current_plan.num_non_severe),
            resource_requirements=partial_results.get("resource_demand", {}).get(
                "resource_requirements", current_plan.resource_requirements),
            dispatch_priority=partial_results.get("coordinator", {}).get(
                "dispatch_priority", current_plan.dispatch_priority),
            dispatched_ambulances=partial_results.get("coordinator", {}).get(
                "dispatched_ambulances", current_plan.dispatched_ambulances),
            selected_hospital=partial_results.get("coordinator", {}).get(
                "selected_hospital", current_plan.selected_hospital),
            response_actions=partial_results.get("coordinator", {}).get(
                "response_actions", current_plan.response_actions),
            routes=partial_results.get("route", current_plan.routes),
            decision_method=partial_results.get("coordinator", {}).get(
                "decision_method", current_plan.decision_method),
            confidence=partial_results.get("coordinator", {}).get(
                "confidence", current_plan.confidence),
            version=current_plan.version + 1,
            replan_history=current_plan.replan_history + [
                {
                    "version": current_plan.version + 1,
                    "event_type": event_type,
                    "event_details": event_details,
                    "agents_rerun": affected,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
            ],
        )

        return new_plan

    # ------------------------------------------------------------------
    # Event application
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_event(
        event_type: str,
        details: Dict[str, Any],
        environment: Any,
    ) -> None:
        """Mutate the environment to reflect the event."""
        if event_type == "AMBULANCE_UNAVAILABLE":
            amb_id = details.get("ambulance_id")
            if amb_id and hasattr(environment, "set_ambulance_unavailable"):
                environment.set_ambulance_unavailable(amb_id)
            elif amb_id:
                # Fallback: iterate ambulances list
                for a in getattr(environment, "ambulances", []):
                    if isinstance(a, dict) and a.get("ambulance_id") == amb_id:
                        a["status"] = "unavailable"
                    elif hasattr(a, "ambulance_id") and a.ambulance_id == amb_id:
                        a.available = False

        elif event_type == "ROAD_BLOCKED":
            node_a = details.get("node_a")
            node_b = details.get("node_b")
            if hasattr(environment, "add_road_blockage"):
                environment.add_road_blockage(node_a, node_b)

        elif event_type == "ROAD_CLEARED":
            node_a = details.get("node_a")
            node_b = details.get("node_b")
            if hasattr(environment, "remove_road_blockage"):
                environment.remove_road_blockage(node_a, node_b)

        elif event_type == "HOSPITAL_FULL":
            hosp_id = details.get("hospital_id")
            if hasattr(environment, "set_hospital_full"):
                environment.set_hospital_full(hosp_id)
            elif hosp_id:
                for h in getattr(environment, "hospitals", []):
                    if isinstance(h, dict) and h.get("hospital_id") == hosp_id:
                        h["available_beds"] = 0

        elif event_type == "CASUALTIES_INCREASED":
            pass  # handled by the severity agent callback

    # ------------------------------------------------------------------
    # Plan diff
    # ------------------------------------------------------------------

    @staticmethod
    def detect_plan_changes(
        old_plan: ResponsePlan,
        new_plan: ResponsePlan,
    ) -> Dict[str, Any]:
        """Compare two plans and return a human-readable diff."""
        changes: List[str] = []

        old_amb_ids = {a.get("ambulance_id") for a in old_plan.dispatched_ambulances}
        new_amb_ids = {a.get("ambulance_id") for a in new_plan.dispatched_ambulances}
        ambulances_changed = old_amb_ids != new_amb_ids
        if ambulances_changed:
            removed = old_amb_ids - new_amb_ids
            added = new_amb_ids - old_amb_ids
            if removed:
                changes.append(f"Removed ambulance(s): {', '.join(sorted(removed))}")
            if added:
                changes.append(f"Added ambulance(s): {', '.join(sorted(added))}")

        old_hosp = old_plan.selected_hospital.get("hospital_id")
        new_hosp = new_plan.selected_hospital.get("hospital_id")
        hospital_changed = old_hosp != new_hosp
        if hospital_changed:
            changes.append(
                f"Hospital changed: {old_hosp} → {new_hosp} "
                f"({new_plan.selected_hospital.get('name', '')})"
            )

        priority_changed = old_plan.dispatch_priority != new_plan.dispatch_priority
        if priority_changed:
            changes.append(
                f"Priority changed: {old_plan.dispatch_priority} → {new_plan.dispatch_priority}"
            )

        if not changes:
            changes.append("No significant changes detected.")

        return {
            "ambulances_changed": ambulances_changed,
            "hospital_changed": hospital_changed,
            "priority_changed": priority_changed,
            "changes": changes,
        }
