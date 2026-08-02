from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_SCHEMA = ROOT / "references" / "schema-discovery-report.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_discovery_report(report: dict[str, Any]) -> list[str]:
    schema = json.loads(DISCOVERY_SCHEMA.read_text(encoding="utf-8-sig"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(report),
        key=lambda error: list(error.absolute_path),
    )
    return [f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in errors]


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
    for report_id, record in records.items():
        if str(record.get("source_id")) not in live_source_ids:
            errors.append(f"Discovery report '{report_id}' must bind to a live_website source.")
        pair = supplied.get(report_id)
        if pair is None:
            continue
        path, report = pair
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
    return errors
