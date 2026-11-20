"""
RESCUE-AI — Training-data generator for the Coordinator Decision Model.

Generates thousands of synthetic emergency scenarios, computes an optimal
dispatch decision for each with a scoring-based optimiser, and writes the
(features, labels) pairs to JSON so that ``train_coordinator.py`` can learn
from them.

Run:
    python -m training.generate_dataset          # from project root
    python training/generate_dataset.py           # alternative
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Synthetic road-map helpers (re-use the project's own synthetic_map)
# ---------------------------------------------------------------------------

try:
    from src.rescue_ai.synthetic_map import create_synthetic_map
    from src.rescue_ai.route_agent import RouteAgent
except ImportError:
    create_synthetic_map = None
    RouteAgent = None


# ---------------------------------------------------------------------------
# Ambulance / hospital pools (matches resource_search_agent.py records)
# ---------------------------------------------------------------------------

_AMBULANCE_POOL = [
    {"ambulance_id": "AMB-101", "location": "A", "type": "ALS",
     "capabilities": ["ALS", "oxygen", "monitor"]},
    {"ambulance_id": "AMB-102", "location": "B", "type": "BLS",
     "capabilities": ["BLS", "oxygen"]},
    {"ambulance_id": "AMB-103", "location": "F", "type": "ALS",
     "capabilities": ["ALS", "oxygen", "monitor"]},
    {"ambulance_id": "AMB-104", "location": "D", "type": "ALS",
     "capabilities": ["ALS", "oxygen", "monitor"]},
    {"ambulance_id": "AMB-105", "location": "C", "type": "BLS",
     "capabilities": ["BLS", "oxygen"]},
    {"ambulance_id": "AMB-106", "location": "E", "type": "BLS",
     "capabilities": ["BLS", "oxygen"]},
    {"ambulance_id": "AMB-107", "location": "A", "type": "ALS",
     "capabilities": ["ALS", "oxygen", "monitor"]},
    {"ambulance_id": "AMB-108", "location": "D", "type": "BLS",
     "capabilities": ["BLS", "oxygen"]},
]

_HOSPITAL_POOL = [
    {"hospital_id": "HOSP-101", "name": "Central Trauma Hospital",
     "location": "E", "trauma_level": 1, "total_capacity": 40,
     "emergency_capacity": 10, "capabilities": ["EMERGENCY", "TRAUMA"]},
    {"hospital_id": "HOSP-102", "name": "Community Hospital",
     "location": "C", "trauma_level": 3, "total_capacity": 25,
     "emergency_capacity": 5, "capabilities": ["EMERGENCY"]},
    {"hospital_id": "HOSP-103", "name": "South Medical Center",
     "location": "D", "trauma_level": 2, "total_capacity": 35,
     "emergency_capacity": 8, "capabilities": ["EMERGENCY", "TRAUMA"]},
    {"hospital_id": "HOSP-104", "name": "West General Hospital",
     "location": "F", "trauma_level": 2, "total_capacity": 30,
     "emergency_capacity": 6, "capabilities": ["EMERGENCY", "TRAUMA"]},
    {"hospital_id": "HOSP-105", "name": "North Clinic",
     "location": "A", "trauma_level": 3, "total_capacity": 15,
     "emergency_capacity": 3, "capabilities": ["EMERGENCY"]},
]

_SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
_SEVERITY_MAP = {s: i for i, s in enumerate(_SEVERITY_LEVELS)}
_NODES = ["A", "B", "C", "D", "E", "F"]


# ---------------------------------------------------------------------------
# ETA look-up (pre-computed with RouteAgent or simple estimates)
# ---------------------------------------------------------------------------

def _build_eta_table() -> Dict[Tuple[str, str], float]:
    """Return {(origin, dest): eta_minutes} for every node pair."""
    if RouteAgent is not None:
        agent = RouteAgent()
        table = {}
        for o in _NODES:
            for d in _NODES:
                if o == d:
                    table[(o, d)] = 0.0
                    continue
                try:
                    r = agent.calculate_route(o, d)
                    table[(o, d)] = r["eta_minutes"]
                except (ValueError, Exception):
                    table[(o, d)] = 999.0
        return table
    # Fallback: uniform 5-min estimate
    return {(o, d): (0.0 if o == d else 5.0) for o in _NODES for d in _NODES}


_ETA_TABLE: Dict[Tuple[str, str], float] | None = None


def _eta(origin: str, dest: str) -> float:
    global _ETA_TABLE
    if _ETA_TABLE is None:
        _ETA_TABLE = _build_eta_table()
    return _ETA_TABLE.get((origin, dest), 999.0)


# ---------------------------------------------------------------------------
# Scenario generator
# ---------------------------------------------------------------------------

def generate_scenario(rng: random.Random | None = None) -> Dict[str, Any]:
    """Create one random emergency scenario."""
    if rng is None:
        rng = random.Random()

    incident_node = rng.choice(_NODES)
    severity = rng.choice(_SEVERITY_LEVELS)
    sev_idx = _SEVERITY_MAP[severity]

    # Casualty counts correlated with severity
    if severity == "LOW":
        num_casualties = rng.randint(1, 2)
    elif severity == "MEDIUM":
        num_casualties = rng.randint(2, 4)
    elif severity == "HIGH":
        num_casualties = rng.randint(3, 7)
    else:
        num_casualties = rng.randint(5, 12)

    num_severe = max(0, min(num_casualties, rng.randint(0, sev_idx + 1)))
    num_non_severe = num_casualties - num_severe

    # Resource requirements (mirrors Severity_n_Resource_Demand.py rules)
    als_required = num_severe
    bls_required = math.ceil(num_non_severe / 2) if num_non_severe else 0

    # Randomly make some ambulances unavailable
    available_ambulances = []
    for amb in _AMBULANCE_POOL:
        avail = rng.random() > 0.25  # 75 % chance available
        if avail:
            eta = _eta(amb["location"], incident_node)
            available_ambulances.append({
                "ambulance_id": amb["ambulance_id"],
                "location": amb["location"],
                "type": amb["type"],
                "capabilities": amb["capabilities"],
                "eta_minutes": round(eta, 2),
                "distance_km": round(eta * 0.67, 2),  # rough estimate
            })

    # Hospitals with random load
    available_hospitals = []
    for hosp in _HOSPITAL_POOL:
        load = rng.randint(0, hosp["total_capacity"])
        avail_cap = hosp["total_capacity"] - load
        eta = _eta(incident_node, hosp["location"])
        available_hospitals.append({
            "hospital_id": hosp["hospital_id"],
            "name": hosp["name"],
            "location": hosp["location"],
            "trauma_level": hosp["trauma_level"],
            "available_capacity": max(0, avail_cap),
            "emergency_capacity": hosp["emergency_capacity"],
            "capabilities": hosp["capabilities"],
            "eta_minutes": round(eta, 2),
            "distance_km": round(eta * 0.67, 2),
        })

    return {
        "incident_node": incident_node,
        "severity": severity,
        "num_casualties": num_casualties,
        "num_severe": num_severe,
        "num_non_severe": num_non_severe,
        "resource_requirements": {
            "ALS_ambulances": als_required,
            "BLS_ambulances": bls_required,
            "paramedic_teams": math.ceil(num_casualties / 10) if num_casualties else 0,
            "police_required": True,
        },
        "available_ambulances": available_ambulances,
        "available_hospitals": available_hospitals,
    }


# ---------------------------------------------------------------------------
# Optimal-decision oracle (scoring-based)
# ---------------------------------------------------------------------------

def compute_optimal_decision(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the best dispatch using a deterministic scoring strategy."""
    severity = scenario["severity"]
    reqs = scenario["resource_requirements"]
    als_needed = reqs["ALS_ambulances"]
    bls_needed = reqs["BLS_ambulances"]

    ambs = sorted(scenario["available_ambulances"], key=lambda a: a["eta_minutes"])
    als_avail = [a for a in ambs if a["type"] == "ALS"]
    bls_avail = [a for a in ambs if a["type"] == "BLS"]

    dispatched_ids: List[str] = []
    # Pick closest ALS
    for a in als_avail[:als_needed]:
        dispatched_ids.append(a["ambulance_id"])
    # Pick closest BLS
    for a in bls_avail[:bls_needed]:
        dispatched_ids.append(a["ambulance_id"])
    # If still short, pick any remaining by ETA
    remaining_needed = max(0, (als_needed + bls_needed) - len(dispatched_ids))
    if remaining_needed > 0:
        for a in ambs:
            if a["ambulance_id"] not in dispatched_ids:
                dispatched_ids.append(a["ambulance_id"])
                remaining_needed -= 1
                if remaining_needed <= 0:
                    break

    # Hospital selection: score = trauma_match * 2 + capacity_norm - distance_penalty
    best_hosp = None
    best_score = -999.0
    for h in scenario["available_hospitals"]:
        if h["available_capacity"] <= 0:
            continue
        trauma_match = 1.0 if (h["trauma_level"] <= 2 and severity in ("HIGH", "CRITICAL")) else 0.5
        cap_norm = min(1.0, h["available_capacity"] / max(1, scenario["num_casualties"]))
        dist_penalty = min(1.0, h["eta_minutes"] / 20.0)
        score = trauma_match * 2.0 + cap_norm * 1.5 - dist_penalty
        if score > best_score:
            best_score = score
            best_hosp = h["hospital_id"]

    if best_hosp is None and scenario["available_hospitals"]:
        best_hosp = scenario["available_hospitals"][0]["hospital_id"]

    priority = severity  # direct mapping for training
    actions: List[str] = []
    if severity in ("HIGH", "CRITICAL"):
        actions.append("Notify trauma center")
        actions.append("Reserve emergency capacity")
    if severity == "CRITICAL":
        actions.append("Request additional paramedic teams")
    actions.append("Dispatch police unit")

    return {
        "dispatched_ambulances": dispatched_ids,
        "selected_hospital": best_hosp,
        "dispatch_priority": priority,
        "num_dispatched": len(dispatched_ids),
        "response_actions": actions,
    }


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def scenario_to_features(scenario: Dict[str, Any]) -> List[float]:
    """Convert a scenario dict to a fixed-length 15-element feature vector."""
    sev_enc = float(_SEVERITY_MAP.get(scenario["severity"], 0))
    ambs = scenario.get("available_ambulances", [])
    hosps = scenario.get("available_hospitals", [])
    reqs = scenario.get("resource_requirements", {})

    als_avail = sum(1 for a in ambs if a.get("type") == "ALS")
    bls_avail = sum(1 for a in ambs if a.get("type") == "BLS")
    amb_etas = [a["eta_minutes"] for a in ambs] or [0.0]
    hosp_etas = [h["eta_minutes"] for h in hosps] or [0.0]
    trauma_levels = [h["trauma_level"] for h in hosps] or [3]
    hosp_caps = [h.get("available_capacity", 0) for h in hosps] or [0]

    return [
        sev_enc,
        float(scenario.get("num_casualties", 0)),
        float(scenario.get("num_severe", 0)),
        float(scenario.get("num_non_severe", 0)),
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


def decision_to_labels(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an optimal decision to classification/regression targets."""
    return {
        "priority_label": _SEVERITY_MAP.get(decision["dispatch_priority"], 0),
        "num_dispatched": decision["num_dispatched"],
        "hospital_id": decision["selected_hospital"],
    }


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------

def generate_training_data(
    n_scenarios: int = 5000,
    seed: int = 42,
) -> Tuple[List[List[float]], List[Dict[str, Any]]]:
    """Generate n training samples: (features_list, labels_list)."""
    rng = random.Random(seed)
    features_list: List[List[float]] = []
    labels_list: List[Dict[str, Any]] = []

    for _ in range(n_scenarios):
        scenario = generate_scenario(rng)
        decision = compute_optimal_decision(scenario)
        features = scenario_to_features(scenario)
        labels = decision_to_labels(decision)
        features_list.append(features)
        labels_list.append(labels)

    return features_list, labels_list


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    out_path = Path(__file__).resolve().parent / "training_data.json"

    print(f"Generating {n} training scenarios...")
    features, labels = generate_training_data(n)

    data = {"features": features, "labels": labels}
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(f"Saved {len(features)} samples to {out_path}")
    print(f"Feature vector length: {len(features[0])}")
    print(f"Label keys: {list(labels[0].keys())}")

    # Quick distribution summary
    from collections import Counter
    priority_dist = Counter(l["priority_label"] for l in labels)
    print(f"Priority distribution: { {_SEVERITY_LEVELS[k]: v for k, v in sorted(priority_dist.items())} }")
