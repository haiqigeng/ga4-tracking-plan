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
AUTHENTICATION_EVENTS = {"login", "sign_up", "password_reset"}
AUTHENTICATED_AREA_TERMS = {
    "account dashboard",
    "account order",
    "authenticated",
    "client space",
    "customer space",
    "order history",
    "profile",
    "preferences",
    "reorder",
    "return",
    "wishlist",
}
FINITE_SCREENSHOT_EVENTS = {
    "header_click",
    "menu_click",
    "submenu_click",
    "footer_click",
    "login",
    "sign_up",
    "payment_error",
    "checkout_error",
    "newsletter_subscribe",
    "contact_submit",
    "catalog_request",
    "start_return",
    "cancel_order",
    "update_profile",
    "update_preferences",
    "password_reset",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate an older tracking-plan JSON file to the GA4-only v2.2 contract.")
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


def infer_access_context(event: dict[str, Any]) -> str:
    event_name = str(event.get("event_name", ""))
    if event_name in AUTHENTICATION_EVENTS:
        return "authentication_flow"
    text = " ".join(str(event.get(key, "")) for key in ("page_type", "page_or_component", "trigger", "page_url_pattern")).lower()
    if any(term in text for term in AUTHENTICATED_AREA_TERMS):
        return "authenticated_area"
    return "public"


def default_screenshot_coverage(event: dict[str, Any]) -> dict[str, Any]:
    event_name = str(event.get("event_name", ""))
    if event_name in FINITE_SCREENSHOT_EVENTS:
        return {"mode": "all_material_scenarios", "scenarios": ["primary_scenario"]}
    return {"mode": "representative", "scenarios": ["representative_example"]}


def default_screenshot_evidence(event: dict[str, Any]) -> dict[str, Any]:
    skip = gated_event(event)
    coverage = event.get("screenshot_coverage", default_screenshot_coverage(event))
    scenario = next(iter(coverage.get("scenarios", [])), "representative_example")
    return {
        "evidence_id": f"EVIDENCE-{slug(str(event.get('event_id') or event.get('event_name', 'event')))}",
        "event_ids": [str(event.get("event_id", ""))],
        "scenario_id": scenario,
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


def migrate_execution_context(plan: dict[str, Any]) -> None:
    context = plan.get("execution_context", {})
    for artifact in context.get("input_artifact_inventory", []):
        if str(artifact.get("artifact_type", "")).startswith("tracking_plan_") and artifact.get("artifact_type") not in {
            "tracking_plan_dev_doc",
            "tracking_plan_review",
        }:
            artifact["artifact_type"] = "tracking_plan_review"
    template_policy = context.get("template_policy", {})
    template_policy["preservation_requirements"] = [
        str(item).replace("five-sheet", "six-sheet").replace("five sheet", "six sheet")
        for item in template_policy.get("preservation_requirements", [])
    ]
    template_policy["allowed_changes"] = [
        str(item).replace("QA placeholders", "screenshot evidence rows")
        for item in template_policy.get("allowed_changes", [])
    ]


def migrate_document(plan: dict[str, Any]) -> None:
    document = plan.get("document", {})
    document["publish_date"] = document.get("publish_date") or document.get("created_date") or "TBD"
    for key in ("status", "created_date", "template_source"):
        document.pop(key, None)
    document["notes"] = str(document.get("notes", "")).replace("QA-ready output", "analyst-readable output")


def infer_lead_model(event_names: set[str]) -> dict[str, Any]:
    lead_names = event_names & {"generate_lead", "newsletter_subscribe", "contact_submit", "catalog_request"}
    if not lead_names:
        mode = "not_applicable"
    elif lead_names == {"generate_lead"}:
        mode = "consolidated"
    elif "generate_lead" in lead_names:
        mode = "hybrid"
    else:
        mode = "separate"
    return {
        "mode": mode,
        "rationale": "Migrated from the existing event inventory; confirm business ownership and consolidation intent.",
        "outcome_mappings": [
            {
                "outcome": name,
                "event_name": name,
                "business_owner": "Web analyst and business owner",
                "evidence_status": "inferred",
            }
            for name in sorted(lead_names)
        ],
    }


def migrate_strategy(plan: dict[str, Any]) -> None:
    strategy = plan.get("measurement_strategy", {})
    for family in strategy.get("selected_event_families", []):
        family.pop("analytics_platform", None)
    strategy["scalability_notes"] = [
        note
        for note in strategy.get("scalability_notes", [])
        if not any(term in str(note).lower() for term in ("qa_id", "recette agent", "future qa skill"))
    ]

    event_names = {str(event.get("event_name", "")) for event in plan.get("events", []) if isinstance(event, dict)}
    strategy.setdefault("lead_event_model", infer_lead_model(event_names))


def migrate_events(plan: dict[str, Any]) -> list[dict[str, Any]]:
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
        event.setdefault("access_context", infer_access_context(event))
        event.setdefault("screenshot_coverage", default_screenshot_coverage(event))
        migrated_events.append(event)
    plan["events"] = migrated_events
    return migrated_events


def migrate_parameters(plan: dict[str, Any]) -> None:
    for parameter in plan.get("parameters", []):
        parameter.setdefault("availability", "to_confirm")
        parameter.setdefault("data_owner", "Web analyst and development team")


def migrate_coverage(plan: dict[str, Any]) -> None:
    coverage = plan.get("website_coverage_map", {})
    coverage_text = " ".join(
        str(value)
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict)
        for value in brief.values()
    ).lower()
    account_applicable = bool(re.search(r"account|login|authentication|customer.?space|client.?space", coverage_text))
    coverage.setdefault(
        "authenticated_journey",
        {
            "applicable": account_applicable,
            "discovery_status": "not_attempted" if account_applicable else "not_applicable",
            "attempted_actions": [],
            "evidence": [],
            "gap_reason": "Migration cannot establish whether authenticated exploration was completed." if account_applicable else "",
        },
    )


def default_user_context() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "data_layer_object": "user_context",
        "push_timing": [],
        "ga4_user_id": {
            "enabled": False,
            "source_path": "",
            "signed_out_behavior": "not_applicable",
            "mapping_rule": "GA4 User-ID is not configured in this migrated plan.",
        },
        "user_properties": [],
        "advertising_user_data": {
            "status": "not_applicable",
            "data_layer_object": "",
            "destination": "not_applicable",
            "fields": [],
            "consent_requirements": [],
            "handling_rule": "Direct identifiers are not sent to GA4.",
        },
    }


def migrate_screenshot_evidence(plan: dict[str, Any], migrated_events: list[dict[str, Any]]) -> None:
    evidence = plan.get("screenshot_evidence", [])
    if not evidence:
        plan["screenshot_evidence"] = [default_screenshot_evidence(event) for event in migrated_events]
        return
    events = {str(event.get("event_id", "")): event for event in migrated_events}
    for row in evidence:
        if not isinstance(row, dict) or row.get("scenario_id"):
            continue
        related = [events.get(str(event_id)) for event_id in row.get("event_ids", [])]
        scenarios = [
            str(event.get("screenshot_coverage", {}).get("scenarios", ["representative_example"])[0])
            for event in related
            if isinstance(event, dict)
        ]
        row["scenario_id"] = scenarios[0] if scenarios else "representative_example"
    plan["screenshot_evidence"] = evidence


def migrate_official_sources(plan: dict[str, Any]) -> None:
    plan["documentation_sources_checked"] = [
        source
        for source in plan.get("documentation_sources_checked", [])
        if source.get("source_type") != "official"
        or any(domain in str(source.get("url", "")).lower() for domain in ("developers.google.com", "support.google.com"))
    ]


def migrate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan = json.loads(json.dumps(plan))
    plan["schema_version"] = "2.2.0"
    for key in ("analytics_platforms", "custom_definitions", "key_events", "qa_cases"):
        plan.pop(key, None)
    migrate_execution_context(plan)
    migrate_document(plan)
    migrate_strategy(plan)
    migrated_events = migrate_events(plan)
    migrate_parameters(plan)
    migrate_coverage(plan)
    plan.setdefault("user_context", default_user_context())
    migrate_screenshot_evidence(plan, migrated_events)
    migrate_official_sources(plan)
    return plan


def main() -> int:
    args = parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    if "$defs" in source:
        raise SystemExit("Schema migration is no longer supported. Migrate tracking-plan JSON documents only.")
    output = migrate_plan(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
