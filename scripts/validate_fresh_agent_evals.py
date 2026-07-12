from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "skill" / "references" / "02-commands" / "fresh-agent-evaluation-cases.json"
REQUIRED_CATEGORIES = {"whole_site_ecommerce", "lead_generation", "client_template", "screenshot_evidence"}
SEVERITIES = {"blocking", "quality"}
REAL_DOMAIN_RE = re.compile(r"https?://([^/\s]+)", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or score the GA4 skill fresh-agent acceptance suite.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Evaluation case manifest.")
    parser.add_argument("--results", type=Path, help="Completed evaluation results to score.")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    cases = manifest.get("cases")
    if manifest.get("version") != "1.0":
        errors.append("Manifest version must be 1.0.")
    if not isinstance(cases, list) or len(cases) < 4:
        return [*errors, "Manifest must contain at least four fresh-agent cases."]
    case_ids: set[str] = set()
    categories: set[str] = set()
    for index, case in enumerate(cases):
        base = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{base} must be an object.")
            continue
        case_id = str(case.get("case_id", ""))
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{base}.case_id must use lowercase ASCII snake_case.")
        elif case_id in case_ids:
            errors.append(f"Duplicate case_id: {case_id}.")
        case_ids.add(case_id)
        categories.add(str(case.get("category", "")))
        prompt = str(case.get("prompt", ""))
        if len(prompt.split()) < 20:
            errors.append(f"{base}.prompt is too short to be reproducible.")
        for domain in REAL_DOMAIN_RE.findall(prompt):
            domain = domain.rstrip(".,;:)")
            if domain.lower() != "example.com" and not domain.lower().endswith(".example.com"):
                errors.append(f"{base}.prompt contains a non-generic domain: {domain}.")
        required = case.get("required_outcomes")
        prohibited = case.get("prohibited_outcomes")
        if not isinstance(required, list) or not required:
            errors.append(f"{base}.required_outcomes must be a non-empty list.")
            required = []
        if not isinstance(prohibited, list) or not prohibited:
            errors.append(f"{base}.prohibited_outcomes must be a non-empty list.")
            prohibited = []
        criterion_ids: set[str] = set()
        for criterion in required:
            criterion_id = str(criterion.get("criterion_id", "")) if isinstance(criterion, dict) else ""
            if not criterion_id or criterion_id in criterion_ids:
                errors.append(f"{base} has a missing or duplicate required criterion_id.")
            criterion_ids.add(criterion_id)
            if not isinstance(criterion, dict) or criterion.get("severity") not in SEVERITIES:
                errors.append(f"{base}.{criterion_id or 'required'} must use severity blocking or quality.")
            if not isinstance(criterion, dict) or len(str(criterion.get("description", "")).split()) < 5:
                errors.append(f"{base}.{criterion_id or 'required'} needs a clear description.")
        for criterion in prohibited:
            criterion_id = str(criterion.get("criterion_id", "")) if isinstance(criterion, dict) else ""
            if not criterion_id or criterion_id in criterion_ids:
                errors.append(f"{base} has a missing or duplicate prohibited criterion_id.")
            criterion_ids.add(criterion_id)
            if not isinstance(criterion, dict) or len(str(criterion.get("description", "")).split()) < 5:
                errors.append(f"{base}.{criterion_id or 'prohibited'} needs a clear description.")
    missing = sorted(REQUIRED_CATEGORIES - categories)
    if missing:
        errors.append(f"Manifest is missing required categories: {', '.join(missing)}.")
    return errors


def score_results(manifest: dict, results: dict) -> list[str]:
    errors: list[str] = []
    supplied = {
        str(item.get("case_id", "")): item
        for item in results.get("case_results", [])
        if isinstance(item, dict)
    }
    quality_total = 0
    quality_passed = 0
    for case in manifest["cases"]:
        case_id = case["case_id"]
        result = supplied.get(case_id)
        if not result:
            errors.append(f"Missing result for case {case_id}.")
            continue
        required_results = result.get("required_outcomes", {})
        prohibited_results = result.get("prohibited_outcomes", {})
        for criterion in case["required_outcomes"]:
            criterion_id = criterion["criterion_id"]
            status = required_results.get(criterion_id) if isinstance(required_results, dict) else None
            if status not in {"pass", "fail"}:
                errors.append(f"{case_id}.{criterion_id} must be pass or fail.")
                continue
            if criterion["severity"] == "blocking" and status != "pass":
                errors.append(f"Blocking criterion failed: {case_id}.{criterion_id}.")
            if criterion["severity"] == "quality":
                quality_total += 1
                quality_passed += status == "pass"
        for criterion in case["prohibited_outcomes"]:
            criterion_id = criterion["criterion_id"]
            status = prohibited_results.get(criterion_id) if isinstance(prohibited_results, dict) else None
            if status not in {"absent", "present"}:
                errors.append(f"{case_id}.{criterion_id} must be absent or present.")
            elif status == "present":
                errors.append(f"Prohibited outcome present: {case_id}.{criterion_id}.")
    minimum = float(manifest.get("pass_rule", {}).get("quality_criteria_minimum_ratio", 1.0))
    if quality_total and quality_passed / quality_total < minimum:
        errors.append(f"Quality criteria pass ratio is {quality_passed}/{quality_total}; minimum is {minimum:.0%}.")
    return errors


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    errors = validate_manifest(manifest)
    if not errors and args.results:
        errors.extend(score_results(manifest, load_json(args.results)))
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"Fresh-agent evaluation manifest passed ({len(manifest['cases'])} cases).")
    if args.results:
        print("Fresh-agent evaluation results passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
