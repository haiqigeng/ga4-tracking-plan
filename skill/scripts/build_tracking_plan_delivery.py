from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from adapt_tracking_plan_workbook import adapt
from check_official_sources import DEFAULT_CACHE, check
from delivery_artifacts import (
    build_handoff,
    event_push_schema,
    expected_events_contract,
)
from diff_tracking_plans import compare
from generate_tracking_plan_workbook import build_workbook
from jsonschema import Draft202012Validator, FormatChecker
from maintenance_analysis import analyze_change_impact, detect_context_drift
from openpyxl import load_workbook
from template_fidelity import (
    add_package_fidelity,
    compare_template_fidelity,
    workbook_fidelity_snapshot,
)
from tracking_plan_model import load_json
from validate_analysis_context import validate_analysis_context
from validate_tracking_plan import render_text, validate_plan
from validate_tracking_plan_workbook import validate_workbook

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release.json"
CONTRACTS = {
    "tracking-plan.schema.json": ROOT / "references" / "schema-tracking-plan.json",
    "analysis-context.schema.json": ROOT / "references" / "schema-analysis-context.json",
    "expected-events.schema.json": ROOT / "references" / "schema-expected-events.json",
    "delivery-handoff.schema.json": ROOT / "references" / "schema-delivery-handoff.json",
    "change-request.schema.json": ROOT / "references" / "schema-change-request.json",
    "drift-report.schema.json": ROOT / "references" / "schema-drift-report.json",
    "impact-report.schema.json": ROOT / "references" / "schema-impact-report.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build an atomic GA4 tracking-plan delivery: lean human workbook, canonical "
            "JSON, machine contracts, official-source evidence, and internal reasoning evidence."
        )
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("analysis_context", type=Path)
    parser.add_argument("--output-dir", "-o", type=Path, required=True)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--previous-plan", type=Path)
    parser.add_argument("--previous-analysis-context", type=Path)
    parser.add_argument("--change-request", type=Path)
    parser.add_argument("--screenshot-dir", type=Path)
    parser.add_argument(
        "--evidence",
        type=Path,
        action="append",
        default=[],
        help="Internal evidence file or directory to copy into the delivery. May be repeated.",
    )
    parser.add_argument(
        "--approval-state",
        choices=["draft", "reviewed", "approved"],
        default="draft",
    )
    parser.add_argument("--approved-by")
    parser.add_argument("--official-offline", action="store_true")
    parser.add_argument("--official-cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--official-cache-ttl-hours", type=float, default=168.0)
    parser.add_argument("--refresh-official", action="store_true")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing output directory after the new bundle passes every gate.",
    )
    return parser.parse_args()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _validate_json(instance: Any, schema_path: Path, label: str) -> None:
    validator = Draft202012Validator(
        load_json(schema_path),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    if errors:
        rendered = "\n".join(
            f"- {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Generated {label} failed its contract:\n{rendered}")


def _copy_evidence(sources: list[Path], destination: Path) -> list[Path]:
    copied: list[Path] = []
    for source in sources:
        if not source.exists():
            raise ValueError(f"Evidence path does not exist: {source}")
        if source.is_dir():
            for child in sorted(path for path in source.rglob("*") if path.is_file()):
                relative = child.relative_to(source)
                target = destination / source.name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
                copied.append(target)
        else:
            target = destination / source.name
            counter = 2
            while target.exists():
                target = destination / f"{source.stem}-{counter}{source.suffix}"
                counter += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def build_delivery(args: argparse.Namespace) -> Path:
    if bool(args.template) != bool(args.mapping):
        raise ValueError("--template and --mapping must be provided together.")
    if args.approval_state == "approved" and not args.approved_by:
        raise ValueError("--approved-by is required for an approved handoff.")
    if args.official_offline and args.approval_state != "draft":
        raise ValueError("Reviewed or approved deliveries require a live official-source check.")

    plan = load_json(args.plan)
    analysis_context = load_json(args.analysis_context)
    plan_issues = validate_plan(plan)
    if plan_issues:
        raise ValueError("Canonical plan gate failed:\n" + render_text(plan_issues))
    context_issues = validate_analysis_context(
        analysis_context,
        plan,
        delivery=True,
    )
    if context_issues:
        raise ValueError("Analysis-context delivery gate failed:\n" + render_text(context_issues))

    official = check(
        plan,
        args.official_offline,
        cache_dir=args.official_cache_dir,
        cache_ttl_hours=args.official_cache_ttl_hours,
        refresh=args.refresh_official,
    )
    if official["errors"]:
        raise ValueError(
            "Official-source gate failed:\n"
            + "\n".join(f"- {error}" for error in official["errors"])
        )

    output = args.output_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.replace:
        raise ValueError(f"Output directory already exists; use --replace: {output}")
    staging = Path(tempfile.mkdtemp(prefix=".ga4-delivery-", dir=output.parent))
    try:
        artifacts: list[tuple[Path, str]] = []
        plan_path = staging / "plan.json"
        _write_json(plan_path, plan)
        artifacts.append((plan_path, "canonical_tracking_plan"))

        internal = staging / "internal"
        context_path = internal / "analysis-context.json"
        official_path = internal / "official-check.json"
        _write_json(context_path, analysis_context)
        _write_json(official_path, official)
        artifacts.extend(
            [
                (context_path, "analysis_evidence_and_coverage"),
                (official_path, "official_source_verification"),
            ]
        )
        if args.previous_analysis_context:
            previous_context = load_json(args.previous_analysis_context)
            previous_context_issues = validate_analysis_context(previous_context)
            if previous_context_issues:
                raise ValueError(
                    "Previous analysis-context input is invalid:\n"
                    + render_text(previous_context_issues)
                )
            drift = detect_context_drift(previous_context, analysis_context, plan)
            _validate_json(
                drift,
                ROOT / "references" / "schema-drift-report.json",
                "evidence drift report",
            )
            drift_path = internal / "drift-report.json"
            _write_json(drift_path, drift)
            artifacts.append((drift_path, "analyst_review_drift_report"))

        if args.change_request:
            change_request = load_json(args.change_request)
            _validate_json(
                change_request,
                ROOT / "references" / "schema-change-request.json",
                "business change request",
            )
            impact = analyze_change_impact(plan, change_request, analysis_context)
            _validate_json(
                impact,
                ROOT / "references" / "schema-impact-report.json",
                "business change impact report",
            )
            if impact["unresolved_selectors"]:
                raise ValueError(
                    "Business change selectors do not resolve in the plan: "
                    + ", ".join(impact["unresolved_selectors"])
                )
            impact_path = internal / "change-impact.json"
            _write_json(impact_path, impact)
            artifacts.append((impact_path, "business_change_impact"))
        for copied in _copy_evidence(args.evidence, internal / "evidence"):
            artifacts.append((copied, "supporting_evidence"))

        contracts_dir = staging / "contracts"
        for name, source in CONTRACTS.items():
            target = contracts_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            artifacts.append((target, "shared_machine_contract"))

        schemas_dir = staging / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)
        for event in plan.get("events", []):
            if not isinstance(event, dict):
                continue
            schema = event_push_schema(event)
            event_name = str(event["event_name"])
            schema_path = schemas_dir / f"{event_name}.schema.json"
            _write_json(schema_path, schema)
            validator = Draft202012Validator(schema)
            example_errors = list(
                validator.iter_errors(event.get("data_layer", {}).get("push", {}))
            )
            if example_errors:
                raise ValueError(
                    f'Generated event schema rejects the canonical push for "{event_name}": '
                    + "; ".join(error.message for error in example_errors)
                )
            artifacts.append((schema_path, "event_push_schema"))

        expected = expected_events_contract(plan)
        _validate_json(
            expected,
            ROOT / "references" / "schema-expected-events.json",
            "expected-events contract",
        )
        expected_path = staging / "expected-events.json"
        _write_json(expected_path, expected)
        artifacts.append((expected_path, "runtime_expected_events_contract"))

        changes: list[dict[str, Any]] = []
        if args.previous_plan:
            previous = load_json(args.previous_plan)
            previous_issues = validate_plan(previous)
            if previous_issues:
                raise ValueError(
                    "Previous-plan diff input is invalid:\n" + render_text(previous_issues)
                )
            difference = compare(previous, plan)
            changes = difference["changes"]
            diff_path = internal / "semantic-diff.json"
            _write_json(diff_path, difference)
            artifacts.append((diff_path, "semantic_change_log"))

        workbook_path = staging / (
            "tracking-plan.xlsm"
            if args.template and args.template.suffix.lower() == ".xlsm"
            else "tracking-plan.xlsx"
        )
        if args.template:
            mapping = load_json(args.mapping)
            workbook = adapt(plan, args.template, mapping)
        else:
            workbook = build_workbook(
                plan,
                changes=changes,
                screenshot_dir=args.screenshot_dir,
            )
        workbook.save(workbook_path)
        if args.template:
            reopened = load_workbook(
                workbook_path,
                data_only=False,
                read_only=False,
                keep_links=True,
                keep_vba=workbook_path.suffix.lower() == ".xlsm",
            )
            fidelity = compare_template_fidelity(
                workbook._ga4_template_fidelity_before,
                workbook_fidelity_snapshot(reopened),
                workbook._ga4_template_fidelity_authorized,
            )
            fidelity = add_package_fidelity(fidelity, args.template, workbook_path)
            if fidelity["violations"]:
                raise ValueError(
                    "Saved supplied-template fidelity gate failed: "
                    + ", ".join(
                        str(item.get("kind")) for item in fidelity["violations"][:12]
                    )
                )
            fidelity_path = internal / "template-fidelity.json"
            _write_json(fidelity_path, fidelity)
            artifacts.append((fidelity_path, "supplied_template_fidelity"))
        workbook_errors = validate_workbook(workbook_path, plan)
        if workbook_errors:
            raise ValueError(
                "Rendered workbook gate failed:\n"
                + "\n".join(f"- {error}" for error in workbook_errors)
            )
        artifacts.append((workbook_path, "human_tracking_plan_workbook"))

        release = load_json(RELEASE)
        handoff = build_handoff(
            skill_version=str(release["version"]),
            plan=plan,
            analysis_context=analysis_context,
            approval_state=args.approval_state,
            approved_by=args.approved_by,
            artifact_paths=artifacts,
            root=staging,
        )
        _validate_json(
            handoff,
            ROOT / "references" / "schema-delivery-handoff.json",
            "delivery handoff",
        )
        _write_json(staging / "handoff.json", handoff)

        if output.exists():
            if output == output.parent or output.parent == output:
                raise ValueError("Refusing to replace a broad output path.")
            shutil.rmtree(output)
        staging.replace(output)
        return output
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def main() -> int:
    args = parse_args()
    try:
        output = build_delivery(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
