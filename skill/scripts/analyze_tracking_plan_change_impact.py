from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from maintenance_analysis import analyze_change_impact
from tracking_plan_model import load_json
from validate_analysis_context import validate_analysis_context
from validate_tracking_plan import render_text, validate_plan

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Map a business change to affected tracking-plan semantics and downstream contracts.")
    parser.add_argument("plan", type=Path)
    parser.add_argument("change_request", type=Path)
    parser.add_argument("--analysis-context", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    return parser.parse_args()


def _schema_errors(value: dict, schema: Path) -> list[str]:
    validator = Draft202012Validator(load_json(schema), format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(value)]


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.plan)
        request = load_json(args.change_request)
        context = load_json(args.analysis_context) if args.analysis_context else None
        issues = validate_plan(plan)
        if context is not None:
            issues.extend(validate_analysis_context(context, plan))
        if issues:
            raise ValueError("Impact inputs are invalid:\n" + render_text(issues))
        request_errors = _schema_errors(
            request,
            ROOT / "references" / "schema-change-request.json",
        )
        if request_errors:
            raise ValueError("Change request is invalid:\n- " + "\n- ".join(request_errors))
        report = analyze_change_impact(plan, request, context)
        report_errors = _schema_errors(
            report,
            ROOT / "references" / "schema-impact-report.json",
        )
        if report_errors:
            raise ValueError("Generated impact report is invalid:\n- " + "\n- ".join(report_errors))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 1 if report["unresolved_selectors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
