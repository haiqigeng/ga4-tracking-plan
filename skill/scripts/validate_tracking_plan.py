from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from ecommerce_matrix import (
    OFFICIAL_ITEM_PARAMETERS,
)
from tracking_plan_validation_catalogs import (
    CUSTOM_CLASSIFICATIONS,
    CUSTOM_PARAMETER_CLASSIFICATIONS,
    GA4_RESERVED_PARAMETER_NAMES,
    OFFICIAL_ECOMMERCE_PARAMETER_CLASSES,
    OFFICIAL_PARAMETER_CLASSES,
    OFFICIAL_SOURCE_DOMAINS,
    REPORTING_PURPOSE_RE,
    WEAK_NOT_TRACKED_REASONS,
    WEAK_REPORTING_PURPOSES,
    WEAK_VALUE_RULES,
    default_schema_path,
    load_ga4_catalog,
    load_json,
)
from tracking_plan_validation_common import check_duplicates, check_official_verification, governed_sensitive_implementation_parameter
from tracking_plan_validation_delivery import check_delivery_rules
from tracking_plan_validation_event_rules import check_event
from tracking_plan_validation_events import (
    check_ga4_name,
    check_legacy_ua_field,
    check_pii_name,
    is_ga4_event,
    should_lint_ga4_parameter_name,
)
from tracking_plan_validation_model import Issue, add_issue
from tracking_plan_validation_screenshot_capture import check_screenshot_capture, check_screenshot_evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and lint a GA4 tracking-plan JSON file.")
    parser.add_argument("plan", type=Path, help="Path to the tracking-plan JSON file.")
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Optional JSON schema path. Defaults to references/03-rules/schema-tracking-plan.json.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument("--warnings-as-errors", action="store_true", help="Exit non-zero when warnings are present.")
    return parser.parse_args()


def validate_schema(plan: dict[str, Any], schema_path: Path, issues: list[Issue]) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        add_issue(
            issues,
            "warning",
            "SCHEMA_VALIDATOR_MISSING",
            "dependencies",
            "Install requirements.txt to enable JSON Schema validation.",
        )
        return

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.path)):
        path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path)
        add_issue(issues, "error", "SCHEMA_VALIDATION", path, error.message)


def values_at_keys(value: Any, target_keys: set[str], prefix: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in target_keys:
                yield path, child
            yield from values_at_keys(child, target_keys, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from values_at_keys(child, target_keys, f"{prefix}[{index}]")


def check_execution_context(plan: dict[str, Any], issues: list[Issue]) -> None:
    context = plan.get("execution_context", {})
    if not isinstance(context, dict):
        return
    mode = str(context.get("execution_mode", ""))
    template_policy = context.get("template_policy", {})
    artifacts = context.get("input_artifact_inventory", [])
    if not isinstance(template_policy, dict):
        return

    artifact_types = {
        str(artifact.get("artifact_type", ""))
        for artifact in artifacts
        if isinstance(artifact, dict)
    }
    policy_mode = str(template_policy.get("mode", ""))
    if mode == "client_template_adaptation":
        if policy_mode not in {"strict_client_template", "hybrid_preserve_client_structure"}:
            add_issue(
                issues,
                "error",
                "CLIENT_TEMPLATE_POLICY_MISSING",
                "$.execution_context.template_policy.mode",
                "Client-template adaptation must use strict_client_template or hybrid_preserve_client_structure.",
            )
        if not (artifact_types & {"template_workbook", "client_tracking_plan", "tracking_plan_dev_doc", "tracking_plan_review", "event_inventory"}):
            add_issue(
                issues,
                "error",
                "CLIENT_TEMPLATE_ARTIFACT_MISSING",
                "$.execution_context.input_artifact_inventory",
                "Client-template adaptation needs a client template, tracking plan, development document, review plan, or event inventory artifact.",
            )
        if template_policy.get("template_diff_required") and not context.get("template_diff_summary"):
            add_issue(
                issues,
                "warning",
                "TEMPLATE_DIFF_SUMMARY_MISSING",
                "$.execution_context.template_diff_summary",
                "Strict or hybrid client-template work should include a concise template diff summary.",
            )
    if mode == "greenfield_best_practice" and policy_mode != "default_skill_template":
        add_issue(
            issues,
            "warning",
            "GREENFIELD_TEMPLATE_POLICY",
            "$.execution_context.template_policy.mode",
            "Greenfield best-practice mode should normally use default_skill_template.",
        )
    preservation = template_policy.get("preservation_requirements", [])
    if policy_mode in {"strict_client_template", "hybrid_preserve_client_structure"} and not preservation:
        add_issue(
            issues,
            "error",
            "TEMPLATE_PRESERVATION_REQUIREMENTS_MISSING",
            "$.execution_context.template_policy.preservation_requirements",
            "Client-template modes need explicit preservation requirements for sheets, columns, order, colors, or protected areas.",
        )


def check_measurement_alignment(plan: dict[str, Any], issues: list[Issue]) -> None:
    briefs = [brief for brief in plan.get("measurement_brief", []) if isinstance(brief, dict)]
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    journey_ids = {str(brief.get("journey_id", "")) for brief in briefs if brief.get("journey_id")}
    events_by_journey: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_names_by_journey: dict[str, set[str]] = defaultdict(set)
    event_ids_by_journey: dict[str, set[str]] = defaultdict(set)

    for event_index, event in enumerate(events):
        journey_id = str(event.get("journey_id", ""))
        if journey_id:
            events_by_journey[journey_id].append(event)
            event_names_by_journey[journey_id].add(str(event.get("event_name", "")))
            event_ids_by_journey[journey_id].add(str(event.get("event_id", "")))
            if journey_id not in journey_ids:
                add_issue(
                    issues,
                    "error",
                    "EVENT_JOURNEY_UNKNOWN",
                    f"$.events[{event_index}].journey_id",
                    f"Event references unknown journey_id '{journey_id}'. Add the journey to measurement_brief or correct the event.",
                )

    for brief_index, brief in enumerate(briefs):
        journey_id = str(brief.get("journey_id", ""))
        if not journey_id:
            continue
        if not events_by_journey.get(journey_id):
            add_issue(
                issues,
                "error",
                "JOURNEY_HAS_NO_EVENTS",
                f"$.measurement_brief[{brief_index}].journey_id",
                f"Journey '{journey_id}' has no event definitions.",
            )
        covered_signals = event_names_by_journey.get(journey_id, set()) | event_ids_by_journey.get(journey_id, set())
        for signal_index, signal in enumerate(brief.get("success_signals", [])):
            signal_name = str(signal)
            if signal_name and signal_name not in covered_signals:
                add_issue(
                    issues,
                    "error",
                    "SUCCESS_SIGNAL_NOT_COVERED",
                    f"$.measurement_brief[{brief_index}].success_signals[{signal_index}]",
                    f"Success signal '{signal_name}' is not covered by an event_name or event_id in journey '{journey_id}'.",
                )


def check_strategy_page_roles(strategy: dict[str, Any], journey_ids: set[str], issues: list[Issue]) -> None:
    for index, page_role in enumerate(strategy.get("page_roles", [])):
        if not isinstance(page_role, dict):
            continue
        journey_id = str(page_role.get("journey_id", ""))
        if journey_id and journey_id not in journey_ids:
            add_issue(
                issues,
                "error",
                "STRATEGY_JOURNEY_UNKNOWN",
                f"$.measurement_strategy.page_roles[{index}].journey_id",
                f"Measurement strategy references unknown journey_id '{journey_id}'.",
            )



def check_strategy_families(selected_families: list[Any], issues: list[Issue]) -> set[str]:
    family_ids: set[str] = set()
    for index, family in enumerate(selected_families):
        if not isinstance(family, dict):
            continue
        if family.get("family_id"):
            family_ids.add(str(family["family_id"]))
        reason = str(family.get("reason", "")).strip()
        if len(reason.split()) < 6:
            add_issue(
                issues,
                "error",
                "STRATEGY_EVENT_FAMILY_REASON_WEAK",
                f"$.measurement_strategy.selected_event_families[{index}].reason",
                "Selected event families need a concrete business or platform rationale.",
            )

    return family_ids


def check_strategy_events(events: list[Any], family_ids: set[str], acceptance_names: set[str], issues: list[Issue]) -> None:
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        family_id = str(event.get("business_event_family", ""))
        if family_id and family_id not in family_ids:
            add_issue(
                issues,
                "error",
                "EVENT_FAMILY_UNKNOWN",
                f"$.events[{index}].business_event_family",
                f"Event references business_event_family '{family_id}' but it is not listed in measurement_strategy.selected_event_families.",
            )
        if event.get("classification") in CUSTOM_CLASSIFICATIONS and str(event.get("event_name", "")) not in acceptance_names:
            add_issue(
                issues,
                "error",
                "CUSTOM_EVENT_ACCEPTANCE_MISSING",
                "$.measurement_strategy.custom_event_acceptance",
                f"Custom event '{event.get('event_name')}' needs a custom_event_acceptance entry with official alternatives and business rationale.",
            )



def check_custom_event_acceptance(entries: list[Any], issues: list[Issue]) -> set[str]:
    names: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            continue
        if item.get("event_name"):
            names.add(str(item["event_name"]))
        reason = str(item.get("business_reason", "")).strip()
        alternatives = item.get("official_alternatives_considered", [])
        if len(reason.split()) < 8 or not alternatives:
            add_issue(
                issues,
                "error",
                "CUSTOM_EVENT_ACCEPTANCE_WEAK",
                f"$.measurement_strategy.custom_event_acceptance[{index}]",
                "Custom-event acceptance entries must state a concrete business reason and official alternatives considered.",
            )
    return names


def check_measurement_strategy(plan: dict[str, Any], issues: list[Issue]) -> None:
    strategy = plan.get("measurement_strategy", {})
    if not isinstance(strategy, dict):
        return
    journey_ids = {
        str(brief.get("journey_id", ""))
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict) and brief.get("journey_id")
    }
    selected_families = strategy.get("selected_event_families", [])
    acceptance = strategy.get("custom_event_acceptance", [])
    check_strategy_page_roles(strategy, journey_ids, issues)
    family_ids = check_strategy_families(selected_families if isinstance(selected_families, list) else [], issues)
    acceptance_names = check_custom_event_acceptance(acceptance if isinstance(acceptance, list) else [], issues)
    events = plan.get("events", [])
    check_strategy_events(events if isinstance(events, list) else [], family_ids, acceptance_names, issues)


def check_covered_journeys(coverage: dict[str, Any], journey_ids: set[str], issues: list[Issue]) -> tuple[set[str], set[str]]:
    covered_ids: set[str] = set()
    included_ids: set[str] = set()
    for index, item in enumerate(coverage.get("journeys_covered", [])):
        if not isinstance(item, dict):
            continue
        journey_id = str(item.get("journey_id", ""))
        if journey_id:
            covered_ids.add(journey_id)
            if item.get("tracking_plan_decision") == "included":
                included_ids.add(journey_id)
            if journey_id not in journey_ids:
                add_issue(issues, "error", "COVERAGE_JOURNEY_UNKNOWN", f"$.website_coverage_map.journeys_covered[{index}].journey_id", f"Coverage map references unknown journey_id '{journey_id}'.")
        if item.get("tracking_plan_decision") != "included":
            continue
        if item.get("coverage_status") in {"blocked", "out_of_scope"}:
            add_issue(issues, "error", "COVERAGE_INCLUDED_BUT_NOT_COVERED", f"$.website_coverage_map.journeys_covered[{index}].coverage_status", "Included journeys cannot be marked blocked or out_of_scope.")
        for field in ("representative_urls", "page_templates", "key_interactions", "evidence"):
            values = item.get(field, [])
            if not isinstance(values, list) or not any(str(value).strip() for value in values):
                add_issue(issues, "error", "COVERAGE_INCLUDED_EVIDENCE_MISSING", f"$.website_coverage_map.journeys_covered[{index}].{field}", f"Included journeys need non-empty {field} so analysts and developers can understand coverage.")
    return covered_ids, included_ids


def check_discovered_journeys(coverage: dict[str, Any], journey_ids: set[str], included_ids: set[str], issues: list[Issue]) -> None:
    gap_text = " ".join(
        " ".join(str(value) for value in gap.values())
        for gap in coverage.get("coverage_gaps", [])
        if isinstance(gap, dict)
    ).lower()
    for index, discovered in enumerate(coverage.get("journeys_discovered", [])):
        if not isinstance(discovered, dict):
            continue
        journey_id = str(discovered.get("journey_id", ""))
        decision = str(discovered.get("decision", ""))
        path = f"$.website_coverage_map.journeys_discovered[{index}]"
        if decision == "include_in_plan" and journey_id not in journey_ids:
            add_issue(issues, "error", "DISCOVERED_JOURNEY_NOT_IN_MEASUREMENT_BRIEF", f"{path}.journey_id", f"Discovered journey '{journey_id}' is marked include_in_plan but is missing from measurement_brief.")
        if decision == "include_in_plan" and journey_id not in included_ids:
            add_issue(issues, "error", "DISCOVERED_JOURNEY_NOT_COVERED", f"{path}.journey_id", f"Discovered journey '{journey_id}' is marked include_in_plan but has no included coverage entry.")
        if decision == "needs_discovery":
            markers = f"{journey_id} {discovered.get('journey_name', '')}".lower().split()
            if not any(marker and marker in gap_text for marker in markers):
                add_issue(issues, "error", "DISCOVERED_JOURNEY_GAP_MISSING", f"{path}.decision", f"Discovered journey '{journey_id}' needs discovery but no matching coverage gap explains the risk.")


def check_measurement_brief_coverage(plan: dict[str, Any], covered_ids: set[str], issues: list[Issue]) -> None:
    for index, brief in enumerate(plan.get("measurement_brief", [])):
        if not isinstance(brief, dict):
            continue
        journey_id = str(brief.get("journey_id", ""))
        if journey_id and journey_id not in covered_ids:
            add_issue(issues, "error", "MEASUREMENT_JOURNEY_NOT_IN_COVERAGE_MAP", f"$.measurement_brief[{index}].journey_id", f"Journey '{journey_id}' must have a matching website_coverage_map.journeys_covered entry.")


def check_whole_site_coverage(coverage: dict[str, Any], issues: list[Issue]) -> None:
    if coverage.get("site_scope") != "whole_site":
        return
    source_types = {
        str(source.get("source_type", ""))
        for source in coverage.get("sources_checked", [])
        if isinstance(source, dict)
    }
    structural_sources = {"sitemap", "robots_txt", "navigation", "url_list", "page_template", "static_html", "playwright_crawl", "browser_exploration", "existing_tracking_plan"}
    if not source_types & structural_sources:
        add_issue(issues, "error", "WHOLE_SITE_COVERAGE_SOURCE_MISSING", "$.website_coverage_map.sources_checked", "Whole-site plans need at least one structural source such as sitemap, navigation, URL list, page templates, static HTML, browser exploration, Playwright, or existing tracking files.")
    if not coverage.get("journeys_discovered"):
        add_issue(issues, "error", "WHOLE_SITE_DISCOVERED_JOURNEYS_MISSING", "$.website_coverage_map.journeys_discovered", "Whole-site plans must list discovered journeys and include/exclude/needs-discovery decisions.")


def check_website_coverage_map(plan: dict[str, Any], issues: list[Issue]) -> None:
    coverage = plan.get("website_coverage_map", {})
    if not isinstance(coverage, dict):
        return
    journey_ids = {
        str(brief.get("journey_id", ""))
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict) and brief.get("journey_id")
    }
    covered_ids, included_ids = check_covered_journeys(coverage, journey_ids, issues)
    check_discovered_journeys(coverage, journey_ids, included_ids, issues)
    check_measurement_brief_coverage(plan, covered_ids, issues)
    check_whole_site_coverage(coverage, issues)

def check_not_tracked_decisions(plan: dict[str, Any], issues: list[Issue]) -> None:
    not_tracked = plan.get("not_tracked", [])
    if isinstance(not_tracked, list) and not not_tracked:
        add_issue(
            issues,
            "warning",
            "NOT_TRACKED_EMPTY",
            "$.not_tracked",
            "Reusable plans should list meaningful interactions intentionally excluded from tracking.",
        )
    for index, decision in enumerate(not_tracked if isinstance(not_tracked, list) else []):
        if not isinstance(decision, dict):
            continue
        reason = str(decision.get("reason", "")).strip()
        if reason.lower().rstrip(".") in WEAK_NOT_TRACKED_REASONS or len(reason.split()) < 5:
            add_issue(
                issues,
                "error",
                "NOT_TRACKED_REASON_WEAK",
                f"$.not_tracked[{index}].reason",
                "Not-tracked decisions need a useful analyst rationale, such as noise, privacy risk, unavailable data, duplicate signal, or lack of business actionability.",
            )


def check_official_source_inventory(plan: dict[str, Any], events: list[Any], issues: list[Issue]) -> None:
    source_urls = [
        str(source.get("url", "")).lower()
        for source in plan.get("documentation_sources_checked", [])
        if isinstance(source, dict) and source.get("source_type") == "official"
    ]
    has_ga4_events = any(isinstance(event, dict) and is_ga4_event(event) for event in events)
    if has_ga4_events and not any(any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS["ga4"]) for url in source_urls):
        add_issue(issues, "error", "GA4_OFFICIAL_SOURCE_MISSING", "$.documentation_sources_checked", "GA4 plans must cite at least one official Google Analytics documentation source.")


def check_parameter_definition(param: dict[str, Any], index: int, issues: list[Issue]) -> None:
    name = str(param.get("parameter_name", ""))
    classification = param.get("classification")
    governed_sensitive = governed_sensitive_implementation_parameter(param)
    if not governed_sensitive:
        check_pii_name(name, f"$.parameters[{index}].parameter_name", issues)
    check_legacy_ua_field(name, f"$.parameters[{index}].parameter_name", issues)
    check_official_verification(param.get("official_verification"), "ga4", f"$.parameters[{index}].official_verification", issues, required=classification in OFFICIAL_PARAMETER_CLASSES)
    if should_lint_ga4_parameter_name(name, param):
        check_ga4_name(name, f"$.parameters[{index}].parameter_name", "parameter", issues)
        if name in GA4_RESERVED_PARAMETER_NAMES and classification not in OFFICIAL_PARAMETER_CLASSES:
            add_issue(issues, "error", "GA4_RESERVED_PARAMETER_NAME", f"$.parameters[{index}].parameter_name", f"'{name}' is reserved/native in GA4 and must not be used as a custom parameter.")
    check_item_parameter_definition(param, index, issues)
    if param.get("pii_risk") == "high" and not governed_sensitive:
        add_issue(issues, "error", "HIGH_PII_RISK", f"$.parameters[{index}].pii_risk", f"Parameter '{name}' has high PII risk.")
    if param.get("cardinality_risk") == "high" and param.get("register_custom_definition"):
        add_issue(issues, "warning", "HIGH_CARDINALITY_CUSTOM_DIMENSION", f"$.parameters[{index}]", f"Parameter '{name}' is high-cardinality and marked for custom definition registration.")
    check_parameter_documentation(param, index, issues)


def check_item_parameter_definition(param: dict[str, Any], index: int, issues: list[Issue]) -> None:
    name = str(param.get("parameter_name", ""))
    if not name.startswith("items[]."):
        return
    classification = param.get("classification")
    if name in OFFICIAL_ITEM_PARAMETERS:
        if classification == "custom_item_parameter":
            add_issue(issues, "warning", "OFFICIAL_ITEM_PARAMETER_MISCLASSIFIED", f"$.parameters[{index}].classification", f"'{name}' is an official GA4 item parameter; classify it as ga4_ecommerce_item_parameter.")
        return
    if classification in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
        add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", f"$.parameters[{index}].classification", f"'{name}' is not an official GA4 item parameter; classify it as custom_item_parameter.")
    elif classification != "custom_item_parameter":
        add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_CLASSIFICATION", f"$.parameters[{index}].classification", f"'{name}' is item-scoped and non-official; use custom_item_parameter.")
    if param.get("scope") != "item":
        add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_SCOPE", f"$.parameters[{index}].scope", f"'{name}' must use item scope.")


def check_parameter_documentation(param: dict[str, Any], index: int, issues: list[Issue]) -> None:
    name = str(param.get("parameter_name", ""))
    classification = param.get("classification")
    purpose = str(param.get("reporting_purpose", "")).strip()
    normalized_purpose = purpose.lower().rstrip(".")
    if normalized_purpose in WEAK_REPORTING_PURPOSES or len(purpose.split()) < 5:
        add_issue(issues, "error", "PARAMETER_REPORTING_PURPOSE_WEAK", f"$.parameters[{index}].reporting_purpose", f"Parameter '{name}' needs a concrete reporting or analysis purpose.")
    elif classification in CUSTOM_PARAMETER_CLASSIFICATIONS and not REPORTING_PURPOSE_RE.search(purpose):
        add_issue(issues, "error", "CUSTOM_PARAMETER_REPORTING_PURPOSE_WEAK", f"$.parameters[{index}].reporting_purpose", f"Custom parameter '{name}' must state the analysis, segmentation, QA, or optimization use it supports.")
    rules = str(param.get("value_rules", "")).strip()
    if classification in CUSTOM_PARAMETER_CLASSIFICATIONS and (rules.lower().rstrip(".") in WEAK_VALUE_RULES or len(rules.split()) < 3):
        add_issue(issues, "error", "CUSTOM_PARAMETER_VALUE_RULES_WEAK", f"$.parameters[{index}].value_rules", f"Custom parameter '{name}' needs concrete value rules or controlled values.")
    availability = str(param.get("availability", ""))
    if availability in {"requires_development", "requires_backend", "to_confirm", "unavailable"} and len(str(param.get("data_owner", "")).split()) < 2:
        add_issue(issues, "error", "PARAMETER_DATA_OWNER_MISSING", f"$.parameters[{index}].data_owner", f"Parameter '{name}' needs a clear owner because its availability is '{availability}'.")


def validate_plan_data(plan: dict[str, Any], schema_path: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    validate_schema(plan, schema_path or default_schema_path(), issues)
    parameters = plan.get("parameters", [])
    events = plan.get("events", [])
    parameter_lookup = {
        param.get("parameter_name", ""): param
        for param in parameters
        if isinstance(param, dict)
    }
    check_duplicates(
        [event.get("event_id", "") for event in events if isinstance(event, dict)],
        "event_id",
        "$.events",
        issues,
    )
    check_execution_context(plan, issues)
    check_measurement_alignment(plan, issues)
    check_measurement_strategy(plan, issues)
    check_website_coverage_map(plan, issues)
    check_not_tracked_decisions(plan, issues)
    check_screenshot_capture(plan, issues)
    check_screenshot_evidence(plan, issues)
    check_delivery_rules(plan, issues)
    check_official_source_inventory(plan, events, issues)
    for index, param in enumerate(parameters):
        if isinstance(param, dict):
            check_parameter_definition(param, index, issues)
    ga4_catalog = load_ga4_catalog()
    for index, event in enumerate(events):
        if isinstance(event, dict):
            check_event(event, index, parameter_lookup, ga4_catalog, issues)
    return issues

def render_text(issues: list[Issue]) -> str:
    if not issues:
        return "Tracking plan validation passed with no issues."
    lines = []
    for issue in issues:
        lines.append(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    plan = load_json(args.plan)
    issues = validate_plan_data(plan, args.schema or default_schema_path())
    if args.format == "json":
        print(json.dumps([issue.__dict__ for issue in issues], indent=2, ensure_ascii=False))
    else:
        print(render_text(issues))
    has_error = any(issue.severity == "error" for issue in issues)
    has_warning = any(issue.severity == "warning" for issue in issues)
    return 1 if has_error or (args.warnings_as_errors and has_warning) else 0


if __name__ == "__main__":
    sys.exit(main())
