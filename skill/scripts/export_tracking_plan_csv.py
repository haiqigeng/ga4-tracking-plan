from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from ecommerce_matrix import (
    OFFICIAL_EVENT_PARAMETERS,
    OFFICIAL_ITEM_PARAMETERS,
    event_family,
    ordered_parameters_for_events,
    parameter_availability,
    parameter_matrix_value,
    parameter_scope,
    parameter_type,
    scope_rule,
)
from tracking_plan_contract import event_parameter_bindings, primary_journey_id, source_registry

FIELDS = [
    "block",
    "journey_id",
    "journey_name",
    "journey_stage",
    "event_name",
    "classification",
    "measurement_role",
    "business_event_family",
    "official_match",
    "event_summary",
    "official_verification_status",
    "official_verification_source",
    "collection_source",
    "duplicate_risk_level",
    "page_or_component",
    "business_question",
    "analysis_use",
    "evidence_status",
    "evidence_confidence",
    "trigger",
    "data_dependencies",
    "key_event",
    "parameter_name",
    "parameter_scope",
    "parameter_type",
    "requirement",
    "classification_or_source",
    "reporting_purpose",
    "expected_value",
    "availability",
    "data_owner",
    "binding_official_gap",
    "source_path",
    "persistence_rule",
    "scope_rule",
    "implementation_notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export an analytics tracking-plan JSON contract to a readable long-format CSV.")
    parser.add_argument("plan", type=Path, help="Path to the canonical tracking-plan JSON file.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output CSV path.")
    return parser.parse_args()


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def compact_json(value: Any) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def official_match_for(event: dict[str, Any]) -> str:
    return str(event.get("official_match") or event.get("event_name") or "")


def parameter_lookup(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {param["parameter_name"]: param for param in plan.get("parameters", []) if isinstance(param, dict)}


def binding_for(event: dict[str, Any], parameter: str) -> dict[str, Any]:
    return next(
        (binding for binding in event_parameter_bindings(event) if binding.get("parameter_name") == parameter),
        {},
    )


def parameter_source(parameter: str, metadata: dict[str, Any] | None, binding: dict[str, Any] | None = None) -> str:
    if binding and str(binding.get("classification", "")).strip():
        return str(binding["classification"])
    if metadata:
        classification = str(metadata.get("classification") or metadata.get("source") or "")
        if parameter.startswith("items[].") and parameter not in OFFICIAL_ITEM_PARAMETERS and classification in {"ga4_ecommerce_parameter", "ga4_ecommerce_item_parameter"}:
            return "custom_item_parameter (metadata misclassified)"
        if not parameter.startswith("items[].") and parameter not in OFFICIAL_EVENT_PARAMETERS and classification == "ga4_ecommerce_parameter":
            return "custom_event_parameter (metadata misclassified)"
        return classification
    if parameter.startswith("items[]."):
        return "ga4_ecommerce_item_parameter" if parameter in OFFICIAL_ITEM_PARAMETERS else "custom_item_parameter"
    if parameter in OFFICIAL_EVENT_PARAMETERS:
        return "ga4_ecommerce_parameter"
    return "official_ga4_event_parameter"


def export_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    params = parameter_lookup(plan)
    sources = source_registry(plan)
    journeys = {brief["journey_id"]: brief["journey_name"] for brief in plan.get("measurement_brief", [])}
    rows: list[dict[str, Any]] = []

    for event in plan.get("events", []):
        block = event_family(event)
        journey_id = primary_journey_id(event)
        for parameter in ordered_parameters_for_events([event]):
            metadata = params.get(parameter)
            binding = binding_for(event, parameter)
            source_id = str(event.get("official_verification", {}).get("source_id", ""))
            rows.append(
                {
                    "block": block,
                    "journey_id": " | ".join(event.get("journey_ids", [journey_id])),
                    "journey_name": " | ".join(
                        journeys.get(event_journey_id, event_journey_id)
                        for event_journey_id in event.get("journey_ids", [journey_id])
                    ),
                    "journey_stage": event.get("journey_stage", ""),
                    "event_name": event.get("event_name", ""),
                    "classification": event.get("classification", ""),
                    "measurement_role": event.get("measurement_role", ""),
                    "business_event_family": event.get("business_event_family", ""),
                    "official_match": official_match_for(event),
                    "event_summary": event.get("event_summary", ""),
                    "official_verification_status": event.get("official_verification", {}).get("status", ""),
                    "official_verification_source": sources.get(source_id, {}).get("url", ""),
                    "collection_source": event.get("collection_strategy", {}).get("collection_source", ""),
                    "duplicate_risk_level": event.get("collection_strategy", {}).get("duplicate_risk", {}).get("level", ""),
                    "page_or_component": event.get("page_or_component", ""),
                    "business_question": event.get("business_question", ""),
                    "analysis_use": event.get("analysis_use", ""),
                    "evidence_status": event.get("evidence_basis", {}).get("status", ""),
                    "evidence_confidence": event.get("evidence_basis", {}).get("confidence", ""),
                    "trigger": event.get("trigger", ""),
                    "data_dependencies": compact_json(event.get("data_dependencies", [])),
                    "key_event": str(event.get("key_event", "")).lower(),
                    "parameter_name": parameter,
                    "parameter_scope": metadata.get("scope") if metadata else parameter_scope(parameter),
                    "parameter_type": metadata.get("type") if metadata else parameter_type(parameter),
                    "requirement": binding.get("requirement", ""),
                    "classification_or_source": parameter_source(parameter, metadata, binding),
                    "reporting_purpose": metadata.get("reporting_purpose", "") if metadata else "",
                    "expected_value": parameter_matrix_value(event, parameter),
                    "availability": binding.get("availability") or parameter_availability(event, parameter),
                    "data_owner": binding.get("data_owner", ""),
                    "binding_official_gap": binding.get("official_gap", ""),
                    "source_path": binding.get("source_path", ""),
                    "persistence_rule": binding.get("persistence_rule", ""),
                    "scope_rule": scope_rule(parameter),
                    "implementation_notes": event.get("implementation_notes", ""),
                }
            )
    return rows


def main() -> int:
    args = parse_args()
    plan = load_plan(args.plan)
    rows = export_rows(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
