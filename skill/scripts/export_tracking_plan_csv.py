from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from ecommerce_matrix import (
    event_family,
    OFFICIAL_EVENT_PARAMETERS,
    OFFICIAL_ITEM_PARAMETERS,
    ordered_parameters_for_events,
    parameter_availability,
    parameter_matrix_value,
    parameter_scope,
    parameter_type,
    scope_rule,
)


FIELDS = [
    "block",
    "journey_id",
    "journey_name",
    "event_name",
    "classification",
    "measurement_role",
    "business_event_family",
    "official_match",
    "official_ga4_match",
    "analytics_platform",
    "platform_event_name",
    "platform_classification",
    "platform_official_match",
    "documentation_source",
    "official_verification_status",
    "official_verification_source",
    "collection_source",
    "duplicate_risk_level",
    "parameter_profile",
    "page_or_component",
    "business_question",
    "trigger",
    "data_dependencies",
    "key_event",
    "priority",
    "parameter_name",
    "parameter_scope",
    "parameter_type",
    "requirement",
    "classification_or_source",
    "reporting_purpose",
    "expected_value",
    "availability",
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
    return str(event.get("official_match") or event.get("official_ga4_match") or event.get("event_name") or "")


def primary_platform_for(event: dict[str, Any], plan: dict[str, Any]) -> str:
    if event.get("primary_platform"):
        return str(event["primary_platform"])
    platforms = plan.get("analytics_platforms", [])
    if isinstance(platforms, list) and len(platforms) == 1:
        return str(platforms[0])
    return "ga4" if event.get("ga4_payload") or event.get("official_ga4_match") else ""


def platform_event_name_for(event: dict[str, Any]) -> str:
    ga4_payload = event.get("ga4_payload", {})
    if isinstance(ga4_payload, dict) and ga4_payload.get("event_name"):
        return str(ga4_payload["event_name"])
    payloads = event.get("implementation_payloads", [])
    if isinstance(payloads, list):
        for payload in payloads:
            if isinstance(payload, dict) and payload.get("event_name"):
                return str(payload["event_name"])
    return str(event.get("event_name", ""))


def parameter_lookup(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {param["parameter_name"]: param for param in plan.get("parameters", []) if isinstance(param, dict)}


def requirement_for(event: dict[str, Any], parameter: str, metadata: dict[str, Any] | None) -> str:
    event_name = str(event.get("event_name", ""))
    if metadata and metadata.get("required"):
        return str(metadata["required"])
    if parameter == "items":
        return "required"
    if parameter in {"items[].item_id", "items[].item_name"}:
        return "one_of_required"
    if parameter == "transaction_id" and event_name in {"purchase", "refund"}:
        return "required"
    if parameter == "currency" and "value" in event.get("ga4_payload", {}).get("parameters", {}):
        return "conditional"
    if parameter == "items[].quantity":
        return "optional_default_1"
    return "optional"


def parameter_source(parameter: str, metadata: dict[str, Any] | None) -> str:
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
    journeys = {brief["journey_id"]: brief["journey_name"] for brief in plan.get("measurement_brief", [])}
    rows: list[dict[str, Any]] = []

    for event in plan.get("events", []):
        block = event_family(event)
        primary_platform = primary_platform_for(event, plan)
        for parameter in ordered_parameters_for_events([event]):
            metadata = params.get(parameter)
            rows.append(
                {
                    "block": block,
                    "journey_id": event.get("journey_id", ""),
                    "journey_name": journeys.get(event.get("journey_id", ""), event.get("journey_id", "")),
                    "event_name": event.get("event_name", ""),
                    "classification": event.get("classification", ""),
                    "measurement_role": event.get("measurement_role", ""),
                    "business_event_family": event.get("business_event_family", ""),
                    "official_match": official_match_for(event),
                    "official_ga4_match": event.get("official_ga4_match", ""),
                    "analytics_platform": primary_platform,
                    "platform_event_name": platform_event_name_for(event),
                    "platform_classification": event.get("classification", ""),
                    "platform_official_match": official_match_for(event),
                    "documentation_source": "",
                    "official_verification_status": event.get("official_verification", {}).get("status", ""),
                    "official_verification_source": event.get("official_verification", {}).get("source_url", ""),
                    "collection_source": event.get("collection_strategy", {}).get("collection_source", ""),
                    "duplicate_risk_level": event.get("collection_strategy", {}).get("duplicate_risk", {}).get("level", ""),
                    "parameter_profile": event.get("parameter_profile", {}).get("profile_id", ""),
                    "page_or_component": event.get("page_or_component", ""),
                    "business_question": event.get("business_question", ""),
                    "trigger": event.get("trigger", ""),
                    "data_dependencies": compact_json(event.get("data_dependencies", [])),
                    "key_event": str(event.get("key_event", "")).lower(),
                    "priority": event.get("priority", ""),
                    "parameter_name": parameter,
                    "parameter_scope": metadata.get("scope") if metadata else parameter_scope(parameter),
                    "parameter_type": metadata.get("type") if metadata else parameter_type(parameter),
                    "requirement": requirement_for(event, parameter, metadata),
                    "classification_or_source": parameter_source(parameter, metadata),
                    "reporting_purpose": metadata.get("reporting_purpose", "") if metadata else "",
                    "expected_value": parameter_matrix_value(event, parameter),
                    "availability": parameter_availability(event, parameter),
                    "scope_rule": scope_rule(parameter),
                    "implementation_notes": event.get("implementation_notes", ""),
                }
            )
        for mapping in event.get("platform_mappings", []):
            if not isinstance(mapping, dict):
                continue
            mapping_props = mapping.get("parameters_or_properties", {})
            if not isinstance(mapping_props, dict):
                mapping_props = {}
            mapping_products = mapping.get("items_or_products", [])
            mapping_rows: list[tuple[str, str]] = [(key, compact_json(value)) for key, value in mapping_props.items()]
            if isinstance(mapping_products, list):
                product_keys = sorted({key for item in mapping_products if isinstance(item, dict) for key in item})
                for key in product_keys:
                    values = [item.get(key) for item in mapping_products if isinstance(item, dict) and item.get(key) not in (None, "")]
                    mapping_rows.append((f"items_or_products[].{key}", " | ".join(str(value) for value in values)))
            if not mapping_rows:
                mapping_rows = [("(event mapping)", mapping.get("event_name", ""))]
            for parameter, expected_value in mapping_rows:
                rows.append(
                    {
                        "block": f"platform mapping - {mapping.get('platform', '')}",
                        "journey_id": event.get("journey_id", ""),
                        "journey_name": journeys.get(event.get("journey_id", ""), event.get("journey_id", "")),
                        "event_name": event.get("event_name", ""),
                        "classification": event.get("classification", ""),
                        "measurement_role": event.get("measurement_role", ""),
                        "business_event_family": event.get("business_event_family", ""),
                        "official_match": official_match_for(event),
                        "official_ga4_match": event.get("official_ga4_match", ""),
                        "analytics_platform": mapping.get("platform", ""),
                        "platform_event_name": mapping.get("event_name", ""),
                        "platform_classification": mapping.get("classification", ""),
                        "platform_official_match": mapping.get("official_match", ""),
                        "documentation_source": mapping.get("documentation_source", ""),
                        "official_verification_status": event.get("official_verification", {}).get("status", ""),
                        "official_verification_source": event.get("official_verification", {}).get("source_url", ""),
                        "collection_source": event.get("collection_strategy", {}).get("collection_source", ""),
                        "duplicate_risk_level": event.get("collection_strategy", {}).get("duplicate_risk", {}).get("level", ""),
                        "parameter_profile": event.get("parameter_profile", {}).get("profile_id", ""),
                        "page_or_component": event.get("page_or_component", ""),
                        "business_question": event.get("business_question", ""),
                        "trigger": event.get("trigger", ""),
                        "data_dependencies": compact_json(event.get("data_dependencies", [])),
                        "key_event": str(event.get("key_event", "")).lower(),
                        "priority": event.get("priority", ""),
                        "parameter_name": parameter,
                        "parameter_scope": "event",
                        "parameter_type": "platform_property",
                        "requirement": "see_platform_documentation",
                        "classification_or_source": mapping.get("classification", ""),
                        "reporting_purpose": "Platform-specific mapping property used to keep analytics-tool schemas separate.",
                        "expected_value": expected_value,
                        "availability": "platform_mapping",
                        "scope_rule": "Use only for the mapped analytics platform; do not mix schemas across tools.",
                        "implementation_notes": mapping.get("implementation_notes", event.get("implementation_notes", "")),
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
