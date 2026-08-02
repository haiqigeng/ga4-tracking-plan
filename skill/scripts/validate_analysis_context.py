from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from discovery_contract import validate_discovery_bindings
from jsonschema import Draft202012Validator, FormatChecker
from tracking_plan_model import load_json
from validate_tracking_plan import Issue, issue, render_text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "references" / "schema-analysis-context.json"
LIKELY_FINITE_PARAMETERS = {
    "item_brand",
    "item_category",
    "item_category2",
    "item_category3",
    "item_category4",
    "item_category5",
    "item_list_id",
    "item_list_name",
    "shipping_tier",
    "payment_type",
    "method",
    "form_name",
    "form_step",
    "project_type",
    "promotion_type",
    "sort_type",
    "filter_type",
    "contact_method",
    "page_type",
    "user_status",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Validate the internal evidence, journey-coverage, and finite-value checkpoint used by a GA4 tracking-plan delivery.")
    )
    parser.add_argument("context", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument(
        "--discovery-report",
        type=Path,
        action="append",
        default=[],
        help="Original discovery report used to verify hashes and hint closure.",
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--delivery",
        action="store_true",
        help="Apply delivery gates for material coverage and unresolved gaps.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def _schema_issues(context: dict[str, Any], schema_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    validator = Draft202012Validator(
        load_json(schema_path),
        format_checker=FormatChecker(),
    )
    for error in sorted(
        validator.iter_errors(context),
        key=lambda item: list(item.absolute_path),
    ):
        path = "$" + "".join(f"[{part!r}]" if isinstance(part, str) else f"[{part}]" for part in error.absolute_path)
        issue(issues, "error", "ANALYSIS_CONTEXT_SCHEMA", path, error.message)
    return issues


def _duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def _normalized_values(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for value in values}


def _ascii_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def _plan_parameters(
    plan: dict[str, Any],
) -> list[tuple[str, int, dict[str, Any]]]:
    result: list[tuple[str, int, dict[str, Any]]] = []
    for event in plan.get("events", []):
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event_name", ""))
        for index, parameter in enumerate(event.get("parameters", [])):
            if isinstance(parameter, dict):
                result.append((event_name, index, parameter))
    return result


def validate_analysis_context(
    context: dict[str, Any],
    plan: dict[str, Any] | None = None,
    *,
    delivery: bool = False,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[Issue]:
    issues = _schema_issues(context, schema_path)
    if issues:
        return issues

    sources = [item for item in context.get("sources", []) if isinstance(item, dict)]
    discovery_reports = [item for item in context.get("discovery_reports", []) if isinstance(item, dict)]
    coverages = [item for item in context.get("journey_coverage", []) if isinstance(item, dict)]
    gaps = [item for item in context.get("coverage_gaps", []) if isinstance(item, dict)]
    opportunities = [item for item in context.get("measurement_opportunities", []) if isinstance(item, dict)]
    domains = [item for item in context.get("value_domains", []) if isinstance(item, dict)]

    source_ids = [str(item.get("source_id", "")) for item in sources]
    coverage_ids = [str(item.get("journey_id", "")) for item in coverages]
    gap_ids = [str(item.get("gap_id", "")) for item in gaps]
    opportunity_ids = [str(item.get("opportunity_id", "")) for item in opportunities]
    domain_ids = [str(item.get("domain_id", "")) for item in domains]
    discovery_report_ids = [str(item.get("report_id", "")) for item in discovery_reports]
    for label, values, path in (
        ("source", source_ids, "$.sources"),
        ("journey coverage", coverage_ids, "$.journey_coverage"),
        ("coverage gap", gap_ids, "$.coverage_gaps"),
        ("measurement opportunity", opportunity_ids, "$.measurement_opportunities"),
        ("value domain", domain_ids, "$.value_domains"),
        ("discovery report", discovery_report_ids, "$.discovery_reports"),
    ):
        duplicate_values = sorted(_duplicates(values))
        if duplicate_values:
            issue(
                issues,
                "error",
                "ANALYSIS_CONTEXT_DUPLICATE_ID",
                path,
                f"Duplicate {label} IDs: {', '.join(duplicate_values)}.",
            )

    known_sources = set(source_ids)
    language_decision = context.get("language_decision", {})
    unknown_language_refs = sorted(set(str(value) for value in language_decision.get("evidence_refs", [])) - known_sources)
    if unknown_language_refs:
        issue(
            issues,
            "error",
            "LANGUAGE_DECISION_UNKNOWN_EVIDENCE",
            "$.language_decision.evidence_refs",
            "Unknown evidence source IDs: " + ", ".join(unknown_language_refs),
        )
    known_discovery_hints: set[str] = set()
    known_discovery_journeys: set[str] = set()
    known_discovery_variants: set[str] = set()
    for index, report in enumerate(discovery_reports):
        source_id = str(report.get("source_id", ""))
        if source_id not in known_sources:
            issue(
                issues,
                "error",
                "DISCOVERY_REPORT_UNKNOWN_SOURCE",
                f"$.discovery_reports[{index}].source_id",
                f"Unknown evidence source ID '{source_id}'.",
            )
        elif next((source for source in sources if source.get("source_id") == source_id), {}).get("source_type") != "live_website":
            issue(
                issues,
                "error",
                "DISCOVERY_REPORT_SOURCE_NOT_LIVE",
                f"$.discovery_reports[{index}].source_id",
                "A rendered discovery report must bind to a live_website source.",
            )
        hints = {str(value) for value in report.get("hint_ids", [])}
        duplicate_hints = sorted(known_discovery_hints & hints)
        if duplicate_hints:
            issue(
                issues,
                "error",
                "DISCOVERY_HINT_DUPLICATE",
                f"$.discovery_reports[{index}].hint_ids",
                "Hint IDs occur in multiple reports: " + ", ".join(duplicate_hints),
            )
        known_discovery_hints.update(hints)
        known_discovery_journeys.update(str(value) for value in report.get("journey_ids", []))
        variants = {str(value) for value in report.get("variant_ids", [])}
        duplicate_variants = sorted(known_discovery_variants & variants)
        if duplicate_variants:
            issue(
                issues,
                "error",
                "DISCOVERY_VARIANT_DUPLICATE",
                f"$.discovery_reports[{index}].variant_ids",
                "Variant IDs occur in multiple reports: " + ", ".join(duplicate_variants),
            )
        known_discovery_variants.update(variants)
    for collection_name, records in (
        ("journey_coverage", coverages),
        ("coverage_gaps", gaps),
        ("measurement_opportunities", opportunities),
        ("value_domains", domains),
    ):
        for index, record in enumerate(records):
            unknown = sorted(set(str(value) for value in record.get("evidence_refs", [])) - known_sources)
            if unknown:
                issue(
                    issues,
                    "error",
                    "ANALYSIS_CONTEXT_UNKNOWN_EVIDENCE",
                    f"$.{collection_name}[{index}].evidence_refs",
                    "Unknown evidence source IDs: " + ", ".join(unknown),
                )

    known_opportunities = set(opportunity_ids)
    covered_opportunities: set[str] = set()
    coverage_variants_by_journey: dict[str, set[str]] = {}
    for index, coverage in enumerate(coverages):
        journey_id = str(coverage.get("journey_id", ""))
        variant_ids = [
            str(variant.get("variant_id", ""))
            for variant in coverage.get("variant_coverage", [])
            if isinstance(variant, dict)
        ]
        duplicate_variant_ids = sorted(_duplicates(variant_ids))
        if duplicate_variant_ids:
            issue(
                issues,
                "error",
                "JOURNEY_VARIANT_DUPLICATE",
                f"$.journey_coverage[{index}].variant_coverage",
                "Duplicate journey-variant IDs: " + ", ".join(duplicate_variant_ids),
            )
        coverage_variants_by_journey[journey_id] = set(variant_ids)
        unknown_variants = sorted(set(variant_ids) - known_discovery_variants) if discovery_reports else []
        if unknown_variants:
            issue(
                issues,
                "error",
                "JOURNEY_UNKNOWN_DISCOVERY_VARIANT",
                f"$.journey_coverage[{index}].variant_coverage",
                "Unknown discovery variant IDs: " + ", ".join(unknown_variants),
            )
        unknown = sorted(set(str(value) for value in coverage.get("opportunity_ids", [])) - known_opportunities)
        if unknown:
            issue(
                issues,
                "error",
                "JOURNEY_UNKNOWN_OPPORTUNITY",
                f"$.journey_coverage[{index}].opportunity_ids",
                "Unknown measurement-opportunity IDs: " + ", ".join(unknown),
            )
        for opportunity_id in coverage.get("opportunity_ids", []):
            opportunity = next(
                (item for item in opportunities if item.get("opportunity_id") == opportunity_id),
                None,
            )
            if opportunity is not None and opportunity.get("journey_id") != coverage.get("journey_id"):
                issue(
                    issues,
                    "error",
                    "JOURNEY_OPPORTUNITY_MISMATCH",
                    f"$.journey_coverage[{index}].opportunity_ids",
                    f"Opportunity '{opportunity_id}' belongs to another journey.",
                )
            covered_opportunities.add(str(opportunity_id))
        if delivery and coverage.get("material") is True and not coverage.get("opportunity_ids"):
            issue(
                issues,
                "error",
                "MATERIAL_JOURNEY_OPPORTUNITY_MISSING",
                f"$.journey_coverage[{index}].opportunity_ids",
                "Every material journey needs explicit measurement-opportunity decisions.",
            )

    mapped_discovery_hints: set[str] = set()
    for index, opportunity in enumerate(opportunities):
        hint_ids = {str(value) for value in opportunity.get("discovery_hint_ids", [])}
        mapped_discovery_hints.update(hint_ids)
        unknown_hints = sorted(hint_ids - known_discovery_hints)
        if unknown_hints:
            issue(
                issues,
                "error",
                "OPPORTUNITY_UNKNOWN_DISCOVERY_HINT",
                f"$.measurement_opportunities[{index}].discovery_hint_ids",
                "Unknown discovery hint IDs: " + ", ".join(unknown_hints),
            )
        variant_id = str(opportunity.get("variant_id", ""))
        journey_id = str(opportunity.get("journey_id", ""))
        if variant_id and variant_id not in known_discovery_variants and discovery_reports:
            issue(
                issues,
                "error",
                "OPPORTUNITY_UNKNOWN_DISCOVERY_VARIANT",
                f"$.measurement_opportunities[{index}].variant_id",
                f"Unknown discovery variant ID '{variant_id}'.",
            )
        if variant_id and variant_id not in coverage_variants_by_journey.get(journey_id, set()):
            issue(
                issues,
                "error",
                "OPPORTUNITY_VARIANT_COVERAGE_MISSING",
                f"$.measurement_opportunities[{index}].variant_id",
                f"Variant '{variant_id}' is not covered under journey '{journey_id}'.",
            )
        if opportunity.get("material") is True and opportunity.get("opportunity_id") not in covered_opportunities:
            issue(
                issues,
                "error",
                "OPPORTUNITY_NOT_LINKED_TO_JOURNEY",
                f"$.measurement_opportunities[{index}]",
                "Every material opportunity must be linked from its journey coverage row.",
            )
        if delivery and opportunity.get("material") is True and opportunity.get("decision") == "unresolved":
            issue(
                issues,
                "error",
                "MATERIAL_OPPORTUNITY_UNRESOLVED",
                f"$.measurement_opportunities[{index}]",
                f"Material opportunity '{opportunity.get('opportunity_id')}' is unresolved.",
            )
        if opportunity.get("decision") == "measure" and opportunity.get("official_fit") == "not_applicable":
            issue(
                issues,
                "error",
                "MEASURED_OPPORTUNITY_OFFICIAL_REVIEW_MISSING",
                f"$.measurement_opportunities[{index}].official_fit",
                "A measured opportunity must evaluate an official candidate as fit or gap.",
            )
    missing_discovery_hints = sorted(known_discovery_hints - mapped_discovery_hints)
    if missing_discovery_hints:
        issue(
            issues,
            "error",
            "DISCOVERY_HINT_DECISION_MISSING",
            "$.measurement_opportunities",
            "Every discovered hint needs a measure, exclude, or unresolved decision: " + ", ".join(missing_discovery_hints),
        )
    missing_discovery_journeys = sorted(known_discovery_journeys - set(coverage_ids))
    if missing_discovery_journeys:
        issue(
            issues,
            "error",
            "DISCOVERY_JOURNEY_COVERAGE_MISSING",
            "$.journey_coverage",
            "Discovered journeys missing from coverage: " + ", ".join(missing_discovery_journeys),
        )
    covered_discovery_variants = set().union(*coverage_variants_by_journey.values()) if coverage_variants_by_journey else set()
    missing_discovery_variants = sorted(known_discovery_variants - covered_discovery_variants)
    if missing_discovery_variants:
        issue(
            issues,
            "error",
            "DISCOVERY_VARIANT_COVERAGE_MISSING",
            "$.journey_coverage",
            "Discovered journey variants missing from coverage: " + ", ".join(missing_discovery_variants),
        )

    gaps_by_journey: dict[str, list[dict[str, Any]]] = {}
    gaps_by_variant: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for gap in gaps:
        gap_journey_id = str(gap.get("journey_id", ""))
        gap_variant_id = str(gap.get("variant_id", ""))
        gaps_by_journey.setdefault(gap_journey_id, []).append(gap)
        if gap_variant_id:
            gaps_by_variant.setdefault((gap_journey_id, gap_variant_id), []).append(gap)
        if delivery and gap.get("material") is True and gap.get("resolution") == "unresolved":
            issue(
                issues,
                "error",
                "MATERIAL_COVERAGE_GAP_UNRESOLVED",
                "$.coverage_gaps",
                f"Material coverage gap '{gap.get('gap_id')}' is unresolved.",
            )

    for index, coverage in enumerate(coverages):
        status = str(coverage.get("status", ""))
        journey_id = str(coverage.get("journey_id", ""))
        material = coverage.get("material") is True
        refs = coverage.get("evidence_refs", [])
        if status in {"observed", "confirmed", "planned"} and not refs:
            issue(
                issues,
                "error",
                "JOURNEY_COVERAGE_EVIDENCE_MISSING",
                f"$.journey_coverage[{index}].evidence_refs",
                f"Journey '{journey_id}' with status '{status}' needs evidence.",
            )
        if delivery and material and status in {"partial", "blocked"}:
            resolved = any(
                gap.get("resolution") in {"confirmed_elsewhere", "excluded", "blocked"}
                for gap in gaps_by_journey.get(journey_id, [])
            )
            if not resolved:
                issue(
                    issues,
                    "error",
                    "MATERIAL_JOURNEY_BOUNDARY_MISSING",
                    f"$.journey_coverage[{index}]",
                    (f"Material journey '{journey_id}' is {status} without a resolved coverage boundary."),
                )
        material_opportunity_variants = {
            str(opportunity.get("variant_id", ""))
            for opportunity in opportunities
            if opportunity.get("journey_id") == journey_id
            and opportunity.get("material") is True
            and opportunity.get("variant_id")
        }
        for variant_index, variant in enumerate(coverage.get("variant_coverage", [])):
            if not isinstance(variant, dict):
                continue
            variant_id = str(variant.get("variant_id", ""))
            variant_status = str(variant.get("status", ""))
            variant_material = variant.get("material") is True
            variant_refs = variant.get("evidence_refs", [])
            variant_path = f"$.journey_coverage[{index}].variant_coverage[{variant_index}]"
            if variant_status in {"observed", "confirmed", "planned"} and not variant_refs:
                issue(
                    issues,
                    "error",
                    "JOURNEY_VARIANT_EVIDENCE_MISSING",
                    f"{variant_path}.evidence_refs",
                    f"Variant '{variant_id}' with status '{variant_status}' needs evidence.",
                )
            if delivery and variant_material and variant_id not in material_opportunity_variants:
                issue(
                    issues,
                    "error",
                    "MATERIAL_VARIANT_OPPORTUNITY_MISSING",
                    variant_path,
                    f"Material variant '{variant_id}' needs an explicit measurement-opportunity decision.",
                )
            if delivery and variant_material and variant_status in {"partial", "blocked"}:
                variant_resolved = any(
                    gap.get("resolution") in {"confirmed_elsewhere", "excluded", "blocked"}
                    for gap in gaps_by_variant.get((journey_id, variant_id), [])
                )
                if not variant_resolved:
                    issue(
                        issues,
                        "error",
                        "MATERIAL_VARIANT_BOUNDARY_MISSING",
                        variant_path,
                        f"Material variant '{variant_id}' is {variant_status} without a resolved variant boundary.",
                    )

    domains_by_id = {str(domain.get("domain_id", "")): domain for domain in domains}

    if plan is not None:
        if context.get("target_state") != plan.get("document", {}).get("target_state"):
            issue(
                issues,
                "error",
                "TARGET_STATE_MISMATCH",
                "$.target_state",
                "Analysis context and tracking plan must describe the same target state.",
            )
        plan_language = str(plan.get("document", {}).get("language", ""))
        if language_decision.get("language") != plan_language:
            issue(
                issues,
                "error",
                "WORKBOOK_LANGUAGE_DECISION_MISMATCH",
                "$.language_decision.language",
                "The plan language must equal the evidence-backed language decision.",
            )

        plan_journeys = {str(item.get("journey_id", "")): item for item in plan.get("journeys", []) if isinstance(item, dict)}
        coverage_by_id = {str(item.get("journey_id", "")): item for item in coverages}
        for journey_id, journey in plan_journeys.items():
            coverage = coverage_by_id.get(journey_id)
            if coverage is None:
                issue(
                    issues,
                    "error",
                    "JOURNEY_COVERAGE_MISSING",
                    "$.journey_coverage",
                    f"Plan journey '{journey_id}' has no coverage record.",
                )
                continue
            if coverage.get("status") != journey.get("status"):
                issue(
                    issues,
                    "error",
                    "JOURNEY_STATUS_MISMATCH",
                    "$.journey_coverage",
                    (f"Journey '{journey_id}' is '{journey.get('status')}' in the plan and '{coverage.get('status')}' in analysis context."),
                )
        extra_coverage = sorted(set(coverage_by_id) - set(plan_journeys))
        if extra_coverage:
            issue(
                issues,
                "warning",
                "JOURNEY_COVERAGE_NOT_IN_PLAN",
                "$.journey_coverage",
                "Coverage exists for journeys absent from the plan: " + ", ".join(extra_coverage),
            )

        opportunity_by_id = {str(item.get("opportunity_id", "")): item for item in opportunities}
        plan_events = {str(item.get("event_name", "")): item for item in plan.get("events", []) if isinstance(item, dict)}
        referenced_events: set[str] = set()
        for opportunity_index, opportunity in enumerate(opportunities):
            journey_id = str(opportunity.get("journey_id", ""))
            if journey_id not in plan_journeys:
                issue(
                    issues,
                    "error",
                    "OPPORTUNITY_UNKNOWN_JOURNEY",
                    f"$.measurement_opportunities[{opportunity_index}].journey_id",
                    f"Opportunity references unknown journey '{journey_id}'.",
                )
            for event_name in opportunity.get("event_names", []):
                event_name = str(event_name)
                event = plan_events.get(event_name)
                if event is None:
                    issue(
                        issues,
                        "error",
                        "OPPORTUNITY_UNKNOWN_EVENT",
                        f"$.measurement_opportunities[{opportunity_index}].event_names",
                        f"Opportunity references unknown event '{event_name}'.",
                    )
                    continue
                referenced_events.add(event_name)
                if journey_id not in event.get("journey_ids", []):
                    issue(
                        issues,
                        "error",
                        "OPPORTUNITY_EVENT_JOURNEY_MISMATCH",
                        f"$.measurement_opportunities[{opportunity_index}].event_names",
                        f"Event '{event_name}' does not belong to journey '{journey_id}'.",
                    )
                classification = str(event.get("classification", ""))
                if opportunity.get("official_fit") == "fit" and classification not in {
                    "official",
                    "official_ecommerce",
                }:
                    issue(
                        issues,
                        "error",
                        "OFFICIAL_FIT_EVENT_MISMATCH",
                        f"$.measurement_opportunities[{opportunity_index}]",
                        f"Official fit for '{opportunity.get('opportunity_id')}' must map to an official event.",
                    )
                if opportunity.get("official_fit") == "gap" and classification != "custom":
                    issue(
                        issues,
                        "error",
                        "OFFICIAL_GAP_EVENT_MISMATCH",
                        f"$.measurement_opportunities[{opportunity_index}]",
                        f"Official gap for '{opportunity.get('opportunity_id')}' must map to a justified custom event.",
                    )

        for event_name, event in plan_events.items():
            if event.get("classification") == "context":
                continue
            declared_ids = {str(value) for value in event.get("measurement_opportunity_ids", [])}
            unknown = sorted(declared_ids - set(opportunity_by_id))
            if unknown:
                issue(
                    issues,
                    "error",
                    "EVENT_UNKNOWN_OPPORTUNITY",
                    f"$.events[{event_name!r}].measurement_opportunity_ids",
                    "Unknown opportunity IDs: " + ", ".join(unknown),
                )
            for opportunity_id in declared_ids & set(opportunity_by_id):
                opportunity = opportunity_by_id[opportunity_id]
                if event_name not in opportunity.get("event_names", []):
                    issue(
                        issues,
                        "error",
                        "EVENT_OPPORTUNITY_BACKLINK_MISSING",
                        f"$.events[{event_name!r}].measurement_opportunity_ids",
                        f"Opportunity '{opportunity_id}' does not map back to event '{event_name}'.",
                    )
            if event_name not in referenced_events:
                issue(
                    issues,
                    "error",
                    "EVENT_WITHOUT_MEASUREMENT_OPPORTUNITY",
                    f"$.events[{event_name!r}]",
                    "Every non-context event must resolve a measured opportunity.",
                )

        parameters = _plan_parameters(plan)
        for event_name, index, parameter in parameters:
            refs = [str(value) for value in parameter.get("value_evidence_refs", [])]
            unknown_domains = sorted(set(refs) - set(domains_by_id))
            if unknown_domains:
                issue(
                    issues,
                    "error",
                    "UNKNOWN_VALUE_DOMAIN",
                    f"$.events[{event_name!r}].parameters[{index}].value_evidence_refs",
                    "Unknown value-domain IDs: " + ", ".join(unknown_domains),
                )
            if not refs:
                issue(
                    issues,
                    "error" if delivery else "warning",
                    "VALUE_DOMAIN_MISSING",
                    f"$.events[{event_name!r}].parameters[{index}]",
                    (f"Parameter '{parameter.get('name')}' must reference the finite or dynamic domain decision used to define its values."),
                )
            for domain_id in refs:
                domain = domains_by_id.get(domain_id)
                if domain is None:
                    continue
                if domain.get("parameter_name") != parameter.get("name") or domain.get("scope") != parameter.get("scope"):
                    issue(
                        issues,
                        "error",
                        "VALUE_DOMAIN_SEMANTIC_MISMATCH",
                        f"$.events[{event_name!r}].parameters[{index}]",
                        f"Value domain '{domain_id}' belongs to another parameter or scope.",
                    )
                event_names = domain.get("event_names") or []
                if event_names and event_name not in event_names:
                    issue(
                        issues,
                        "error",
                        "VALUE_DOMAIN_EVENT_MISMATCH",
                        f"$.events[{event_name!r}].parameters[{index}]",
                        f"Value domain '{domain_id}' does not apply to event '{event_name}'.",
                    )
                if domain.get("kind") == "finite" and domain.get("complete") is True:
                    if _normalized_values(domain.get("values")) != _normalized_values(parameter.get("allowed_values")):
                        issue(
                            issues,
                            "error",
                            "FINITE_VALUE_DOMAIN_MISMATCH",
                            f"$.events[{event_name!r}].parameters[{index}].allowed_values",
                            (f"Allowed values for '{parameter.get('name')}' do not match complete evidence domain '{domain_id}'."),
                        )
                if domain.get("kind") == "dynamic" and parameter.get("allowed_values"):
                    issue(
                        issues,
                        "error",
                        "DYNAMIC_DOMAIN_HAS_ALLOWED_VALUES",
                        f"$.events[{event_name!r}].parameters[{index}].allowed_values",
                        f"Dynamic value domain '{domain_id}' cannot be presented as exhaustive.",
                    )
                if domain.get("normalization") != parameter.get("value_mode"):
                    issue(
                        issues,
                        "error",
                        "VALUE_DOMAIN_MODE_MISMATCH",
                        f"$.events[{event_name!r}].parameters[{index}].value_mode",
                        f"Value mode does not match evidence domain '{domain_id}'.",
                    )
                if parameter.get("value_mode") == "controlled_semantic" and domain.get("value_language") != plan.get("document", {}).get("language"):
                    issue(
                        issues,
                        "error",
                        "VALUE_DOMAIN_LANGUAGE_MISMATCH",
                        f"$.events[{event_name!r}].parameters[{index}].value_language",
                        f"Controlled domain '{domain_id}' must use the workbook language.",
                    )

        document_language = str(plan.get("document", {}).get("language", ""))
        for domain_index, domain in enumerate(domains):
            if domain.get("normalization") != "controlled_semantic":
                continue
            if domain.get("value_language") != document_language:
                issue(
                    issues,
                    "error",
                    "CONTROLLED_DOMAIN_LANGUAGE_MISMATCH",
                    f"$.value_domains[{domain_index}].value_language",
                    "Controlled semantic values must use the selected workbook language.",
                )
            if domain.get("kind") != "finite":
                continue
            values = domain.get("values", [])
            labels = domain.get("value_labels", [])
            label_values = [item.get("value") for item in labels if isinstance(item, dict)]
            if _normalized_values(values) != _normalized_values(label_values):
                issue(
                    issues,
                    "error",
                    "CONTROLLED_VALUE_LABEL_INVENTORY_MISMATCH",
                    f"$.value_domains[{domain_index}].value_labels",
                    "Every finite controlled value needs exactly one localized label.",
                )
            if len(label_values) != len(_normalized_values(label_values)):
                issue(
                    issues,
                    "error",
                    "CONTROLLED_VALUE_LABEL_DUPLICATE",
                    f"$.value_domains[{domain_index}].value_labels",
                    "Controlled value labels contain duplicate value entries.",
                )
            for label_index, label in enumerate(labels):
                if not isinstance(label, dict):
                    continue
                if label.get("language") != document_language:
                    issue(
                        issues,
                        "error",
                        "CONTROLLED_VALUE_LABEL_LANGUAGE_MISMATCH",
                        f"$.value_domains[{domain_index}].value_labels[{label_index}].language",
                        "The localized value label must use the selected workbook language.",
                    )
                value = label.get("value")
                if isinstance(value, str) and _ascii_slug(str(label.get("label", ""))) != value:
                    issue(
                        issues,
                        "error",
                        "CONTROLLED_VALUE_LABEL_SLUG_MISMATCH",
                        f"$.value_domains[{domain_index}].value_labels[{label_index}]",
                        "The technical value must be the ASCII snake_case normalization of its localized label.",
                    )

        for domain_index, domain in enumerate(domains):
            if (
                delivery
                and domain.get("parameter_name") in LIKELY_FINITE_PARAMETERS
                and domain.get("kind") == "dynamic"
                and domain.get("dynamic_reason") == "not_observable"
            ):
                issue(
                    issues,
                    "warning",
                    "LIKELY_FINITE_DOMAIN_NOT_EXHAUSTED",
                    f"$.value_domains[{domain_index}]",
                    (
                        f"Likely finite parameter '{domain.get('parameter_name')}' was not "
                        "exhausted. Run targeted rendered discovery or record a stronger "
                        "dynamic reason such as over_50."
                    ),
                )

        for domain_index, domain in enumerate(domains):
            matching = [
                (event_name, parameter)
                for event_name, _index, parameter in parameters
                if parameter.get("name") == domain.get("parameter_name")
                and parameter.get("scope") == domain.get("scope")
                and (not domain.get("event_names") or event_name in domain.get("event_names", []))
            ]
            if not matching:
                issue(
                    issues,
                    "warning",
                    "VALUE_DOMAIN_UNUSED",
                    f"$.value_domains[{domain_index}]",
                    f"Value domain '{domain.get('domain_id')}' is not used by the plan.",
                )

    return issues


def main() -> int:
    args = parse_args()
    try:
        context = load_json(args.context)
        plan = load_json(args.plan) if args.plan else None
        issues = validate_analysis_context(
            context,
            plan,
            delivery=args.delivery,
            schema_path=args.schema,
        )
        for message in validate_discovery_bindings(
            context,
            args.discovery_report,
            require_live_report=args.delivery,
        ):
            issue(
                issues,
                "error",
                "DISCOVERY_BINDING_INVALID",
                "$.discovery_reports",
                message,
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([item.__dict__ for item in issues], indent=2, ensure_ascii=False))
    elif issues:
        print(render_text(issues))
    has_error = any(item.severity == "error" for item in issues)
    has_warning = any(item.severity == "warning" for item in issues)
    return int(has_error or (args.delivery and has_warning))


if __name__ == "__main__":
    raise SystemExit(main())
