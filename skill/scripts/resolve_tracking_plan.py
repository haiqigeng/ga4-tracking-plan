from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from official_ga4_catalog import catalog_receipt_signature, enrich_plan_official_semantics, load_catalog, load_parameter_library, load_scenario_library
from official_source_receipt import finalize_receipt, receipt_validation_errors, tracking_plan_sha256
from validate_tracking_plan import render_text, validate_plan_data

RULES_DIR = Path(__file__).resolve().parents[1] / "references" / "03-rules"
RECOMMENDED_CATALOG = load_catalog(RULES_DIR / "library-ga4-recommended-events.json")
SCENARIO_LIBRARY = load_scenario_library(RULES_DIR / "library-ga4-event-scenarios.json")
PARAMETER_LIBRARY = load_parameter_library(RULES_DIR / "library-parameters.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve official GA4 semantics and bind a live source-check receipt before validation and rendering."
    )
    parser.add_argument("plan", type=Path, help="Draft tracking-plan JSON.")
    parser.add_argument("--receipt", type=Path, required=True, help="Live receipt produced by check_official_catalog.py.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Resolved tracking-plan JSON.")
    return parser.parse_args()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def resolve_plan(plan: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    publish_date = date.fromisoformat(str(plan.get("document", {}).get("publish_date", "")))
    expected_urls = {
        str(source.get("url", "")).split("#", 1)[0].rstrip("/")
        for source in plan.get("documentation_sources_checked", [])
        if isinstance(source, dict) and source.get("source_type") == "official" and source.get("url")
    }
    receipt_errors = receipt_validation_errors(
        receipt,
        publish_date=publish_date,
        expected_urls=expected_urls,
        expected_catalog_signature=catalog_receipt_signature(RECOMMENDED_CATALOG),
        expected_draft_plan_sha256=tracking_plan_sha256(plan),
    )
    if receipt_errors:
        raise ValueError("Official-source receipt is not publishable:\n- " + "\n- ".join(receipt_errors))
    language = str(plan.get("language_policy", {}).get("workbook_language", "en"))
    resolved = enrich_plan_official_semantics(
        plan,
        RECOMMENDED_CATALOG,
        SCENARIO_LIBRARY,
        PARAMETER_LIBRARY,
        overwrite_official=language == "en",
    )
    checked_date = datetime.fromisoformat(str(receipt["checked_at"]).replace("Z", "+00:00")).date().isoformat()
    for source in resolved.get("documentation_sources_checked", []):
        if isinstance(source, dict) and source.get("source_type") == "official":
            source["checked_date"] = checked_date
    bound_receipt = dict(receipt)
    bound_receipt["resolved_plan_sha256"] = tracking_plan_sha256(resolved)
    resolved["official_source_check"] = finalize_receipt(bound_receipt)
    return resolved


def main() -> int:
    args = parse_args()
    try:
        resolved = resolve_plan(_load_object(args.plan), _load_object(args.receipt))
    except (ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    issues = validate_plan_data(resolved)
    if issues:
        print(render_text(issues), file=sys.stderr)
    if any(issue.severity == "error" for issue in issues):
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
