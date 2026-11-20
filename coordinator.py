"""Coordinator agent for the RESCUE-AI incident pipeline."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from types import ModuleType


BASE_DIR = Path(__file__).resolve().parent
SEVERITY_MODULE_PATHS = tuple(sorted(BASE_DIR.glob("*Severity*Resource_Demand*.py")))


def _load_severity_module():
    severity_path = next(
        (path for path in SEVERITY_MODULE_PATHS if path.is_file()),
        None,
    )
    if severity_path is None:
        raise FileNotFoundError(
            "Severity agent not found. Checked: "
            + ", ".join(str(path) for path in SEVERITY_MODULE_PATHS)
        )

    spec = importlib.util.spec_from_file_location("rescue_ai_severity", severity_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load severity agent from {severity_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoordinatorAgent:
    """Runs and combines the vision and severity agents for one incident."""

    def __init__(
        self,
        vision_loader: Optional[Callable[[], Dict[str, Any]]] = None,
        vision_runner: Optional[Callable[..., Dict[str, Any]]] = None,
        severity_analyzer: Optional[Callable[..., Dict[str, Any]]] = None,
        resource_searcher: Optional[Any] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._vision_loader = vision_loader
        self._vision_runner = vision_runner
        self._vision_module: Optional[ModuleType] = None
        self._severity_analyzer = severity_analyzer
        self._resource_searcher = resource_searcher

        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            vision_module = self.load_vision_module()
            self.output_dir = Path(vision_module.OUTPUT_DIR)
        self._vision_models: Optional[Dict[str, Any]] = None

    def load_vision_module(self) -> ModuleType:
        if self._vision_module is None:
            import vision

            self._vision_module = vision
        return self._vision_module

    def load_vision_models(self) -> Dict[str, Any]:
        if self._vision_models is None:
            if self._vision_loader is None:
                self._vision_loader = self.load_vision_module().load_models
            self._vision_models = self._vision_loader()
        return self._vision_models

    def load_severity_analyzer(self) -> Callable[..., Dict[str, Any]]:
        if self._severity_analyzer is None:
            severity_module = _load_severity_module()
            self._severity_analyzer = severity_module.analyze_accident
        return self._severity_analyzer

    def load_resource_searcher(self) -> Any:
        if self._resource_searcher is None:
            from src.rescue_ai.resource_search_agent import ResourceSearchAgent

            self._resource_searcher = ResourceSearchAgent()
        return self._resource_searcher

    def add_resource_recommendations(
        self,
        incident_data: Dict[str, Any],
        severity_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        incident_location = (
            incident_data.get("synthetic_location")
            or incident_data.get("map_location")
        )
        if not incident_location:
            return {
                "status": "NOT_ASSESSED",
                "reason": "No synthetic map location was supplied.",
                "dispatch_authorized": False,
                "ambulance_candidates": [],
                "hospital_candidates": [],
            }

        resources = severity_result.get("resource_demand", {})
        severe_count = severity_result.get("patient_statistics", {}).get(
            "severe_wound_patients",
            0,
        )
        ambulance_capabilities = ["ALS", "oxygen", "monitor"] if severe_count else ["BLS", "oxygen"]

        try:
            searcher = self.load_resource_searcher()
            ambulances = searcher.search_ambulances(
                incident_location,
                ambulance_capabilities,
            )
            hospitals = searcher.search_hospitals(
                incident_location,
                ["TRAUMA"],
            )
        except ValueError as exc:
            return {
                "status": "NOT_ASSESSED",
                "reason": str(exc),
                "dispatch_authorized": False,
                "ambulance_candidates": [],
                "hospital_candidates": [],
            }

        return {
            "status": "RECOMMENDATIONS_READY",
            "map_type": "synthetic",
            "incident_location": incident_location,
            "ambulance_capabilities": ambulance_capabilities,
            "required_resource_counts": {
                "ALS_ambulances": resources.get("ALS_ambulances", 0),
                "BLS_ambulances": resources.get("BLS_ambulances", 0),
                "paramedic_teams": resources.get("paramedic_teams", 0),
            },
            "dispatch_authorized": False,
            "ambulance_candidates": ambulances,
            "hospital_candidates": hospitals,
            "note": "Candidate recommendations only; no real dispatch is performed.",
        }

    def process_incident(
        self,
        incident_data: Dict[str, Any],
        image_bytes: bytes,
    ) -> Tuple[Dict[str, Any], Path]:
        filename = Path(incident_data["image_filename"]).name

        with tempfile.TemporaryDirectory(prefix="rescue_ai_") as temp_dir:
            image_path = Path(temp_dir) / filename
            image_path.write_bytes(image_bytes)

            if self._vision_runner is None:
                self._vision_runner = getattr(
                    self.load_vision_module(),
                    "rescue_pipeline",
                )

            vision_result = self._vision_runner(
                image_path,
                self.load_vision_models(),
            )

        severity_result = self.load_severity_analyzer()(vision_result)
        resource_routing = self.add_resource_recommendations(
            incident_data,
            severity_result,
        )

        combined_result = {
            **incident_data,
            **vision_result,
            "severity_and_resource_demand": severity_result,
            "resource_routing_recommendations": resource_routing,
            "status": "completed" if severity_result.get("status") not in (
                "invalid_input",
                "incomplete",
            ) else severity_result["status"],
        }

        report_dir = self.output_dir / image_path.stem / "json"
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "accident_detection.json"
        json_path.write_text(
            json.dumps(combined_result, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

        return combined_result, json_path
