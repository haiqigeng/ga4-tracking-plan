from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from discovery_contract import load_discovery_report
from jsonschema import Draft202012Validator
from maintenance_analysis import detect_context_drift
from tracking_plan_model import load_json
from validate_analysis_context import validate_analysis_context
from validate_tracking_plan import render_text, validate_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect evidence, journey-coverage, and finite-domain drift without changing a plan.")
    parser.add_argument("before_context", type=Path)
    parser.add_argument("after_context", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--before-discovery-report", type=Path)
    parser.add_argument("--after-discovery-report", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        before = load_json(args.before_context)
        after = load_json(args.after_context)
        plan = load_json(args.plan)
        issues = [
            *validate_plan(plan),
            *validate_analysis_context(before),
            *validate_analysis_context(after),
        ]
        if issues:
            raise ValueError("Drift inputs are invalid:\n" + render_text(issues))
        before_discovery = load_discovery_report(args.before_discovery_report) if args.before_discovery_report else None
        after_discovery = load_discovery_report(args.after_discovery_report) if args.after_discovery_report else None
        if bool(before_discovery) != bool(after_discovery):
            raise ValueError("Rendered drift comparison requires both --before-discovery-report and --after-discovery-report.")
        report = detect_context_drift(
            before,
            after,
            plan,
            before_discovery,
            after_discovery,
        )
        report_errors = list(
            Draft202012Validator(load_json(Path(__file__).resolve().parents[1] / "references" / "schema-drift-report.json")).iter_errors(report)
        )
        if report_errors:
            raise ValueError("Generated drift report is invalid:\n- " + "\n- ".join(error.message for error in report_errors))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 1 if report["status"] == "review_required" else 0


if __name__ == "__main__":
    raise SystemExit(main())
