"""
RESCUE-AI — Coordinator Agent (Trained Decision Model).

This is the **core innovation** of RESCUE-AI: a lightweight trained ML model
that replaces LLM-based coordination.  It receives the full incident state
(severity, casualties, candidate ambulances, candidate hospitals, road
conditions) and outputs a dispatch decision.

When trained models are available it uses them; otherwise it falls back to
deterministic rule-based decisions so the pipeline always works.

Usage::

    from src.rescue_ai.coordinator_agent import CoordinatorDecisionAgent

    agent = CoordinatorDecisionAgent()
    decision = agent.make_decision(incident_state)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional


# Severity encoding shared with the training pipeline
_SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
_SEVERITY_MAP = {s: i for i, s in enumerate(_SEVERITY_LEVELS)}

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root


def _scenario_to_features(state: Dict[str, Any]) -> List[float]:
    """Convert an incident_state dict to the same 15-element feature vector
    that the training pipeline uses."""
    sev_enc = float(_SEVERITY_MAP.get(state.get("severity", "LOW"), 0))
    ambs = state.get("candidate_ambulances", [])
    hosps = state.get("candidate_hospitals", [])
    reqs = state.get("resource_requirements", {})

    als_avail = sum(1 for a in ambs if a.get("type", a.get("ambulance_type", "")) == "ALS")
    bls_avail = sum(1 for a in ambs if a.get("type", a.get("ambulance_type", "")) == "BLS")

    amb_etas = [a.get("eta_minutes", 0.0) for a in ambs] or [0.0]
    hosp_etas = [h.get("eta_minutes", 0.0) for h in hosps] or [0.0]
    trauma_levels = [h.get("trauma_level", 3) for h in hosps] or [3]
    hosp_caps = [h.get("available_capacity", h.get("available_beds", 0)) for h in hosps] or [0]

    return [
        sev_enc,
        float(state.get("num_casualties", 0)),
        float(state.get("num_severe", 0)),
        float(state.get("num_non_severe", 0)),
        float(reqs.get("ALS_ambulances", 0)),
        float(reqs.get("BLS_ambulances", 0)),
        float(len(ambs)),
        float(als_avail),
        float(bls_avail),
        min(amb_etas),
        sum(amb_etas) / len(amb_etas),
        float(len(hosps)),
        min(hosp_etas),
        float(min(trauma_levels)),
        float(max(hosp_caps)),
    ]


class CoordinatorDecisionAgent:
    """The Coordinator: decides which ambulances to dispatch and which
    hospital to route casualties to.

    Parameters
    ----------
    model_dir : path to directory containing ``priority_model.joblib``
        and ``dispatch_model.joblib``.  If the files do not exist the
        agent falls back to deterministic rules.
    """

    def __init__(self, model_dir: str | Path | None = None) -> None:
        if model_dir is None:
            model_dir = BASE_DIR / "training" / "trained_model"
        self._model_dir = Path(model_dir)
        self._priority_model: Any = None
        self._dispatch_model: Any = None
        self._models_loaded = False
        self._load_models()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_models(self) -> None:
        pri_path = self._model_dir / "priority_model.joblib"
        dis_path = self._model_dir / "dispatch_model.joblib"

        if pri_path.is_file() and dis_path.is_file():
            try:
                import joblib
                self._priority_model = joblib.load(pri_path)
                self._dispatch_model = joblib.load(dis_path)
                self._models_loaded = True
                print(f"[Coordinator] ML models loaded from {self._model_dir}")
            except Exception as exc:
                print(f"[Coordinator] Could not load models: {exc} — using rules")
                self._models_loaded = False
        else:
            print("[Coordinator] No trained models found — using rule-based fallback")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def make_decision(self, incident_state: Dict[str, Any]) -> Dict[str, Any]:
        """Produce a dispatch decision from the full incident state.

        Parameters
        ----------
        incident_state : dict with keys

            - severity : str
            - num_casualties : int
            - num_severe : int
            - num_non_severe : int
            - resource_requirements : dict
            - candidate_ambulances : list[dict]  (each has ambulance_id,
              type/ambulance_type, eta_minutes, distance_km/distance_m, etc.)
            - candidate_hospitals : list[dict]   (each has hospital_id,
              name, eta_minutes, trauma_level, available_capacity/available_beds)
            - road_conditions : dict (optional)

        Returns
        -------
        dict with keys dispatch_priority, dispatched_ambulances,
        selected_hospital, response_actions, decision_method, confidence.
        """
        if self._models_loaded:
            return self._ml_decision(incident_state)
        return self._rule_based_decision(incident_state)

    # ------------------------------------------------------------------
    # ML-based decision
    # ------------------------------------------------------------------

    def _ml_decision(self, state: Dict[str, Any]) -> Dict[str, Any]:
        import numpy as np

        features = np.array([_scenario_to_features(state)], dtype=np.float32)

        # Predict priority
        pri_pred = int(self._priority_model.predict(features)[0])
        pri_proba = self._priority_model.predict_proba(features)[0]
        confidence = float(max(pri_proba))
        priority = _SEVERITY_LEVELS[min(pri_pred, len(_SEVERITY_LEVELS) - 1)]

        # Predict dispatch count
        num_dispatch = max(1, int(round(self._dispatch_model.predict(features)[0])))

        # Select ambulances (closest by ETA, up to num_dispatch)
        ambs = sorted(
            state.get("candidate_ambulances", []),
            key=lambda a: a.get("eta_minutes", 999),
        )
        dispatched = []
        for a in ambs[:num_dispatch]:
            dispatched.append({
                "ambulance_id": a.get("ambulance_id", "unknown"),
                "ambulance_type": a.get("type", a.get("ambulance_type", "BLS")),
                "eta_minutes": round(a.get("eta_minutes", 0), 2),
            })

        # Select hospital (best by scoring)
        hospital = self._select_best_hospital(state, priority)

        # Response actions
        actions = self._determine_actions(priority)

        return {
            "dispatch_priority": priority,
            "dispatched_ambulances": dispatched,
            "selected_hospital": hospital,
            "response_actions": actions,
            "decision_method": "ml_model",
            "confidence": round(confidence, 4),
        }

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------

    def _rule_based_decision(self, state: Dict[str, Any]) -> Dict[str, Any]:
        severity = state.get("severity", "LOW")
        reqs = state.get("resource_requirements", {})
        als_needed = reqs.get("ALS_ambulances", 0)
        bls_needed = reqs.get("BLS_ambulances", 0)
        total_needed = max(1, als_needed + bls_needed)

        ambs = sorted(
            state.get("candidate_ambulances", []),
            key=lambda a: a.get("eta_minutes", 999),
        )

        # Pick ALS first, then BLS, then any
        als_ambs = [a for a in ambs if a.get("type", a.get("ambulance_type", "")) == "ALS"]
        bls_ambs = [a for a in ambs if a.get("type", a.get("ambulance_type", "")) == "BLS"]

        dispatched = []
        # ALS picks
        for a in als_ambs[:als_needed]:
            dispatched.append({
                "ambulance_id": a.get("ambulance_id"),
                "ambulance_type": "ALS",
                "eta_minutes": round(a.get("eta_minutes", 0), 2),
            })
        # BLS picks
        for a in bls_ambs[:bls_needed]:
            dispatched.append({
                "ambulance_id": a.get("ambulance_id"),
                "ambulance_type": "BLS",
                "eta_minutes": round(a.get("eta_minutes", 0), 2),
            })
        # Fill remaining
        picked_ids = {d["ambulance_id"] for d in dispatched}
        remaining = total_needed - len(dispatched)
        for a in ambs:
            if remaining <= 0:
                break
            aid = a.get("ambulance_id")
            if aid not in picked_ids:
                dispatched.append({
                    "ambulance_id": aid,
                    "ambulance_type": a.get("type", a.get("ambulance_type", "BLS")),
                    "eta_minutes": round(a.get("eta_minutes", 0), 2),
                })
                picked_ids.add(aid)
                remaining -= 1

        hospital = self._select_best_hospital(state, severity)
        actions = self._determine_actions(severity)

        return {
            "dispatch_priority": severity,
            "dispatched_ambulances": dispatched,
            "selected_hospital": hospital,
            "response_actions": actions,
            "decision_method": "rule_based",
            "confidence": 1.0,
        }

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_best_hospital(
        state: Dict[str, Any], priority: str,
    ) -> Dict[str, Any]:
        """Pick the best hospital by a scoring formula."""
        hosps = state.get("candidate_hospitals", [])
        if not hosps:
            return {"hospital_id": "NONE", "name": "No hospital available", "eta_minutes": 0}

        best = None
        best_score = -999.0
        for h in hosps:
            cap = h.get("available_capacity", h.get("available_beds", 0))
            if cap <= 0:
                continue
            trauma = h.get("trauma_level", 3)
            eta = h.get("eta_minutes", 999)
            trauma_match = 1.0 if (trauma <= 2 and priority in ("HIGH", "CRITICAL")) else 0.5
            cap_norm = min(1.0, cap / max(1, state.get("num_casualties", 1)))
            dist_penalty = min(1.0, eta / 20.0)
            score = trauma_match * 2.0 + cap_norm * 1.5 - dist_penalty
            if score > best_score:
                best_score = score
                best = h

        if best is None:
            best = hosps[0]

        return {
            "hospital_id": best.get("hospital_id", "unknown"),
            "name": best.get("name", "Unknown Hospital"),
            "eta_minutes": round(best.get("eta_minutes", 0), 2),
        }

    @staticmethod
    def _determine_actions(priority: str) -> List[str]:
        """Generate response actions based on priority."""
        actions = ["Dispatch police unit"]
        if priority in ("HIGH", "CRITICAL"):
            actions.insert(0, "Notify trauma center")
            actions.insert(1, "Reserve emergency capacity")
        if priority == "CRITICAL":
            actions.insert(0, "Request additional paramedic teams")
            actions.append("Alert regional emergency coordinator")
        return actions
