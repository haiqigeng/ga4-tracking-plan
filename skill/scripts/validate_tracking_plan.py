from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from ecommerce_matrix import (
    ECOMMERCE_PARAMETERS_BY_PROFILE,
    ECOMMERCE_PROFILE_BY_EVENT,
    EVENT_PARAMETERS_BY_EVENT,
    OFFICIAL_ITEM_PARAMETERS,
)

from tracking_plan_validation_catalogs import (
    CUSTOM_CLASSIFICATIONS,
    CUSTOM_PARAMETER_CLASSIFICATIONS,
    ECOMMERCE_EVENTS,
    GA4_CLASSIFICATIONS,
    GA4_RESERVED_PARAMETER_NAMES,
    HIGH_CARDINALITY_GOVERNANCE_RE,
    LEGACY_WRAPPER_EVENT_KEYS,
    LEGACY_WRAPPER_PARAMETERS,
    MANUAL_COLLECTION_SOURCES,
    NON_CONVERSION_MEASUREMENT_ROLES,
    OFFICIAL_ECOMMERCE_PARAMETER_CLASSES,
    OFFICIAL_PARAMETER_CLASSES,
    OFFICIAL_SOURCE_DOMAINS,
    OFFICIAL_VERIFICATION_CLASSES,
    PIANO_CLASSIFICATIONS,
    POTENTIAL_DUPLICATE_EVENTS,
    REPORTING_PURPOSE_RE,
    TRANSACTION_EVENTS,
    VALUE_EVENTS_REQUIRE_CURRENCY,
    WEAK_BUSINESS_QUESTION_RE,
    WEAK_BUSINESS_QUESTIONS,
    WEAK_COMPONENT_CONTEXTS,
    WEAK_DATA_DEPENDENCY_VALUES,
    WEAK_NOT_TRACKED_REASONS,
    WEAK_REPORTING_PURPOSES,
    WEAK_VALUE_RULES,
    default_schema_path,
    load_ga4_catalog,
    load_json,
    load_piano_event_catalog,
)
from tracking_plan_validation_events import (
    check_custom_event_rationale,
    check_ga4_event_shape,
    check_ga4_name,
    check_legacy_ua_field,
    check_piano_event_shape,
    check_pii_name,
    check_platform_mapping,
    is_ga4_event,
    should_lint_ga4_parameter_name,
)
from tracking_plan_validation_model import Issue, add_issue


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


def walk_keys(value: Any, prefix: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            yield path, key
            yield from walk_keys(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_keys(child, f"{prefix}[{index}]")


def check_duplicates(values: list[str], label: str, path: str, issues: list[Issue]) -> None:
    for value, count in Counter(values).items():
        if value and count > 1:
            add_issue(issues, "error", "DUPLICATE_ID", path, f"{label} '{value}' appears {count} times.")



def expected_network_mentions_event(expected_network: Any, event_name: str) -> bool:
    if not event_name or not isinstance(expected_network, list):
        return False
    text = " ".join(str(entry) for entry in expected_network)
    return event_name in text


def check_business_question(value: Any, path: str, issues: list[Issue]) -> None:
    question = str(value or "").strip()
    if not question:
        return
    normalized = question.lower().rstrip(".")
    if normalized in WEAK_BUSINESS_QUESTIONS or WEAK_BUSINESS_QUESTION_RE.search(question):
        add_issue(
            issues,
            "error",
            "EVENT_BUSINESS_QUESTION_WEAK",
            path,
            "Business question must express the analysis need or decision supported by the event, not just the implementation action to track.",
        )


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
        if not (artifact_types & {"template_workbook", "client_tracking_plan", "tracking_plan_dev_doc", "tracking_plan_recette", "event_inventory"}):
            add_issue(
                issues,
                "error",
                "CLIENT_TEMPLATE_ARTIFACT_MISSING",
                "$.execution_context.input_artifact_inventory",
                "Client-template adaptation needs a client template, tracking plan, dev doc, recette plan, or event inventory artifact.",
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


def check_measurement_strategy(plan: dict[str, Any], issues: list[Issue]) -> None:
    strategy = plan.get("measurement_strategy", {})
    if not isinstance(strategy, dict):
        return

    platforms = set(plan.get("analytics_platforms", []) if isinstance(plan.get("analytics_platforms", []), list) else [])
    journey_ids = {
        str(brief.get("journey_id", ""))
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict) and brief.get("journey_id")
    }
    selected_families = strategy.get("selected_event_families", [])
    family_ids = {
        str(family.get("family_id", ""))
        for family in selected_families
        if isinstance(family, dict) and family.get("family_id")
    }
    custom_acceptance_names = {
        str(item.get("event_name", ""))
        for item in strategy.get("custom_event_acceptance", [])
        if isinstance(item, dict) and item.get("event_name")
    }

    for index, page_role in enumerate(strategy.get("page_roles", []) if isinstance(strategy.get("page_roles", []), list) else []):
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

    for index, family in enumerate(selected_families if isinstance(selected_families, list) else []):
        if not isinstance(family, dict):
            continue
        platform = str(family.get("analytics_platform", ""))
        if platforms and platform not in platforms and platform != "other":
            add_issue(
                issues,
                "error",
                "STRATEGY_PLATFORM_OUT_OF_SCOPE",
                f"$.measurement_strategy.selected_event_families[{index}].analytics_platform",
                f"Selected event family platform '{platform}' is not listed in analytics_platforms.",
            )
        reason = str(family.get("reason", "")).strip()
        if len(reason.split()) < 6:
            add_issue(
                issues,
                "error",
                "STRATEGY_EVENT_FAMILY_REASON_WEAK",
                f"$.measurement_strategy.selected_event_families[{index}].reason",
                "Selected event families need a concrete business or platform rationale.",
            )

    for index, event in enumerate(plan.get("events", []) if isinstance(plan.get("events", []), list) else []):
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
        if event.get("classification") in CUSTOM_CLASSIFICATIONS and str(event.get("event_name", "")) not in custom_acceptance_names:
            add_issue(
                issues,
                "error",
                "CUSTOM_EVENT_ACCEPTANCE_MISSING",
                "$.measurement_strategy.custom_event_acceptance",
                f"Custom event '{event.get('event_name')}' needs a custom_event_acceptance entry with official alternatives and business rationale.",
            )

    for index, item in enumerate(strategy.get("custom_event_acceptance", []) if isinstance(strategy.get("custom_event_acceptance", []), list) else []):
        if not isinstance(item, dict):
            continue
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


def check_website_coverage_map(plan: dict[str, Any], issues: list[Issue]) -> None:
    coverage = plan.get("website_coverage_map", {})
    if not isinstance(coverage, dict):
        return

    journey_ids = {
        str(brief.get("journey_id", ""))
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict) and brief.get("journey_id")
    }
    source_types = {
        str(source.get("source_type", ""))
        for source in coverage.get("sources_checked", [])
        if isinstance(source, dict)
    }
    structural_sources = {
        "sitemap",
        "robots_txt",
        "navigation",
        "url_list",
        "page_template",
        "playwright_crawl",
        "browser_exploration",
        "existing_tracking_plan",
    }

    covered_journey_ids: set[str] = set()
    included_coverage_ids: set[str] = set()
    for index, item in enumerate(coverage.get("journeys_covered", []) if isinstance(coverage.get("journeys_covered", []), list) else []):
        if not isinstance(item, dict):
            continue
        journey_id = str(item.get("journey_id", ""))
        if journey_id:
            covered_journey_ids.add(journey_id)
            if item.get("tracking_plan_decision") == "included":
                included_coverage_ids.add(journey_id)
            if journey_id not in journey_ids:
                add_issue(
                    issues,
                    "error",
                    "COVERAGE_JOURNEY_UNKNOWN",
                    f"$.website_coverage_map.journeys_covered[{index}].journey_id",
                    f"Coverage map references unknown journey_id '{journey_id}'.",
                )
        if item.get("tracking_plan_decision") == "included":
            if item.get("coverage_status") in {"blocked", "out_of_scope"}:
                add_issue(
                    issues,
                    "error",
                    "COVERAGE_INCLUDED_BUT_NOT_COVERED",
                    f"$.website_coverage_map.journeys_covered[{index}].coverage_status",
                    "Included journeys cannot be marked blocked or out_of_scope.",
                )
            for field in ["representative_urls", "page_templates", "key_interactions", "evidence"]:
                values = item.get(field, [])
                if not isinstance(values, list) or not any(str(value).strip() for value in values):
                    add_issue(
                        issues,
                        "error",
                        "COVERAGE_INCLUDED_EVIDENCE_MISSING",
                        f"$.website_coverage_map.journeys_covered[{index}].{field}",
                        f"Included journeys need non-empty {field} so analysts and future QA can understand coverage.",
                    )

    coverage_gap_text = " ".join(
        " ".join(str(value) for value in gap.values())
        for gap in coverage.get("coverage_gaps", [])
        if isinstance(gap, dict)
    ).lower()
    for index, discovered in enumerate(coverage.get("journeys_discovered", []) if isinstance(coverage.get("journeys_discovered", []), list) else []):
        if not isinstance(discovered, dict):
            continue
        journey_id = str(discovered.get("journey_id", ""))
        decision = str(discovered.get("decision", ""))
        if decision == "include_in_plan" and journey_id not in journey_ids:
            add_issue(
                issues,
                "error",
                "DISCOVERED_JOURNEY_NOT_IN_MEASUREMENT_BRIEF",
                f"$.website_coverage_map.journeys_discovered[{index}].journey_id",
                f"Discovered journey '{journey_id}' is marked include_in_plan but is missing from measurement_brief.",
            )
        if decision == "include_in_plan" and journey_id not in included_coverage_ids:
            add_issue(
                issues,
                "error",
                "DISCOVERED_JOURNEY_NOT_COVERED",
                f"$.website_coverage_map.journeys_discovered[{index}].journey_id",
                f"Discovered journey '{journey_id}' is marked include_in_plan but has no included coverage entry.",
            )
        if decision == "needs_discovery":
            marker_text = f"{journey_id} {discovered.get('journey_name', '')}".lower()
            if not any(part and part in coverage_gap_text for part in marker_text.split()):
                add_issue(
                    issues,
                    "error",
                    "DISCOVERED_JOURNEY_GAP_MISSING",
                    f"$.website_coverage_map.journeys_discovered[{index}].decision",
                    f"Discovered journey '{journey_id}' needs discovery but no matching coverage gap explains the risk.",
                )

    for brief_index, brief in enumerate(plan.get("measurement_brief", []) if isinstance(plan.get("measurement_brief", []), list) else []):
        if not isinstance(brief, dict):
            continue
        journey_id = str(brief.get("journey_id", ""))
        if journey_id and journey_id not in covered_journey_ids:
            add_issue(
                issues,
                "error",
                "MEASUREMENT_JOURNEY_NOT_IN_COVERAGE_MAP",
                f"$.measurement_brief[{brief_index}].journey_id",
                f"Journey '{journey_id}' must have a matching website_coverage_map.journeys_covered entry.",
            )

    if coverage.get("site_scope") == "whole_site" and not (source_types & structural_sources):
        add_issue(
            issues,
            "error",
            "WHOLE_SITE_COVERAGE_SOURCE_MISSING",
            "$.website_coverage_map.sources_checked",
            "Whole-site plans need at least one structural source such as sitemap, navigation, URL list, page templates, browser exploration, Playwright, or existing tracking files.",
        )
    if coverage.get("site_scope") == "whole_site" and not coverage.get("journeys_discovered"):
        add_issue(
            issues,
            "error",
            "WHOLE_SITE_DISCOVERED_JOURNEYS_MISSING",
            "$.website_coverage_map.journeys_discovered",
            "Whole-site plans must list discovered journeys and include/exclude/needs-discovery decisions.",
        )


def check_official_verification(
    verification: Any,
    platform: str,
    path: str,
    issues: list[Issue],
    *,
    required: bool,
) -> None:
    if not isinstance(verification, dict):
        if required:
            add_issue(issues, "error", "OFFICIAL_VERIFICATION_MISSING", path, "Official-first choices need source URL, checked date, and scope note.")
        return
    status = str(verification.get("status", ""))
    source_url = str(verification.get("source_url", "")).lower()
    scope_note = str(verification.get("scope_note", "")).strip()
    if required and status != "verified":
        add_issue(
            issues,
            "error",
            "OFFICIAL_VERIFICATION_NOT_VERIFIED",
            f"{path}.status",
            "Official/native/recommended/platform-standard fields must be marked verified against official documentation.",
        )
    if required and platform in OFFICIAL_SOURCE_DOMAINS and not any(domain in source_url for domain in OFFICIAL_SOURCE_DOMAINS[platform]):
        add_issue(
            issues,
            "error",
            "OFFICIAL_VERIFICATION_SOURCE_INVALID",
            f"{path}.source_url",
            f"Official verification for {platform} must cite an official source domain.",
        )
    if required and len(scope_note.split()) < 3:
        add_issue(
            issues,
            "error",
            "OFFICIAL_VERIFICATION_SCOPE_WEAK",
            f"{path}.scope_note",
            "Official verification must state event, item, property, or implementation scope clearly.",
        )


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


def check_event(
    event: dict[str, Any],
    index: int,
    parameter_lookup: dict[str, dict[str, Any]],
    ga4_catalog: dict[str, Any],
    piano_catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{index}]"
    event_name = event.get("event_name", "")
    classification = event.get("classification", "")
    parameters = event.get("parameters", [])
    parameter_names = set(parameter_lookup)
    data_layer = event.get("data_layer", {})
    ga4_payload = event.get("ga4_payload", {})
    privacy = event.get("privacy", {})

    check_legacy_ua_field(str(event_name), f"{base}.event_name", issues)

    if not event.get("primary_platform"):
        add_issue(issues, "error", "PRIMARY_PLATFORM_MISSING", f"{base}.primary_platform", "Every event needs primary_platform for platform-specific QA and mapping.")
    if not str(event.get("official_match", "")).strip():
        add_issue(issues, "error", "OFFICIAL_MATCH_MISSING", f"{base}.official_match", "Every event needs official_match describing the official event match or custom rationale.")
    check_official_verification(
        event.get("official_verification"),
        str(event.get("primary_platform", "")),
        f"{base}.official_verification",
        issues,
        required=classification in OFFICIAL_VERIFICATION_CLASSES,
    )
    collection_strategy = event.get("collection_strategy", {})
    if isinstance(collection_strategy, dict):
        collection_source = str(collection_strategy.get("collection_source", ""))
        duplicate_risk = collection_strategy.get("duplicate_risk", {})
        if classification == "automatic" and collection_source != "ga4_automatic":
            add_issue(
                issues,
                "warning",
                "AUTOMATIC_COLLECTION_SOURCE_MISMATCH",
                f"{base}.collection_strategy.collection_source",
                "GA4 automatic events should normally use collection_source='ga4_automatic'.",
            )
        if classification == "enhanced_measurement" and collection_source != "ga4_enhanced_measurement":
            add_issue(
                issues,
                "warning",
                "ENHANCED_COLLECTION_SOURCE_MISMATCH",
                f"{base}.collection_strategy.collection_source",
                "GA4 enhanced-measurement events should normally use collection_source='ga4_enhanced_measurement'.",
            )
        if str(event_name) in POTENTIAL_DUPLICATE_EVENTS and collection_source in MANUAL_COLLECTION_SOURCES:
            if not isinstance(duplicate_risk, dict) or duplicate_risk.get("level") == "low":
                add_issue(
                    issues,
                    "warning",
                    "ENHANCED_MEASUREMENT_DUPLICATE_RISK_UNDERSTATED",
                    f"{base}.collection_strategy.duplicate_risk.level",
                    f"Manual collection of '{event_name}' needs a medium/high duplicate-risk decision unless native collection is explicitly disabled or insufficient.",
                )
            reason_text = " ".join(str(duplicate_risk.get(key, "")) for key in ["reason", "dedupe_rule"]) if isinstance(duplicate_risk, dict) else ""
            if len(reason_text.split()) < 8:
                add_issue(
                    issues,
                    "error",
                    "DUPLICATE_RISK_DECISION_WEAK",
                    f"{base}.collection_strategy.duplicate_risk",
                    "Manual collection of automatic/enhanced-measurement candidates needs a concrete duplicate-risk reason and dedupe rule.",
                )
    page_or_component = str(event.get("page_or_component", "")).strip()
    if page_or_component.lower().rstrip(".") in WEAK_COMPONENT_CONTEXTS or len(page_or_component.split()) < 2:
        add_issue(
            issues,
            "error",
            "EVENT_COMPONENT_CONTEXT_WEAK",
            f"{base}.page_or_component",
            "Event page_or_component must identify the concrete page area, module, form, list, or interaction target.",
        )
    data_dependencies = event.get("data_dependencies", [])
    if not isinstance(data_dependencies, list) or not data_dependencies:
        add_issue(
            issues,
            "error",
            "EVENT_DATA_DEPENDENCIES_MISSING",
            f"{base}.data_dependencies",
            "Every event needs concrete data dependencies so developers and QA know which source values are required.",
        )
    elif any(
        str(dependency).strip().lower().rstrip(".") in WEAK_DATA_DEPENDENCY_VALUES
        or len(str(dependency).strip().split()) < 2
        for dependency in data_dependencies
    ):
        add_issue(
            issues,
            "error",
            "EVENT_DATA_DEPENDENCY_WEAK",
            f"{base}.data_dependencies",
            "Event data_dependencies must list concrete source values or systems, not generic placeholders.",
        )
    role = str(event.get("measurement_role", ""))
    if role in NON_CONVERSION_MEASUREMENT_ROLES and event.get("key_event"):
        add_issue(
            issues,
            "error",
            "KEY_EVENT_ROLE_INVALID",
            f"{base}.measurement_role",
            f"Events with measurement_role '{role}' should not be marked as key events.",
        )
    if role == "macro_conversion" and not event.get("key_event"):
        add_issue(
            issues,
            "warning",
            "MACRO_CONVERSION_NOT_KEY_EVENT",
            f"{base}.key_event",
            "Macro conversions should normally be marked as key events or explicitly justified in implementation_notes.",
        )
    if role == "macro_conversion" and event.get("priority") != "must":
        add_issue(
            issues,
            "warning",
            "MACRO_CONVERSION_PRIORITY",
            f"{base}.priority",
            "Macro conversions should normally use priority='must'.",
        )
    check_business_question(event.get("business_question"), f"{base}.business_question", issues)

    for parameter in parameters:
        check_pii_name(str(parameter), f"{base}.parameters", issues)
        check_legacy_ua_field(str(parameter), f"{base}.parameters", issues)
        if parameter in LEGACY_WRAPPER_PARAMETERS:
            add_issue(
                issues,
                "warning",
                "LEGACY_WRAPPER_PARAMETER",
                f"{base}.parameters",
                f"Parameter '{parameter}' is a legacy wrapper pattern. Prefer direct GA4 event parameters.",
            )
        if parameter.startswith("items[].") and parameter not in OFFICIAL_ITEM_PARAMETERS and parameter not in parameter_names:
            add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_NOT_DEFINED", f"{base}.parameters", f"Custom item parameter '{parameter}' must be defined in the parameter reference.")
        elif parameter not in parameter_names and not parameter.startswith("items[]."):
            add_issue(issues, "warning", "PARAMETER_NOT_DEFINED", f"{base}.parameters", f"Parameter '{parameter}' is not in the parameter reference.")

    event_key = data_layer.get("event_key")
    if event_name in LEGACY_WRAPPER_EVENT_KEYS or event_key in LEGACY_WRAPPER_EVENT_KEYS:
        add_issue(
            issues,
            "error",
            "LEGACY_WRAPPER_EVENT",
            f"{base}.data_layer.event_key",
            "Use the GA4 event name directly instead of a wrapper event such as gtm.custom_event.",
        )

    push = data_layer.get("push", {})
    if isinstance(push, dict):
        pushed_event = push.get("event")
        if pushed_event in LEGACY_WRAPPER_EVENT_KEYS:
            add_issue(
                issues,
                "error",
                "LEGACY_WRAPPER_PUSH",
                f"{base}.data_layer.push.event",
                "dataLayer push uses a wrapper event. Push the final GA4 event name directly.",
            )
        for path, key in walk_keys(push, f"{base}.data_layer.push"):
            check_pii_name(key, path, issues)
            check_legacy_ua_field(key, path, issues)

    payload_name = ga4_payload.get("event_name")
    if payload_name and payload_name != event_name:
        add_issue(issues, "error", "PAYLOAD_EVENT_MISMATCH", f"{base}.ga4_payload.event_name", f"Payload event '{payload_name}' does not match event_name '{event_name}'.")

    payload_parameters = ga4_payload.get("parameters", {}) if isinstance(ga4_payload.get("parameters"), dict) else {}
    for name in payload_parameters:
        check_pii_name(name, f"{base}.ga4_payload.parameters.{name}", issues)
        check_legacy_ua_field(name, f"{base}.ga4_payload.parameters.{name}", issues)

    if event_name in ECOMMERCE_EVENTS and classification != "recommended_ecommerce":
        add_issue(issues, "warning", "ECOMMERCE_CLASSIFICATION", f"{base}.classification", f"Official ecommerce event '{event_name}' should usually be classified as recommended_ecommerce.")
    if classification == "recommended_ecommerce" and event_name not in ECOMMERCE_EVENTS:
        add_issue(issues, "error", "INVALID_ECOMMERCE_EVENT", f"{base}.event_name", f"'{event_name}' is not an official GA4 ecommerce event.")

    if classification == "recommended_ecommerce":
        profile = event.get("parameter_profile")
        expected_profile = ECOMMERCE_PROFILE_BY_EVENT.get(str(event_name))
        if not isinstance(profile, dict):
            add_issue(issues, "error", "ECOMMERCE_PARAMETER_PROFILE_MISSING", f"{base}.parameter_profile", "Ecommerce events need a canonical parameter profile.")
        else:
            profile_id = profile.get("profile_id")
            if expected_profile and profile_id != expected_profile:
                add_issue(
                    issues,
                    "error",
                    "ECOMMERCE_PARAMETER_PROFILE_MISMATCH",
                    f"{base}.parameter_profile.profile_id",
                    f"{event_name} should use parameter profile '{expected_profile}'.",
                )
            canonical = profile.get("canonical_parameter_order", [])
            expected_order = ECOMMERCE_PARAMETERS_BY_PROFILE.get(str(profile_id), [])
            if expected_order and canonical != expected_order:
                add_issue(
                    issues,
                    "error",
                    "ECOMMERCE_PARAMETER_PROFILE_ORDER",
                    f"{base}.parameter_profile.canonical_parameter_order",
                    "Ecommerce parameter profile must use the canonical order for the profile.",
                )
            ordered_event_parameters = [parameter for parameter in event.get("parameters", []) if parameter in canonical]
            canonical_present = [parameter for parameter in canonical if parameter in event.get("parameters", [])]
            if ordered_event_parameters != canonical_present:
                add_issue(
                    issues,
                    "warning",
                    "ECOMMERCE_EVENT_PARAMETER_ORDER",
                    f"{base}.parameters",
                    "Ecommerce event parameters should follow the canonical profile order to keep the Event Matrix readable.",
                )
        official_event_parameters = EVENT_PARAMETERS_BY_EVENT.get(event_name, set())
        for name in payload_parameters:
            metadata = parameter_lookup.get(name)
            if name not in official_event_parameters:
                if metadata is None:
                    add_issue(issues, "warning", "CUSTOM_ECOMMERCE_PARAMETER_NOT_DEFINED", f"{base}.ga4_payload.parameters.{name}", f"Custom ecommerce event parameter '{name}' must be defined in the parameter reference.")
                elif metadata.get("classification") in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                    add_issue(issues, "error", "CUSTOM_ECOMMERCE_PARAMETER_MISCLASSIFIED", f"{base}.ga4_payload.parameters.{name}", f"'{name}' is not an official parameter for {event_name}; classify it as custom_event_parameter or remove it.")
        items = ga4_payload.get("items", [])
        if not isinstance(items, list) or not items:
            add_issue(issues, "error", "ECOMMERCE_ITEMS_MISSING", f"{base}.ga4_payload.items", "Ecommerce events need an items array when product/item data is available.")
        for item_index, item in enumerate(items if isinstance(items, list) else []):
            if not isinstance(item, dict):
                continue
            if "item_id" not in item and "item_name" not in item:
                add_issue(issues, "error", "ECOMMERCE_ITEM_ID_OR_NAME", f"{base}.ga4_payload.items[{item_index}]", "Each ecommerce item needs item_id or item_name.")
            if "currency" in item:
                add_issue(issues, "error", "ITEM_SCOPE_CURRENCY", f"{base}.ga4_payload.items[{item_index}].currency", "currency is event-scoped, not item-scoped.")
            for key in item:
                parameter_name = f"items[].{key}"
                metadata = parameter_lookup.get(parameter_name)
                if parameter_name in OFFICIAL_ITEM_PARAMETERS:
                    continue
                if metadata is None:
                    add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_NOT_DEFINED", f"{base}.ga4_payload.items[{item_index}].{key}", f"Custom item parameter '{parameter_name}' must be defined in the parameter reference.")
                elif metadata.get("classification") in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                    add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", f"{base}.ga4_payload.items[{item_index}].{key}", f"'{parameter_name}' is not an official GA4 item parameter; classify it as custom_item_parameter or remove it.")
        flush_keys = set(data_layer.get("flush_keys", []))
        if "ecommerce" not in flush_keys:
            add_issue(issues, "warning", "ECOMMERCE_FLUSH_MISSING", f"{base}.data_layer.flush_keys", "Flush ecommerce before ecommerce pushes to prevent stale item data.")

    if event_name in TRANSACTION_EVENTS and "transaction_id" not in payload_parameters:
        add_issue(issues, "error", "TRANSACTION_ID_MISSING", f"{base}.ga4_payload.parameters", f"{event_name} needs transaction_id for deduplication.")
    if event_name in VALUE_EVENTS_REQUIRE_CURRENCY and "value" in payload_parameters and "currency" not in payload_parameters:
        add_issue(issues, "error", "CURRENCY_MISSING", f"{base}.ga4_payload.parameters", "currency is required when value is sent.")

    if privacy.get("pii_risk") == "high":
        add_issue(issues, "error", "HIGH_PII_RISK", f"{base}.privacy.pii_risk", "High PII risk must be resolved before plan approval.")
    cardinality_notes = f"{privacy.get('notes', '')} {event.get('implementation_notes', '')}"
    if privacy.get("cardinality_risk") == "high" and not HIGH_CARDINALITY_GOVERNANCE_RE.search(cardinality_notes):
        add_issue(issues, "warning", "HIGH_CARDINALITY_RISK", f"{base}.privacy.cardinality_risk", "High-cardinality fields should not be registered as reporting dimensions unless justified.")

    qa = event.get("qa", {})
    if not qa.get("qa_id"):
        add_issue(issues, "error", "EVENT_QA_MISSING", f"{base}.qa.qa_id", "Every testable event needs a stable qa_id.")
    if not qa.get("expected_data_layer"):
        add_issue(issues, "warning", "EXPECTED_DATALAYER_MISSING", f"{base}.qa.expected_data_layer", "QA should include expected dataLayer keys or note why none apply.")
    if not qa.get("expected_network"):
        add_issue(issues, "warning", "EXPECTED_NETWORK_MISSING", f"{base}.qa.expected_network", "QA should include expected GA4/network event and key parameters.")
    elif not expected_network_mentions_event(qa.get("expected_network"), str(event_name)):
        add_issue(
            issues,
            "error",
            "QA_EXPECTED_NETWORK_EVENT_NAME_MISSING",
            f"{base}.qa.expected_network",
            f"Event QA expected_network must mention the expected event name '{event_name}'.",
        )

    if classification in GA4_CLASSIFICATIONS and classification != "automatic" and not ga4_payload:
        add_issue(
            issues,
            "warning",
            "GA4_PAYLOAD_MISSING",
            f"{base}.ga4_payload",
            "GA4 recommended, ecommerce, and custom events should include a ga4_payload example unless the event is intentionally automatic-only.",
        )

    if event.get("primary_platform") and event.get("platform_mappings"):
        mapped_platforms = {mapping.get("platform") for mapping in event.get("platform_mappings", []) if isinstance(mapping, dict)}
        if event.get("primary_platform") not in mapped_platforms and event.get("primary_platform") != "ga4":
            add_issue(
                issues,
                "warning",
                "PRIMARY_PLATFORM_MAPPING_MISSING",
                f"{base}.platform_mappings",
                f"primary_platform is {event.get('primary_platform')} but no matching platform mapping is listed.",
            )

    for payload_index, payload in enumerate(event.get("implementation_payloads", [])):
        if not isinstance(payload, dict):
            continue
        check_legacy_ua_field(str(payload.get("event_name", "")), f"{base}.implementation_payloads[{payload_index}].event_name", issues)
        payload_data = payload.get("payload", {})
        if isinstance(payload_data, dict):
            for key in payload_data:
                check_pii_name(str(key), f"{base}.implementation_payloads[{payload_index}].payload.{key}", issues)
                check_legacy_ua_field(str(key), f"{base}.implementation_payloads[{payload_index}].payload.{key}", issues)

    check_piano_event_shape(event, index, piano_catalog, issues)
    check_ga4_event_shape(event, index, ga4_catalog, issues)
    check_custom_event_rationale(event, index, issues)

    for mapping_index, mapping in enumerate(event.get("platform_mappings", [])):
        if isinstance(mapping, dict):
            check_platform_mapping(event, index, mapping, mapping_index, piano_catalog, issues)


def validate_plan_data(plan: dict[str, Any], schema_path: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    schema_path = schema_path or default_schema_path()
    validate_schema(plan, schema_path, issues)

    parameters = plan.get("parameters", [])
    parameter_lookup = {param.get("parameter_name", ""): param for param in parameters if isinstance(param, dict)}
    ga4_catalog = load_ga4_catalog()
    piano_catalog = load_piano_event_catalog()
    events = plan.get("events", [])
    qa_cases = plan.get("qa_cases", [])
    custom_definitions = plan.get("custom_definitions", [])
    documentation_sources = plan.get("documentation_sources_checked", [])
    registered_item_custom_dimensions = {
        definition.get("parameter_name")
        for definition in custom_definitions
        if isinstance(definition, dict)
        and definition.get("scope") == "item"
        and definition.get("registration_type") == "custom_dimension"
    }
    custom_definition_keys = {
        (definition.get("parameter_name"), definition.get("scope"))
        for definition in custom_definitions
        if isinstance(definition, dict)
    }

    check_duplicates([event.get("event_id", "") for event in events if isinstance(event, dict)], "event_id", "$.events", issues)
    check_duplicates([case.get("qa_id", "") for case in qa_cases if isinstance(case, dict)], "qa_id", "$.qa_cases", issues)
    check_execution_context(plan, issues)
    check_measurement_alignment(plan, issues)
    check_measurement_strategy(plan, issues)
    check_website_coverage_map(plan, issues)
    check_not_tracked_decisions(plan, issues)
    source_urls = [
        str(source.get("url", "")).lower()
        for source in documentation_sources
        if isinstance(source, dict) and source.get("source_type") == "official"
    ]
    has_ga4_events = any(isinstance(event, dict) and is_ga4_event(event) for event in events)
    has_piano_events = any(
        isinstance(event, dict)
        and (event.get("primary_platform") == "piano_analytics" or event.get("classification") in PIANO_CLASSIFICATIONS)
        for event in events
    )
    if has_ga4_events and not any(any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS["ga4"]) for url in source_urls):
        add_issue(
            issues,
            "error",
            "GA4_OFFICIAL_SOURCE_MISSING",
            "$.documentation_sources_checked",
            "GA4 plans must cite at least one official Google Analytics documentation source.",
        )
    if has_piano_events and not any(any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS["piano_analytics"]) for url in source_urls):
        add_issue(
            issues,
            "error",
            "PIANO_OFFICIAL_SOURCE_MISSING",
            "$.documentation_sources_checked",
            "Piano Analytics plans must cite at least one official Piano documentation source.",
        )

    for index, param in enumerate(parameters):
        if not isinstance(param, dict):
            continue
        name = str(param.get("parameter_name", ""))
        check_pii_name(name, f"$.parameters[{index}].parameter_name", issues)
        check_legacy_ua_field(name, f"$.parameters[{index}].parameter_name", issues)
        classification = param.get("classification")
        parameter_platform = "piano_analytics" if str(classification).startswith("piano_") else "ga4"
        check_official_verification(
            param.get("official_verification"),
            parameter_platform,
            f"$.parameters[{index}].official_verification",
            issues,
            required=classification in OFFICIAL_PARAMETER_CLASSES,
        )
        if should_lint_ga4_parameter_name(name, param):
            check_ga4_name(name, f"$.parameters[{index}].parameter_name", "parameter", issues)
            if name in GA4_RESERVED_PARAMETER_NAMES and classification not in {
                "ga4_auto_collected_parameter",
                "ga4_native_parameter",
                "ga4_recommended_parameter",
                "ga4_ecommerce_parameter",
                "ga4_ecommerce_item_parameter",
            }:
                add_issue(
                    issues,
                    "error",
                    "GA4_RESERVED_PARAMETER_NAME",
                    f"$.parameters[{index}].parameter_name",
                    f"'{name}' is reserved/native in GA4 and must not be used as a custom parameter.",
                )
        if name.startswith("items[]."):
            if name in OFFICIAL_ITEM_PARAMETERS:
                if classification == "custom_item_parameter":
                    add_issue(issues, "warning", "OFFICIAL_ITEM_PARAMETER_MISCLASSIFIED", f"$.parameters[{index}].classification", f"'{name}' is an official GA4 item parameter; classify it as ga4_ecommerce_item_parameter.")
            else:
                if classification in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                    add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", f"$.parameters[{index}].classification", f"'{name}' is not an official GA4 item parameter; classify it as custom_item_parameter.")
                elif classification != "custom_item_parameter":
                    add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_CLASSIFICATION", f"$.parameters[{index}].classification", f"'{name}' is item-scoped and non-official; use custom_item_parameter.")
                if param.get("scope") != "item":
                    add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_SCOPE", f"$.parameters[{index}].scope", f"'{name}' must use item scope.")
                if param.get("register_custom_definition") and name not in registered_item_custom_dimensions:
                    add_issue(issues, "warning", "CUSTOM_ITEM_DIMENSION_MISSING", "$.custom_definitions", f"'{name}' is marked for registration but no matching item-scoped custom dimension is listed.")
        if param.get("pii_risk") == "high":
            add_issue(issues, "error", "HIGH_PII_RISK", f"$.parameters[{index}].pii_risk", f"Parameter '{name}' has high PII risk.")
        if param.get("cardinality_risk") == "high" and param.get("register_custom_definition"):
            add_issue(issues, "warning", "HIGH_CARDINALITY_CUSTOM_DIMENSION", f"$.parameters[{index}]", f"Parameter '{name}' is high-cardinality and marked for custom definition registration.")
        reporting_purpose = str(param.get("reporting_purpose", "")).strip()
        normalized_purpose = reporting_purpose.lower().rstrip(".")
        if normalized_purpose in WEAK_REPORTING_PURPOSES or len(reporting_purpose.split()) < 5:
            add_issue(
                issues,
                "error",
                "PARAMETER_REPORTING_PURPOSE_WEAK",
                f"$.parameters[{index}].reporting_purpose",
                f"Parameter '{name}' needs a concrete reporting or analysis purpose.",
            )
        elif classification in CUSTOM_PARAMETER_CLASSIFICATIONS and not REPORTING_PURPOSE_RE.search(reporting_purpose):
            add_issue(
                issues,
                "error",
                "CUSTOM_PARAMETER_REPORTING_PURPOSE_WEAK",
                f"$.parameters[{index}].reporting_purpose",
                f"Custom parameter '{name}' must state the analysis, segmentation, QA, or optimization use it supports.",
            )
        value_rules = str(param.get("value_rules", "")).strip()
        normalized_rules = value_rules.lower().rstrip(".")
        if classification in CUSTOM_PARAMETER_CLASSIFICATIONS and (normalized_rules in WEAK_VALUE_RULES or len(value_rules.split()) < 3):
            add_issue(
                issues,
                "error",
                "CUSTOM_PARAMETER_VALUE_RULES_WEAK",
                f"$.parameters[{index}].value_rules",
                f"Custom parameter '{name}' needs concrete value rules or controlled values.",
            )
        if param.get("register_custom_definition") and (name, param.get("scope")) not in custom_definition_keys:
            add_issue(
                issues,
                "error",
                "CUSTOM_DEFINITION_MISSING",
                "$.custom_definitions",
                f"Parameter '{name}' is marked for custom definition/Data Model registration but no matching custom_definitions row exists.",
            )
        if classification == "piano_custom_property" and param.get("register_custom_definition"):
            matching_definitions = [
                definition
                for definition in custom_definitions
                if isinstance(definition, dict)
                and definition.get("parameter_name") == name
                and definition.get("scope") == param.get("scope")
            ]
            if not any(definition.get("registration_type") == "piano_data_model_property" for definition in matching_definitions):
                add_issue(
                    issues,
                    "error",
                    "PIANO_DATA_MODEL_DEFINITION_MISSING",
                    "$.custom_definitions",
                    f"Piano custom property '{name}' is marked for registration but no Piano Data Model property row is listed.",
                )

    for index, event in enumerate(events):
        if isinstance(event, dict):
            check_event(event, index, parameter_lookup, ga4_catalog, piano_catalog, issues)

    events_by_id = {event.get("event_id"): event for event in events if isinstance(event, dict)}
    events_by_name = {event.get("event_name"): event for event in events if isinstance(event, dict)}
    event_qa_ids = {event.get("qa", {}).get("qa_id") for event in events if isinstance(event, dict)}
    qa_case_ids = {case.get("qa_id") for case in qa_cases if isinstance(case, dict)}
    for event_id, event in events_by_id.items():
        if event and event.get("qa", {}).get("qa_id") not in qa_case_ids:
            add_issue(issues, "warning", "QA_CASE_MISSING", "$.qa_cases", f"Event '{event_id}' has no matching qa_cases entry.")
    for index, case in enumerate(qa_cases):
        if not isinstance(case, dict):
            continue
        event_id = case.get("event_id")
        event = events_by_id.get(event_id)
        if not event:
            add_issue(issues, "error", "QA_EVENT_NOT_FOUND", f"$.qa_cases[{index}].event_id", f"QA case references unknown event_id '{event_id}'.")
            continue
        if case.get("event_name") != event.get("event_name"):
            add_issue(issues, "error", "QA_EVENT_NAME_MISMATCH", f"$.qa_cases[{index}].event_name", "QA case event_name does not match the referenced event.")
        if case.get("qa_id") not in event_qa_ids:
            add_issue(issues, "warning", "QA_ID_NOT_ON_EVENT", f"$.qa_cases[{index}].qa_id", "QA case qa_id is not referenced by an event qa block.")
        if not expected_network_mentions_event(case.get("expected_network"), str(case.get("event_name", ""))):
            add_issue(
                issues,
                "error",
                "QA_EXPECTED_NETWORK_EVENT_NAME_MISSING",
                f"$.qa_cases[{index}].expected_network",
                f"Top-level QA expected_network must mention the expected event name '{case.get('event_name')}'.",
            )

    for index, key_event in enumerate(plan.get("key_events", []) if isinstance(plan.get("key_events", []), list) else []):
        if not isinstance(key_event, dict):
            continue
        event = events_by_name.get(key_event.get("event_name"))
        if not event:
            add_issue(
                issues,
                "error",
                "KEY_EVENT_NOT_FOUND",
                f"$.key_events[{index}].event_name",
                f"Key event '{key_event.get('event_name')}' is not defined in events.",
            )
            continue
        if event.get("measurement_role") in NON_CONVERSION_MEASUREMENT_ROLES:
            add_issue(
                issues,
                "error",
                "KEY_EVENT_ROLE_INVALID",
                f"$.key_events[{index}].event_name",
                f"Key event '{key_event.get('event_name')}' points to a {event.get('measurement_role')} event.",
            )

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
