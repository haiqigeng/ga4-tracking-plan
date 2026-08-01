from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from tracking_plan_model import load_json
from validate_tracking_plan import Issue, issue, render_text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "references" / "schema-analysis-context.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the internal evidence, journey-coverage, and finite-value "
            "checkpoint used by a GA4 tracking-plan delivery."
        )
    )
    parser.add_argument("context", type=Path)
    parser.add_argument("--plan", type=Path)
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
        path = "$" + "".join(
            f"[{part!r}]" if isinstance(part, str) else f"[{part}]"
            for part in error.absolute_path
        )
        issue(issues, "error", "ANALYSIS_CONTEXT_SCHEMA", path, error.message)
    return issues


def _duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def _normalized_values(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for value in values
    }


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
    coverages = [
        item for item in context.get("journey_coverage", []) if isinstance(item, dict)
    ]
    gaps = [item for item in context.get("coverage_gaps", []) if isinstance(item, dict)]
    domains = [item for item in context.get("value_domains", []) if isinstance(item, dict)]

    source_ids = [str(item.get("source_id", "")) for item in sources]
    coverage_ids = [str(item.get("journey_id", "")) for item in coverages]
    gap_ids = [str(item.get("gap_id", "")) for item in gaps]
    domain_ids = [str(item.get("domain_id", "")) for item in domains]
    for label, values, path in (
        ("source", source_ids, "$.sources"),
        ("journey coverage", coverage_ids, "$.journey_coverage"),
        ("coverage gap", gap_ids, "$.coverage_gaps"),
        ("value domain", domain_ids, "$.value_domains"),
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
    for collection_name, records in (
        ("journey_coverage", coverages),
        ("coverage_gaps", gaps),
        ("value_domains", domains),
    ):
        for index, record in enumerate(records):
            unknown = sorted(
                set(str(value) for value in record.get("evidence_refs", []))
                - known_sources
            )
            if unknown:
                issue(
                    issues,
                    "error",
                    "ANALYSIS_CONTEXT_UNKNOWN_EVIDENCE",
                    f"$.{collection_name}[{index}].evidence_refs",
                    "Unknown evidence source IDs: " + ", ".join(unknown),
                )

    gaps_by_journey: dict[str, list[dict[str, Any]]] = {}
    for gap in gaps:
        gaps_by_journey.setdefault(str(gap.get("journey_id", "")), []).append(gap)
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
                    (
                        f"Material journey '{journey_id}' is {status} without a "
                        "resolved coverage boundary."
                    ),
                )

    domains_by_id = {
        str(domain.get("domain_id", "")): domain
        for domain in domains
    }

    if plan is not None:
        if context.get("target_state") != plan.get("document", {}).get("target_state"):
            issue(
                issues,
                "error",
                "TARGET_STATE_MISMATCH",
                "$.target_state",
                "Analysis context and tracking plan must describe the same target state.",
            )

        plan_journeys = {
            str(item.get("journey_id", "")): item
            for item in plan.get("journeys", [])
            if isinstance(item, dict)
        }
        coverage_by_id = {
            str(item.get("journey_id", "")): item
            for item in coverages
        }
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
                    (
                        f"Journey '{journey_id}' is '{journey.get('status')}' in the "
                        f"plan and '{coverage.get('status')}' in analysis context."
                    ),
                )
        extra_coverage = sorted(set(coverage_by_id) - set(plan_journeys))
        if extra_coverage:
            issue(
                issues,
                "warning",
                "JOURNEY_COVERAGE_NOT_IN_PLAN",
                "$.journey_coverage",
                "Coverage exists for journeys absent from the plan: "
                + ", ".join(extra_coverage),
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
            if (
                parameter.get("allowed_values")
                and not refs
                and not (
                    parameter.get("classification") == "official"
                    and parameter.get("name") == "customer_type"
                    and parameter.get("allowed_values") == ["new", "returning"]
                )
            ):
                issue(
                    issues,
                    "error" if delivery else "warning",
                    "FINITE_VALUE_EVIDENCE_MISSING",
                    f"$.events[{event_name!r}].parameters[{index}]",
                    (
                        f"Finite project-specific parameter '{parameter.get('name')}' "
                        "must reference the evidence domain used to exhaust its values."
                    ),
                )
            for domain_id in refs:
                domain = domains_by_id.get(domain_id)
                if domain is None:
                    continue
                if (
                    domain.get("parameter_name") != parameter.get("name")
                    or domain.get("scope") != parameter.get("scope")
                ):
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
                    if _normalized_values(domain.get("values")) != _normalized_values(
                        parameter.get("allowed_values")
                    ):
                        issue(
                            issues,
                            "error",
                            "FINITE_VALUE_DOMAIN_MISMATCH",
                            f"$.events[{event_name!r}].parameters[{index}].allowed_values",
                            (
                                f"Allowed values for '{parameter.get('name')}' do not match "
                                f"complete evidence domain '{domain_id}'."
                            ),
                        )

        for domain_index, domain in enumerate(domains):
            matching = [
                (event_name, parameter)
                for event_name, _index, parameter in parameters
                if parameter.get("name") == domain.get("parameter_name")
                and parameter.get("scope") == domain.get("scope")
                and (
                    not domain.get("event_names")
                    or event_name in domain.get("event_names", [])
                )
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
