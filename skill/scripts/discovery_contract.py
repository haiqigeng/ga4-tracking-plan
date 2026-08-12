from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contract_utils import sha256_file
from discovery_quality import coverage_gap_identity, merge_evidence_coverage_statuses
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_SCHEMA = ROOT / "references" / "schema-discovery-report.json"


def validate_discovery_report(report: dict[str, Any]) -> list[str]:
    schema = json.loads(DISCOVERY_SCHEMA.read_text(encoding="utf-8-sig"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(report),
        key=lambda error: list(error.absolute_path),
    )
    messages = [f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in errors]
    for index, candidate in enumerate(report.get("finite_value_candidates", [])):
        if not isinstance(candidate, dict) or "capture_status" not in candidate:
            continue
        values = candidate.get("values", [])
        captured = int(candidate.get("captured_value_count", -1))
        observed = int(candidate.get("observed_value_count", -1))
        status = str(candidate.get("capture_status", ""))
        complete = candidate.get("complete") is True
        path = f"finite_value_candidates/{index}"
        if captured != len(values):
            messages.append(f"{path}: captured_value_count must equal the number of retained unique values")
        if complete != (status == "complete"):
            messages.append(f"{path}: complete must be true exactly when capture_status is complete")
        if status == "complete" and not (captured == observed <= 50):
            messages.append(f"{path}: complete capture requires captured_value_count == observed_value_count <= 50")
        if status == "over_50" and observed <= 50:
            messages.append(f"{path}: over_50 requires observed_value_count above 50")
    return messages


def load_discovery_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(report, dict):
        raise ValueError(f"Discovery report must be a JSON object: {path}")
    errors = validate_discovery_report(report)
    if errors:
        raise ValueError(f"Discovery report is invalid ({path}):\n- " + "\n- ".join(errors))
    return report


def report_hint_ids(report: dict[str, Any]) -> list[str]:
    return sorted(str(item["hint_id"]) for item in report.get("measurement_opportunity_hints", []) if isinstance(item, dict) and item.get("hint_id"))


def report_journey_ids(report: dict[str, Any]) -> list[str]:
    return sorted(str(item["journey_id"]) for item in report.get("journey_coverage_ledger", []) if isinstance(item, dict) and item.get("journey_id"))


def report_variant_ids(report: dict[str, Any]) -> list[str]:
    return sorted(
        str(variant["variant_id"])
        for journey in report.get("journey_coverage_ledger", [])
        if isinstance(journey, dict)
        for variant in journey.get("variant_coverage", [])
        if isinstance(variant, dict) and variant.get("variant_id")
    )


def validate_discovery_bindings(
    context: dict[str, Any],
    report_paths: list[Path],
    *,
    require_live_report: bool,
) -> list[str]:
    errors: list[str] = []
    records = {str(item.get("report_id")): item for item in context.get("discovery_reports", []) if isinstance(item, dict) and item.get("report_id")}
    context_run_id = str(context.get("run_id", ""))
    supplied: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in report_paths:
        try:
            report = load_discovery_report(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(str(error))
            continue
        report_id = str(report["report_id"])
        if report_id in supplied:
            errors.append(f"Discovery report '{report_id}' was supplied more than once.")
            continue
        supplied[report_id] = (path, report)

    live_source_ids = {
        str(item.get("source_id")) for item in context.get("sources", []) if isinstance(item, dict) and item.get("source_type") == "live_website"
    }
    if require_live_report and live_source_ids and not records:
        errors.append("Live-website delivery requires at least one hash-bound discovery report.")
    if require_live_report and set(records) != set(supplied):
        missing = sorted(set(records) - set(supplied))
        extra = sorted(set(supplied) - set(records))
        if missing:
            errors.append("Context discovery reports not supplied: " + ", ".join(missing))
        if extra:
            errors.append("Supplied discovery reports absent from context: " + ", ".join(extra))

    known_hints: dict[str, tuple[str, str]] = {}
    known_journeys: set[str] = set()
    known_variants: set[str] = set()
    report_journey_statuses: dict[str, str] = {}
    report_variant_statuses: dict[tuple[str, str], str] = {}
    report_gap_states: dict[tuple[str, ...], str] = {}
    for report_id, record in sorted(records.items()):
        record_run_id = str(record.get("run_id", ""))
        if record_run_id != context_run_id:
            errors.append(f"Discovery report '{report_id}' does not belong to context run '{context_run_id}'.")
        if str(record.get("source_id")) not in live_source_ids:
            errors.append(f"Discovery report '{report_id}' must bind to a live_website source.")
        pair = supplied.get(report_id)
        if pair is None:
            continue
        path, report = pair
        report_run_id = str(report.get("run_id", ""))
        if report_run_id and report_run_id != record_run_id:
            errors.append(f"Discovery run identifier mismatch for '{report_id}'.")
        digest = sha256_file(path)
        if digest != str(record.get("sha256")):
            errors.append(f"Discovery report hash mismatch for '{report_id}'.")
        hints = report_hint_ids(report)
        journeys = report_journey_ids(report)
        variants = report_variant_ids(report)
        if hints != sorted(str(value) for value in record.get("hint_ids", [])):
            errors.append(f"Discovery hint inventory mismatch for '{report_id}'.")
        if journeys != sorted(str(value) for value in record.get("journey_ids", [])):
            errors.append(f"Discovery journey inventory mismatch for '{report_id}'.")
        if variants != sorted(str(value) for value in record.get("variant_ids", [])):
            errors.append(f"Discovery variant inventory mismatch for '{report_id}'.")
        if str(report.get("outcome")) != str(record.get("outcome")):
            errors.append(f"Discovery outcome mismatch for '{report_id}'.")
        if record.get("generated_at") and str(report.get("generated_at")) != str(record.get("generated_at")):
            errors.append(f"Discovery generation timestamp mismatch for '{report_id}'.")
        for hint in report.get("measurement_opportunity_hints", []):
            if isinstance(hint, dict) and hint.get("hint_id"):
                hint_id = str(hint["hint_id"])
                journey_id = str(hint.get("journey_id", ""))
                variant_id = str(hint.get("variant_id", ""))
                hint_context = (journey_id, variant_id)
                if hint_id in known_hints and known_hints[hint_id] != hint_context:
                    errors.append(f"Discovery hint '{hint_id}' maps to conflicting journey variants.")
                known_hints[hint_id] = hint_context
        known_journeys.update(journeys)
        known_variants.update(variants)
        for journey in report.get("journey_coverage_ledger", []):
            if not isinstance(journey, dict):
                continue
            journey_id = str(journey.get("journey_id", ""))
            journey_status = str(journey.get("status", ""))
            existing_journey_status = report_journey_statuses.get(journey_id)
            report_journey_statuses[journey_id] = (
                merge_evidence_coverage_statuses([existing_journey_status, journey_status])
                if existing_journey_status
                else journey_status
            )
            for variant in journey.get("variant_coverage", []):
                if isinstance(variant, dict) and variant.get("variant_id"):
                    key = (journey_id, str(variant["variant_id"]))
                    variant_status = str(variant.get("status", ""))
                    existing_variant_status = report_variant_statuses.get(key)
                    report_variant_statuses[key] = (
                        merge_evidence_coverage_statuses([existing_variant_status, variant_status])
                        if existing_variant_status
                        else variant_status
                    )
        for gap in report.get("coverage_gaps", []):
            if isinstance(gap, dict) and gap.get("gap_id") and gap.get("evidence_state"):
                identity = coverage_gap_identity(gap)
                gap_state = str(gap["evidence_state"])
                existing_gap_state = report_gap_states.get(identity)
                if existing_gap_state and existing_gap_state != gap_state:
                    if identity[0] == "interaction_recipe":
                        report_gap_states[identity] = merge_evidence_coverage_statuses(
                            [existing_gap_state, gap_state]
                        )
                    else:
                        errors.append(
                            f"Coverage gap '{gap.get('gap_id')}' has conflicting factual states: "
                            f"'{existing_gap_state}' and '{gap_state}'."
                        )
                else:
                    report_gap_states[identity] = gap_state

    mapped_hints: set[str] = set()
    for opportunity in context.get("measurement_opportunities", []):
        if not isinstance(opportunity, dict):
            continue
        for value in opportunity.get("discovery_hint_ids", []):
            hint_id = str(value)
            mapped_hints.add(hint_id)
            if hint_id not in known_hints:
                errors.append(f"Opportunity '{opportunity.get('opportunity_id')}' references unknown discovery hint '{hint_id}'.")
            elif known_hints[hint_id] != (
                str(opportunity.get("journey_id")),
                str(opportunity.get("variant_id", "")),
            ):
                errors.append(f"Opportunity '{opportunity.get('opportunity_id')}' and hint '{hint_id}' use different journey variants.")
    missing_hints = sorted(set(known_hints) - mapped_hints)
    if missing_hints:
        errors.append("Discovered hints without an explicit measure/exclude/unresolved opportunity: " + ", ".join(missing_hints))
    covered_journeys = {str(item.get("journey_id")) for item in context.get("journey_coverage", []) if isinstance(item, dict)}
    missing_journeys = sorted(known_journeys - covered_journeys)
    if missing_journeys:
        errors.append("Discovered journeys missing from journey_coverage: " + ", ".join(missing_journeys))
    covered_variants = {
        str(variant.get("variant_id"))
        for journey in context.get("journey_coverage", [])
        if isinstance(journey, dict)
        for variant in journey.get("variant_coverage", [])
        if isinstance(variant, dict) and variant.get("variant_id")
    }
    missing_variants = sorted(known_variants - covered_variants)
    if missing_variants:
        errors.append("Discovered journey variants missing from journey_coverage: " + ", ".join(missing_variants))
    for coverage in context.get("journey_coverage", []):
        if not isinstance(coverage, dict):
            continue
        journey_id = str(coverage.get("journey_id", ""))
        report_status = report_journey_statuses.get(journey_id)
        context_status = str(coverage.get("status", ""))
        if context_status == "observed" and report_status in {"partial", "not_tested", "externally_blocked", "blocked"}:
            errors.append(
                f"Journey '{journey_id}' is marked observed although rendered discovery "
                f"recorded '{report_status}'. Use confirmed with other evidence or retain "
                "the factual boundary."
            )
        if context_status in {"externally_blocked", "blocked"} and report_status == "not_tested":
            errors.append(f"Journey '{journey_id}' was not tested and cannot be relabelled externally blocked.")
        for variant in coverage.get("variant_coverage", []):
            if not isinstance(variant, dict):
                continue
            variant_id = str(variant.get("variant_id", ""))
            report_variant_status = report_variant_statuses.get((journey_id, variant_id))
            context_variant_status = str(variant.get("status", ""))
            if context_variant_status == "observed" and report_variant_status in {"partial", "not_tested", "externally_blocked", "blocked"}:
                errors.append(
                    f"Variant '{variant_id}' is marked observed although rendered discovery recorded '{report_variant_status}'."
                )
            if context_variant_status in {"externally_blocked", "blocked"} and report_variant_status == "not_tested":
                errors.append(f"Variant '{variant_id}' was not tested and cannot be relabelled externally blocked.")
    for gap in context.get("coverage_gaps", []):
        if not isinstance(gap, dict):
            continue
        gap_id = str(gap.get("gap_id", ""))
        report_state = report_gap_states.get(coverage_gap_identity(gap))
        context_state = str(gap.get("evidence_state", ""))
        if report_state and context_state and report_state != context_state:
            errors.append(
                f"Coverage gap '{gap_id}' changed factual evidence_state from '{report_state}' to '{context_state}'."
            )
    return errors
