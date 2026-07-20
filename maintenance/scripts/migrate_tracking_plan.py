from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / "skill" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from official_ga4_catalog import (  # noqa: E402
    enrich_plan_official_semantics,
    load_catalog,
    load_parameter_library,
    load_scenario_library,
    source_id_for_url,
)
from official_source_receipt import pending_receipt  # noqa: E402

RULES_DIR = Path(__file__).resolve().parents[2] / "skill" / "references" / "03-rules"
RECOMMENDED_CATALOG = load_catalog(RULES_DIR / "library-ga4-recommended-events.json")
SCENARIO_LIBRARY = load_scenario_library(RULES_DIR / "library-ga4-event-scenarios.json")
PARAMETER_LIBRARY = load_parameter_library(RULES_DIR / "library-parameters.json")

AUTHENTICATION_EVENTS = {"login", "sign_up", "password_reset"}
EVENT_STAGE_BY_NAME = {
    "page_view": "context",
    "view_item_list": "discovery",
    "select_item": "discovery",
    "search": "discovery",
    "view_search_results": "discovery",
    "view_item": "consideration",
    "view_promotion": "consideration",
    "select_promotion": "consideration",
    "add_to_wishlist": "consideration",
    "add_to_cart": "conversion",
    "remove_from_cart": "conversion",
    "view_cart": "conversion",
    "begin_checkout": "conversion",
    "add_shipping_info": "conversion",
    "add_payment_info": "conversion",
    "purchase": "conversion",
    "generate_lead": "conversion",
    "sign_up": "conversion",
    "login": "conversion",
    "payment_error": "failure",
    "checkout_error": "failure",
    "refund": "recovery",
    "start_return": "service",
    "cancel_order": "service",
    "update_profile": "retention",
    "update_preferences": "retention",
}
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
    parser = argparse.ArgumentParser(description="Migrate an older tracking-plan JSON file to the GA4-only v3 contract.")
    parser.add_argument("source", type=Path, help="Existing tracking-plan JSON or schema file.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    return parser.parse_args()


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "-", value.upper()).strip("-")
    return normalized[:72] or "EVIDENCE"


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
        "status": "blocked",
        "shared_reason": "",
        "notes": "Screenshot capture has not been completed. Attempt Playwright MCP and update this evidence before delivery.",
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
    if template_policy.get("mode") == "hybrid_preserve_client_structure":
        template_policy["mode"] = "approved_structural_extension"
    if template_policy.get("mode") in {"strict_client_template", "approved_structural_extension"}:
        template_policy["template_diff_required"] = True
    template_policy["preservation_requirements"] = [
        str(item)
        .replace("six-sheet workbook", "five core sheets plus Screenshot Register when requested")
        .replace("six sheet workbook", "five core sheets plus Screenshot Register when requested")
        for item in template_policy.get("preservation_requirements", [])
    ]
    template_policy["allowed_changes"] = [
        str(item).replace("QA placeholders", "screenshot evidence rows")
        for item in template_policy.get("allowed_changes", [])
    ]
    context.pop("template_diff_summary", None)


def migrate_document(plan: dict[str, Any]) -> None:
    document = plan.get("document", {})
    document["publish_date"] = document.get("publish_date") or document.get("created_date") or "TBD"
    for key in ("status", "created_date", "template_source"):
        document.pop(key, None)
    document["notes"] = str(document.get("notes", "")).replace("QA-ready output", "analyst-readable output")


def migrate_language_policy(plan: dict[str, Any]) -> None:
    plan.setdefault(
        "language_policy",
        {
            "site_language_scope": "unknown",
            "site_languages": [],
            "workbook_language": "en",
            "controlled_value_language": "en",
            "technical_name_language": "en",
            "controlled_value_format": "lowercase_ascii_snake_case",
            "decision_basis": "English retained provisionally because the source plan did not record a website language decision.",
        },
    )


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
    parameters = {
        str(parameter.get("parameter_name", "")): parameter
        for parameter in plan.get("parameters", [])
        if isinstance(parameter, dict)
    }
    for display_order, event in enumerate(plan.get("events", []), 1):
        if event.get("primary_platform") not in (None, "", "ga4"):
            continue
        event.pop("primary_platform", None)
        event.pop("ga4_payload", None)
        event.pop("parameter_profile", None)
        event.pop("platform_mappings", None)
        event.pop("implementation_payloads", None)
        event.pop("qa", None)
        event.pop("official_ga4_match", None)
        event.setdefault("analysis_use", str(event.get("business_question", "")))
        event.setdefault("evidence_basis", default_evidence_basis(event))
        event.setdefault("access_context", infer_access_context(event))
        event.setdefault("screenshot_coverage", default_screenshot_coverage(event))
        legacy_journey = str(event.pop("journey_id", "")).strip()
        event.setdefault("journey_ids", [legacy_journey] if legacy_journey else ["initial_journey"])
        event.setdefault("journey_stage", EVENT_STAGE_BY_NAME.get(str(event.get("event_name", "")), "context"))
        event.setdefault("display_order", display_order)
        if "parameter_bindings" not in event:
            bindings = []
            for name in event.pop("parameters", []):
                parameter = parameters.get(str(name), {})
                requirement = str(parameter.get("required", "optional"))
                bindings.append(
                    {
                        "parameter_name": str(name),
                        "requirement": requirement,
                        "condition": str(parameter.get("value_rules", "")) if requirement == "conditional" else "",
                        "inclusion_reason": (
                            f"Official {requirement} parameter for this event."
                            if requirement != "optional"
                            else str(parameter.get("reporting_purpose", "Supports the documented analysis use for this event."))
                        ),
                        "availability": str(parameter.get("availability", "to_confirm")),
                        "data_owner": str(parameter.get("data_owner", "Web analyst and development team")),
                        "official_source_id": "",
                        "official_source_locator": "",
                    }
                )
            event["parameter_bindings"] = bindings
        migrated_events.append(event)
    plan["events"] = migrated_events
    return migrated_events


def migrate_parameters(plan: dict[str, Any]) -> None:
    controlled_language = str(plan.get("language_policy", {}).get("controlled_value_language", "und"))
    controlled_language_available = controlled_language in {"en", "fr"}
    entry_language = {True: controlled_language, False: "und"}[controlled_language_available]
    entry_mapping_method = {
        True: "normalization_only",
        False: "official_or_technical_value",
    }[controlled_language_available]
    for parameter in plan.get("parameters", []):
        existing_domain = parameter.get("value_domain")
        if isinstance(existing_domain, dict):
            for entry in existing_domain.get("entries", []):
                if not isinstance(entry, dict):
                    continue
                entry.setdefault(
                    "mapping_method",
                    "normalization_only"
                    if entry.get("language") in {controlled_language, "und"}
                    else "translated_to_controlled_language",
                )
            for key in ("required", "allowed_values", "value_provenance", "availability", "data_owner"):
                parameter.pop(key, None)
            continue
        allowed = parameter.get("allowed_values", [])
        provenance = parameter.get("value_provenance", {})
        provenance = provenance if isinstance(provenance, dict) else {}
        availability = str(parameter.get("availability", ""))
        source = str(parameter.get("source", "")).strip()
        mode = str(provenance.get("mode", ""))
        if not mode:
            mode = {
                (True, "observed"): "observed_exhaustive",
                (True, "confirmed_available"): "client_confirmed",
            }.get(
                (bool(allowed), availability),
                {True: "proposed_taxonomy", False: "governed_rule"}[bool(allowed)],
            )
        source_refs = list(provenance.get("source_refs", []))
        parameter["value_domain"] = {
            "mode": mode,
            "entries": [
                {
                    "raw_label": str(value),
                    "normalized_value": str(value),
                    "language": entry_language,
                    "source_ref": source_refs[0] if source_refs else "",
                    "mapping_method": entry_mapping_method,
                }
                for value in allowed
            ],
            "source_refs": source_refs or ([source] if source and mode in {"observed_exhaustive", "client_confirmed"} else []),
            "notes": str(provenance.get("notes") or "Migrated from existing value rules; confirm raw labels and evidence before publication."),
        }
        for key in ("required", "allowed_values", "value_provenance", "availability", "data_owner"):
            parameter.pop(key, None)


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
    recommendation = coverage.pop("playwright_recommendation", {})
    if "browser_exploration" not in coverage:
        required = not isinstance(recommendation, dict) or recommendation.get("status") != "not_needed"
        coverage["browser_exploration"] = {
            "requirement": "required" if required else "not_needed",
            "playwright_mcp_attempt": {
                "status": "not_recorded" if required else "not_required",
                "detail": "The source plan did not record an actual Playwright MCP exploration attempt."
                if required
                else "The source plan marked live browser exploration as not needed.",
            },
            "selected_browser": "",
            "journey_discovery_status": "blocked" if required else "not_needed",
            "value_discovery_status": "blocked" if required else "not_needed",
            "evidence_refs": [],
            "detail": str(recommendation.get("reason", ""))
            if isinstance(recommendation, dict) and recommendation.get("reason")
            else "Confirm browser journey and finite-value discovery before publication.",
        }


def default_user_context() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "data_layer_object": "user",
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


PAGE_FIELD_RENAMES = {
    "location": "page_location",
    "title": "page_title",
    "referrer": "page_referrer",
    "template": "page_template",
    "language": "nav_language",
    "environment": "nav_environment",
    "site_language": "nav_language",
    "site_environment": "nav_environment",
}


def migrate_datalayer_wrappers(plan: dict[str, Any]) -> None:
    for event in plan.get("events", []):
        match event:
            case {"data_layer": {"push": dict() as push} as data_layer}:
                pass
            case _:
                continue

        legacy_page = push.pop("page_data", None)
        if isinstance(legacy_page, dict):
            push.setdefault("page", {}).update(
                {
                    PAGE_FIELD_RENAMES.get(str(name), str(name)): value
                    for name, value in legacy_page.items()
                }
            )

        legacy_user = push.pop("user_context", None)
        if isinstance(legacy_user, dict):
            push.setdefault("user", {}).update(legacy_user)

        loose = {
            name: push.pop(name)
            for name in list(push)
            if name not in {"event", "page", "event_data", "ecommerce", "user"}
        }
        if loose:
            push.setdefault("event_data", {}).update(loose)

        page = push.get("page")
        if isinstance(page, dict):
            for old_name, new_name in (("site_language", "nav_language"), ("site_environment", "nav_environment")):
                if old_name in page:
                    page.setdefault(new_name, page.pop(old_name))

        data_layer.setdefault(
            "consent_timing",
            {"page_view": "core_context_before_cmp_ready"}.get(event.get("event_name"), "after_cmp_ready"),
        )

        data_layer["flush_keys"] = [
            {"page_data": "page", "user_context": "user"}.get(str(name), str(name))
            for name in data_layer.get("flush_keys", [])
        ]
        data_layer["mapping_notes"] = str(data_layer.get("mapping_notes", "")).replace("page_data", "page").replace("user_context", "user")

        for binding in filter(dict.__instancecheck__, event.get("parameter_bindings", [])):
            if binding.get("parameter_name") == "page_data.template":
                binding["parameter_name"] = "page_template"

    for parameter in plan.get("parameters", []):
        if parameter.get("parameter_name") != "page_data.template":
            continue
        parameter.update(
            {
                "parameter_name": "page_template",
                "scope": "event",
                "classification": "custom_event_parameter",
                "register_custom_definition": True,
            }
        )
        verification = parameter.get("official_verification")
        if isinstance(verification, dict):
            verification["scope_note"] = "Custom page_template event parameter; not an official GA4 parameter."

    context = plan["user_context"]
    context["data_layer_object"] = "user"
    mapping = context.get("ga4_user_id")
    if isinstance(mapping, dict):
        mapping["source_path"] = str(mapping.get("source_path", "")).replace("user_context.", "user.")
    for user_property in filter(dict.__instancecheck__, context.get("user_properties", [])):
        user_property["source_path"] = str(user_property.get("source_path", "")).replace("user_context.", "user.")


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
    for row in evidence:
        if not isinstance(row, dict):
            continue
        if row.get("status") in {"capture_required", "skip_allowed"}:
            row["status"] = "blocked"
            row["file_name"] = ""
            row["notes"] = "Screenshot capture has not been completed. Attempt Playwright MCP and update this evidence before delivery."
    plan["screenshot_evidence"] = evidence


def migrate_screenshot_capture(plan: dict[str, Any]) -> None:
    if isinstance(plan.get("screenshot_capture"), dict):
        return
    evidence = [row for row in plan.get("screenshot_evidence", []) if isinstance(row, dict)]
    statuses = {str(row.get("status", "")) for row in evidence}
    all_supplied = bool(evidence) and all(
        str(row.get("status", "")) in {"captured", "shared_evidence"} and str(row.get("file_name", "")).strip()
        for row in evidence
    )
    if statuses == {"not_needed"}:
        plan["screenshot_capture"] = {
            "requirement": "not_requested",
            "playwright_mcp_attempt": {
                "status": "not_required",
                "detail": "The source plan did not request screenshot evidence.",
            },
            "outcome": "not_requested",
            "delivery_notice": "Screenshots were not requested for this migrated plan.",
        }
    elif all_supplied:
        plan["screenshot_capture"] = {
            "requirement": "required",
            "playwright_mcp_attempt": {
                "status": "not_required",
                "detail": "Existing screenshot files were supplied with the source plan; no new browser capture was required.",
            },
            "outcome": "captured",
            "delivery_notice": "Screenshot capture is complete with images supplied by the source plan. Verify that each image is embedded before delivery.",
        }
    else:
        captured = any(status in {"captured", "shared_evidence"} for status in statuses)
        plan["screenshot_capture"] = {
            "requirement": "required",
            "playwright_mcp_attempt": {
                "status": "not_recorded",
                "detail": "The source plan does not record a Playwright MCP attempt. Run one before delivery.",
            },
            "outcome": "partially_captured" if captured else "blocked",
            "delivery_notice": (
                "Screenshot capture is partially complete: remaining evidence requires a Playwright MCP attempt before delivery."
                if captured
                else "Screenshot capture is blocked: a Playwright MCP attempt is required before delivery."
            ),
        }


def migrate_official_sources(plan: dict[str, Any]) -> None:
    sources = []
    for source in plan.get("documentation_sources_checked", []):
        if source.get("source_type") == "official" and not any(
            domain in str(source.get("url", "")).lower()
            for domain in ("developers.google.com", "support.google.com")
        ):
            continue
        url = str(source.get("url", ""))
        source["source_id"] = str(source.get("source_id") or source_id_for_url(url))
        source["checked_date"] = source.get("checked_date") or None
        source["language"] = str(source.get("language") or ("fr" if "hl=fr" in url.lower() else "en"))
        source.setdefault("content_signature", "")
        sources.append(source)
    plan["documentation_sources_checked"] = sources


def migrate_verification_blocks(plan: dict[str, Any]) -> None:
    for item in [*plan.get("events", []), *plan.get("parameters", [])]:
        if not isinstance(item, dict):
            continue
        verification = item.get("official_verification")
        if not isinstance(verification, dict):
            continue
        source_url = str(verification.pop("source_url", ""))
        trigger_url = str(verification.pop("trigger_source_url", ""))
        verification.pop("checked_date", None)
        verification.pop("source_language", None)
        verification.setdefault("source_id", source_id_for_url(source_url) if source_url else "not_applicable")
        if trigger_url:
            verification.setdefault("trigger_source_id", source_id_for_url(trigger_url))
        verification.setdefault("translation_status", "not_needed")


def migrate_user_properties(plan: dict[str, Any]) -> None:
    for item in plan.get("user_context", {}).get("user_properties", []):
        if isinstance(item, dict):
            item.pop("allowed_values", None)


def migrate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    plan = json.loads(json.dumps(plan))
    plan["schema_version"] = "3.1.0"
    for key in ("analytics_platforms", "custom_definitions", "key_events", "qa_cases"):
        plan.pop(key, None)
    migrate_execution_context(plan)
    migrate_document(plan)
    migrate_language_policy(plan)
    migrate_strategy(plan)
    migrated_events = migrate_events(plan)
    migrate_parameters(plan)
    migrate_coverage(plan)
    user_context = plan.get("user_context")
    plan["user_context"] = user_context if isinstance(user_context, dict) else default_user_context()
    migrate_user_properties(plan)
    migrate_datalayer_wrappers(plan)
    migrate_screenshot_evidence(plan, migrated_events)
    migrate_screenshot_capture(plan)
    migrate_official_sources(plan)
    migrate_verification_blocks(plan)
    plan["official_source_check"] = pending_receipt("Migration does not perform a live official-source check.")
    return enrich_plan_official_semantics(
        plan,
        RECOMMENDED_CATALOG,
        SCENARIO_LIBRARY,
        PARAMETER_LIBRARY,
        overwrite_official=True,
    )


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
