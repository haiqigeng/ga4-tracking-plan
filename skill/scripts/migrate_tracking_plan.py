from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

GATED_TERMS = {
    "account",
    "authentication",
    "checkout",
    "connexion",
    "credential",
    "login",
    "paiement",
    "password",
    "payment",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate a v1 analytics tracking-plan JSON file to the GA4-only v2 contract.")
    parser.add_argument("source", type=Path, help="Existing tracking-plan JSON or schema file.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    return parser.parse_args()


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")
    return normalized[:72] or "EVIDENCE"


def gated_event(event: dict[str, Any]) -> bool:
    text = " ".join(
        str(event.get(key, ""))
        for key in ("event_name", "page_type", "page_or_component", "trigger", "page_url_pattern")
    ).lower()
    return any(term in text for term in GATED_TERMS)


def default_evidence_basis(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "inferred",
        "source_refs": [f"Journey coverage: {event.get('journey_id', 'unknown')}"] ,
        "confidence": "medium",
    }


def default_screenshot_evidence(event: dict[str, Any]) -> dict[str, Any]:
    skip = gated_event(event)
    return {
        "evidence_id": f"EVIDENCE-{slug(str(event.get('event_id') or event.get('event_name', 'event')))}",
        "event_ids": [str(event.get("event_id", ""))],
        "file_name": "",
        "page_or_component": str(event.get("page_or_component", "")),
        "url_or_route": str(event.get("page_url_pattern", "")),
        "capture_objective": f"Show {event.get('page_or_component', 'the relevant page or component')} for {event.get('event_name', 'the event')}.",
        "status": "skip_allowed" if skip else "capture_required",
        "shared_reason": "",
        "notes": (
            "Skip is allowed when approved credentials or a safe test environment are unavailable."
            if skip
            else "Capture a representative page state or clearly identify the tracked interaction."
        ),
    }


def migrate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan = json.loads(json.dumps(plan))
    plan["schema_version"] = "2.0.0"
    for key in ("analytics_platforms", "custom_definitions", "key_events", "qa_cases"):
        plan.pop(key, None)

    context = plan.get("execution_context", {})
    for artifact in context.get("input_artifact_inventory", []):
        if str(artifact.get("artifact_type", "")).startswith("tracking_plan_") and artifact.get("artifact_type") not in {
            "tracking_plan_dev_doc",
            "tracking_plan_review",
        }:
            artifact["artifact_type"] = "tracking_plan_review"
    template_policy = context.get("template_policy", {})
    template_policy["preservation_requirements"] = [
        str(item).replace("six-sheet", "five-sheet").replace("six sheet", "five sheet")
        for item in template_policy.get("preservation_requirements", [])
    ]
    template_policy["allowed_changes"] = [
        str(item).replace("QA placeholders", "screenshot evidence rows")
        for item in template_policy.get("allowed_changes", [])
    ]

    document = plan.get("document", {})
    document["publish_date"] = document.get("publish_date") or document.get("created_date") or "TBD"
    for key in ("status", "created_date", "template_source"):
        document.pop(key, None)
    document["notes"] = str(document.get("notes", "")).replace("QA-ready output", "analyst-readable output")

    strategy = plan.get("measurement_strategy", {})
    for family in strategy.get("selected_event_families", []):
        family.pop("analytics_platform", None)
    strategy["scalability_notes"] = [
        note
        for note in strategy.get("scalability_notes", [])
        if not any(term in str(note).lower() for term in ("qa_id", "recette agent", "future qa skill"))
    ]

    migrated_events: list[dict[str, Any]] = []
    for event in plan.get("events", []):
        if event.get("primary_platform") not in (None, "", "ga4"):
            continue
        event.pop("primary_platform", None)
        event.pop("platform_mappings", None)
        event.pop("implementation_payloads", None)
        event.pop("qa", None)
        event.pop("official_ga4_match", None)
        event.setdefault("analysis_use", str(event.get("business_question", "")))
        event.setdefault("evidence_basis", default_evidence_basis(event))
        migrated_events.append(event)
    plan["events"] = migrated_events

    for parameter in plan.get("parameters", []):
        parameter.setdefault("availability", "to_confirm")
        parameter.setdefault("data_owner", "Web analyst and development team")

    existing_evidence = plan.get("screenshot_evidence", [])
    if not existing_evidence:
        existing_evidence = [default_screenshot_evidence(event) for event in migrated_events]
    plan["screenshot_evidence"] = existing_evidence

    plan["documentation_sources_checked"] = [
        source
        for source in plan.get("documentation_sources_checked", [])
        if source.get("source_type") != "official"
        or any(domain in str(source.get("url", "")).lower() for domain in ("developers.google.com", "support.google.com"))
    ]
    return plan


def migrate_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(schema))
    schema["title"] = "GA4 tracking plan contract"
    schema["description"] = "Canonical GA4-only structure for analyst-readable, implementation-ready tracking plans."
    required = schema["required"]
    for key in ("analytics_platforms", "custom_definitions", "key_events", "qa_cases"):
        if key in required:
            required.remove(key)
        schema["properties"].pop(key, None)
    if "screenshot_evidence" not in required:
        required.insert(required.index("not_tracked"), "screenshot_evidence")
    schema["properties"]["screenshot_evidence"] = {
        "type": "array",
        "minItems": 1,
        "items": {"$ref": "#/$defs/screenshotEvidence"},
    }

    defs = schema["$defs"]
    artifact_types = defs["inputArtifact"]["properties"]["artifact_type"]["enum"]
    artifact_types[:] = [
        "tracking_plan_review" if str(item).startswith("tracking_plan_") and item not in {"tracking_plan_dev_doc", "tracking_plan_review"} else item
        for item in artifact_types
    ]

    selected = defs["selectedEventFamily"]
    if "analytics_platform" in selected["required"]:
        selected["required"].remove("analytics_platform")
    selected["properties"].pop("analytics_platform", None)

    document = defs["document"]
    for key in ("status", "created_date", "template_source"):
        if key in document["required"]:
            document["required"].remove(key)
        document["properties"].pop(key, None)
    if "publish_date" not in document["required"]:
        document["required"].append("publish_date")
    document["properties"]["publish_date"] = {
        "type": "string",
        "minLength": 1,
        "description": "Publication date in YYYY-MM-DD format, or TBD while the plan remains unpublished.",
    }

    event = defs["event"]
    for key in ("primary_platform", "qa"):
        if key in event["required"]:
            event["required"].remove(key)
    for key in ("primary_platform", "platform_mappings", "implementation_payloads", "qa"):
        event["properties"].pop(key, None)
    event["properties"].pop("official_ga4_match", None)
    for key in ("analysis_use", "evidence_basis"):
        if key not in event["required"]:
            event["required"].append(key)
    event["properties"]["analysis_use"] = {"type": "string", "minLength": 1}
    event["properties"]["evidence_basis"] = {"$ref": "#/$defs/evidenceBasis"}
    event["properties"]["classification"]["enum"] = [
        "automatic",
        "enhanced_measurement",
        "recommended",
        "recommended_ecommerce",
        "custom",
    ]

    sources = defs["collectionStrategy"]["properties"]["collection_source"]["enum"]
    defs["collectionStrategy"]["properties"]["collection_source"]["enum"] = [
        item for item in sources if item in {"ga4_automatic", "ga4_enhanced_measurement", "manual_gtm", "data_layer", "gtag", "sdk", "server_side", "unknown"}
    ]

    parameter = defs["parameter"]
    for key in ("availability", "data_owner"):
        if key not in parameter["required"]:
            parameter["required"].append(key)
    parameter["properties"]["availability"] = {
        "enum": ["observed", "confirmed_available", "requires_development", "requires_backend", "to_confirm", "unavailable"]
    }
    parameter["properties"]["data_owner"] = {"type": "string", "minLength": 1}

    definitions_to_remove = {
        "platformMapping",
        "implementationPayload",
        "qa",
        "customDefinition",
        "keyEvent",
        "qaCase",
        "qaStatus",
        "analyticsPlatform",
    }
    for key in definitions_to_remove:
        defs.pop(key, None)

    allowed_parameter_classes = [
        "ga4_auto_collected_parameter",
        "ga4_native_parameter",
        "ga4_recommended_parameter",
        "ga4_ecommerce_parameter",
        "ga4_ecommerce_item_parameter",
        "custom_event_parameter",
        "custom_item_parameter",
        "custom_user_property",
        "data_layer_variable",
        "implementation_variable",
    ]
    defs["parameterClassification"]["enum"] = allowed_parameter_classes
    defs["evidenceBasis"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "source_refs", "confidence"],
        "properties": {
            "status": {"enum": ["observed", "confirmed", "inferred", "recommended", "unavailable"]},
            "source_refs": {"$ref": "#/$defs/stringArray"},
            "confidence": {"enum": ["high", "medium", "low"]},
        },
    }
    defs["cropRectangle"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["x", "y", "width", "height"],
        "properties": {key: {"type": "integer", "minimum": 0} for key in ("x", "y", "width", "height")},
    }
    defs["annotationRectangle"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["x1", "y1", "x2", "y2"],
        "properties": {key: {"type": "integer", "minimum": 0} for key in ("x1", "y1", "x2", "y2")},
    }
    defs["screenshotEvidence"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "evidence_id",
            "event_ids",
            "file_name",
            "page_or_component",
            "url_or_route",
            "capture_objective",
            "status",
            "shared_reason",
            "notes",
        ],
        "properties": {
            "evidence_id": {"type": "string", "pattern": "^EVIDENCE-[A-Z0-9-]{2,80}$"},
            "event_ids": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "minLength": 1}},
            "file_name": {"type": "string"},
            "page_or_component": {"type": "string", "minLength": 1},
            "url_or_route": {"type": "string", "minLength": 1},
            "capture_objective": {"type": "string", "minLength": 1},
            "status": {"enum": ["capture_required", "captured", "shared_evidence", "skip_allowed", "not_needed", "blocked"]},
            "shared_reason": {"type": "string"},
            "crop": {"$ref": "#/$defs/cropRectangle"},
            "annotation": {"$ref": "#/$defs/annotationRectangle"},
            "notes": {"type": "string"},
        },
    }
    return schema


def main() -> int:
    args = parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    output = migrate_schema(source) if "$defs" in source else migrate_plan(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
