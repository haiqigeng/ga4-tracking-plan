from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "maintenance" / "evaluations" / "fresh-agent-evaluation-cases.json"
REQUIRED_CATEGORIES = {"whole_site_ecommerce", "lead_generation", "client_template", "screenshot_evidence"}
SEVERITIES = {"blocking", "quality"}
REAL_DOMAIN_RE = re.compile(r"https?://([^/\s]+)", re.I)
MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["version", "cases"],
    "properties": {
        "version": {"const": "1.0"},
        "pass_rule": {
            "type": "object",
            "properties": {
                "quality_criteria_minimum_ratio": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "cases": {
            "type": "array",
            "minItems": 4,
            "allOf": [
                {
                    "contains": {
                        "type": "object",
                        "required": ["category"],
                        "properties": {"category": {"const": category}},
                    }
                }
                for category in sorted(REQUIRED_CATEGORIES)
            ],
            "items": {
                "type": "object",
                "required": ["case_id", "category", "title", "prompt", "required_outcomes", "prohibited_outcomes"],
                "properties": {
                    "case_id": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                    "category": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "prompt": {"type": "string", "pattern": r"^\S+(?:\s+\S+){19,}"},
                    "required_outcomes": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["criterion_id", "severity", "description"],
                            "properties": {
                                "criterion_id": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                                "severity": {"enum": sorted(SEVERITIES)},
                                "description": {"type": "string", "pattern": r"^\S+(?:\s+\S+){4,}"},
                            },
                        },
                    },
                    "prohibited_outcomes": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["criterion_id", "description"],
                            "properties": {
                                "criterion_id": {"type": "string", "pattern": "^[a-z0-9_]+$"},
                                "description": {"type": "string", "pattern": r"^\S+(?:\s+\S+){4,}"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or score the GA4 skill fresh-agent acceptance suite.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Evaluation case manifest.")
    parser.add_argument("--results", type=Path, required=True, help="Completed results from actual fresh-agent sessions.")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def validate_manifest(manifest: dict) -> list[str]:
    errors = [f"{error.json_path}: {error.message}" for error in Draft202012Validator(MANIFEST_SCHEMA).iter_errors(manifest)]
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        return errors
    valid_cases = [case for case in cases if isinstance(case, dict)]
    case_ids = Counter(str(case.get("case_id", "")) for case in valid_cases)
    errors.extend(f"Duplicate case_id: {case_id}." for case_id, count in case_ids.items() if case_id and count > 1)
    for index, case in enumerate(valid_cases):
        prompt = str(case.get("prompt", ""))
        for domain in REAL_DOMAIN_RE.findall(prompt):
            domain = domain.rstrip(".,;:)")
            if domain.lower() != "example.com" and not domain.lower().endswith(".example.com"):
                errors.append(f"cases[{index}].prompt contains a non-generic domain: {domain}.")
        match case:
            case {"required_outcomes": list() as required, "prohibited_outcomes": list() as prohibited}:
                criterion_ids = Counter(
                    str(criterion.get("criterion_id", ""))
                    for criterion in [*required, *prohibited]
                    if isinstance(criterion, dict)
                )
                errors.extend(
                    f"cases[{index}] has a duplicate criterion_id: {criterion_id}."
                    for criterion_id, count in criterion_ids.items()
                    if criterion_id and count > 1
                )
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
    if not errors:
        errors.extend(score_results(manifest, load_json(args.results)))
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"Fresh-agent evaluation results passed ({len(manifest['cases'])} cases).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
