from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

FIXTURE = Path(__file__).resolve().parents[1] / "references" / "03-rules" / "example-ga4-tracking-plan.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a focused GA4 tracking-plan JSON draft from one initial journey.")
    parser.add_argument("url", help="Representative public URL for the initial journey.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--title", default="GA4 tracking plan draft", help="Human document title.")
    parser.add_argument("--owner", default="TBD", help="Human owner shown in the workbook.")
    parser.add_argument("--journey-name", default="Initial journey", help="Human journey name.")
    parser.add_argument("--journey-id", help="Stable lowercase journey ID. Derived from the journey name when omitted.")
    parser.add_argument("--plan-id", help="Stable lowercase plan ID. Derived from the title when omitted.")
    parser.add_argument(
        "--screenshots",
        choices=("required", "not_requested"),
        default="required",
        help="Use not_requested only when the requester explicitly excludes screenshots.",
    )
    return parser.parse_args()


def identifier(value: str, fallback: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return normalized or fallback


def validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The initial URL must be an absolute http:// or https:// URL.")
    return value


def no_user_context() -> dict:
    return {
        "status": "not_applicable",
        "data_layer_object": "user_context",
        "push_timing": [],
        "ga4_user_id": {
            "enabled": False,
            "source_path": "",
            "signed_out_behavior": "not_applicable",
            "mapping_rule": "Authenticated user context is outside this initial scaffold until website discovery confirms it.",
        },
        "user_properties": [],
        "advertising_user_data": {
            "status": "not_applicable",
            "data_layer_object": "",
            "destination": "not_applicable",
            "fields": [],
            "consent_requirements": [],
            "handling_rule": "No advertising user data is defined in this initial GA4 scaffold.",
        },
    }


def screenshot_state(requirement: str, event_id: str, journey_id: str, journey_name: str, url: str) -> tuple[dict, dict, dict]:
    if requirement == "not_requested":
        coverage = {"mode": "not_needed", "scenarios": []}
        capture = {
            "requirement": "not_requested",
            "playwright_mcp_attempt": {"status": "not_required", "detail": "The requester explicitly excluded screenshots from this delivery."},
            "outcome": "not_requested",
            "delivery_notice": "Screenshots were explicitly excluded from this tracking-plan delivery.",
        }
        status = "not_needed"
        notes = "Screenshot evidence was explicitly excluded from this delivery."
    else:
        coverage = {"mode": "representative", "scenarios": ["representative_example"]}
        capture = {
            "requirement": "required",
            "playwright_mcp_attempt": {"status": "not_recorded", "detail": "Run Playwright MCP website exploration before final delivery."},
            "outcome": "blocked",
            "delivery_notice": "Screenshot capture remains blocked until a Playwright MCP attempt is recorded.",
        }
        status = "blocked"
        notes = "Attempt Playwright MCP and replace this blocked row with captured evidence before delivery."
    evidence = {
        "evidence_id": f"EVIDENCE-{event_id}",
        "event_ids": [event_id],
        "scenario_id": "representative_example",
        "file_name": "",
        "page_or_component": f"{journey_name} representative page",
        "url_or_route": url,
        "capture_objective": f"Show the representative page state for {journey_name}.",
        "status": status,
        "shared_reason": "",
        "notes": notes,
    }
    return coverage, capture, evidence


def initialize_plan(
    url: str,
    *,
    title: str = "GA4 tracking plan draft",
    owner: str = "TBD",
    journey_name: str = "Initial journey",
    journey_id: str | None = None,
    plan_id: str | None = None,
    screenshots: str = "required",
) -> dict:
    url = validate_url(url)
    journey_id = identifier(journey_id or journey_name, "initial_journey")
    plan_id = identifier(plan_id or title, "ga4_tracking_plan")
    event_id = f"EVT-{journey_id.upper().replace('_', '-')}-PAGE-VIEW"
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event = copy.deepcopy(next(item for item in fixture["events"] if item["event_name"] == "page_view"))
    parameter_names = set(event["parameters"])
    parameters = [copy.deepcopy(item) for item in fixture["parameters"] if item["parameter_name"] in parameter_names]
    coverage, capture, evidence = screenshot_state(screenshots, event_id, journey_id, journey_name, url)

    event.update(
        {
            "event_id": event_id,
            "journey_id": journey_id,
            "business_event_family": "page_context",
            "page_url_pattern": url,
            "page_type": "page",
            "page_or_component": f"{journey_name} representative page",
            "business_question": f"How do users enter and view the {journey_name.lower()} before continuing to meaningful actions?",
            "trigger": f"Page load or SPA route change for {url}.",
            "analysis_use": f"Measure entry and page-view context for the {journey_name.lower()} before its interaction model is completed.",
            "screenshot_coverage": coverage,
            "evidence_basis": {
                "status": "inferred",
                "source_refs": [f"Initial URL supplied: {url}"],
                "confidence": "low",
            },
        }
    )
    event["data_layer"]["push"]["page_data"].update({"location": url, "template": "page"})
    event["ga4_payload"]["parameters"].update({"page_location": "%current_url%", "page_template": "page"})
    for parameter in parameters:
        if parameter["parameter_name"] == "page_location":
            parameter["example_value"] = url
        elif parameter["parameter_name"] == "page_data.template":
            parameter.update({"example_value": "page", "allowed_values": ["page"], "reporting_purpose": "Segments behavior by the governed page template."})

    plan = {
        "schema_version": "2.4.0",
        "plan_id": plan_id,
        "execution_context": {
            "execution_mode": "greenfield_best_practice",
            "mode_reason": "Initial greenfield draft created before full website and business-journey discovery.",
            "input_artifact_inventory": [
                {
                    "artifact_type": "website_url",
                    "artifact_ref": url,
                    "role": "Seed the initial journey and website discovery.",
                    "template_relevance": "site_discovery",
                    "confidentiality_status": "public_url",
                }
            ],
            "template_policy": {
                "mode": "default_skill_template",
                "template_source": "generate_tracking_plan_workbook.py",
                "preservation_requirements": ["Keep the standard six-sheet human workbook structure stable."],
                "allowed_changes": ["Replace scaffold content with observed journeys, events, parameters, and evidence."],
                "template_diff_required": False,
            },
            "template_diff_summary": {
                "status": "not_needed",
                "summary": "Default generated workbook selected; no client template was supplied.",
                "columns_added": [],
                "columns_removed": [],
                "style_or_structure_changes": [],
            },
        },
        "document": {
            "title": title,
            "version": "v0.1",
            "owner": owner,
            "notes": "Initial analyst draft. Complete website discovery, business questions, events, parameters, and evidence before publication.",
            "publish_date": date.today().isoformat(),
        },
        "measurement_brief": [
            {
                "journey_id": journey_id,
                "journey_name": journey_name,
                "scope": f"Initial representative page at {url}; expand after website and journey discovery.",
                "url_or_route": url,
                "page_type": "page",
                "expected_user_actions": ["view the representative page", "continue to a meaningful next action"],
                "business_goal": f"Understand how the {journey_name.lower()} supports the website's business outcomes.",
                "analysis_needs": ["Measure journey entry volume", "Define meaningful downstream actions after discovery"],
                "success_signals": ["page_view"],
                "audience_or_segment_needs": ["device category", "traffic source", "consent state"],
                "data_available": ["page URL", "page title", "page referrer"],
                "implementation_context": ["GTM web container", "dataLayer", "GA4 web stream"],
                "constraints": ["Do not send direct PII", "Verify official GA4 semantics before publication"],
                "priority": "must",
                "open_questions": ["Which business outcomes and interactions belong to this journey?", "Which values are available from the website or backend?"],
            }
        ],
        "measurement_strategy": {
            "detected_archetypes": [
                {"archetype": "Generic web journey", "confidence": "low", "evidence": [f"Initial URL supplied: {url}"]}
            ],
            "page_roles": [
                {
                    "journey_id": journey_id,
                    "page_role": "Representative journey entry",
                    "business_purpose": "Provide the first observed context before deeper business and interaction analysis.",
                    "primary_success_signal": "Users view the page and continue to a meaningful downstream action.",
                }
            ],
            "selected_event_families": [
                {
                    "family_id": "page_context",
                    "family_name": "Page context",
                    "events_or_actions": ["page_view"],
                    "reason": "Page context is the minimum useful starting point for journey and acquisition analysis.",
                    "official_sources_considered": ["GA4 automatic page_view"],
                }
            ],
            "excluded_event_families": [
                {"family_name": "Unobserved interactions and outcomes", "reason": "Add only after website evidence and business analysis confirm them."}
            ],
            "custom_event_acceptance": [],
            "lead_event_model": {"mode": "not_applicable", "rationale": "No lead outcome has been observed in the initial scaffold.", "outcome_mappings": []},
            "scalability_notes": [
                "Add event families by journey instead of creating isolated click events.",
                "Reuse governed parameters and controlled English lowercase ASCII values across future journeys.",
            ],
        },
        "website_coverage_map": {
            "site_scope": "selected_pages",
            "coverage_summary": f"Initial scaffold covers only the representative URL {url}.",
            "sources_checked": [
                {"source_type": "url_list", "source_ref": url, "used_for": "Seed public website discovery.", "confidence": "low"}
            ],
            "journeys_covered": [
                {
                    "journey_id": journey_id,
                    "journey_name": journey_name,
                    "representative_urls": [url],
                    "page_templates": ["page"],
                    "key_interactions": ["page view"],
                    "coverage_status": "assumed",
                    "tracking_plan_decision": "included",
                    "evidence": [f"Initial URL supplied: {url}"],
                    "notes": "Replace assumed coverage with observed browser evidence before publication.",
                }
            ],
            "coverage_gaps": [
                {
                    "gap": "Remaining public, dynamic, transactional, and authenticated journeys have not been explored.",
                    "impact": "The scaffold is not a complete website tracking plan.",
                    "recommended_next_step": "Run browser and Playwright MCP discovery, then add only observed or client-confirmed journeys.",
                }
            ],
            "authenticated_journey": {
                "applicable": False,
                "discovery_status": "not_applicable",
                "attempted_actions": [],
                "evidence": [],
                "gap_reason": "Authentication applicability is not known in the initial selected-page scaffold.",
            },
            "playwright_recommendation": {
                "status": "required" if screenshots == "required" else "not_needed",
                "reason": "Required for website exploration and screenshot evidence before final delivery."
                if screenshots == "required"
                else "Screenshots were explicitly excluded from this delivery.",
            },
            "journeys_discovered": [
                {
                    "journey_id": journey_id,
                    "journey_name": journey_name,
                    "source_refs": [f"Initial URL supplied: {url}"],
                    "representative_urls": [url],
                    "page_templates": ["page"],
                    "key_interactions": ["page view"],
                    "decision": "include_in_plan",
                    "decision_reason": "Retain as the initial journey seed until browser evidence refines the scope.",
                }
            ],
        },
        "user_context": no_user_context(),
        "events": [event],
        "parameters": parameters,
        "screenshot_capture": capture,
        "screenshot_evidence": [evidence],
        "not_tracked": [
            {"interaction": "Interactions not yet observed", "reason": "The initializer creates a page-context scaffold, not an inferred event inventory."}
        ],
        "assumptions": ["The supplied URL is a public representative page and requires browser discovery before the plan is complete."],
        "documentation_sources_checked": [
            copy.deepcopy(item)
            for item in fixture["documentation_sources_checked"]
            if item["name"] in {"GA4 recommended events", "Google Tag Manager dataLayer"}
        ],
    }
    return plan


def main() -> int:
    args = parse_args()
    plan = initialize_plan(
        args.url,
        title=args.title,
        owner=args.owner,
        journey_name=args.journey_name,
        journey_id=args.journey_id,
        plan_id=args.plan_id,
        screenshots=args.screenshots,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    if args.screenshots == "required":
        print("Draft created. Record the Playwright MCP attempt and screenshot outcome before final validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
