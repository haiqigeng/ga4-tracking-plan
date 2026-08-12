from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from discovery_contract import (
    load_discovery_report,
    report_hint_ids,
    report_journey_ids,
    report_variant_ids,
    sha256_file,
)
from discovery_quality import merge_discovery_reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Create an analysis-context seed in which every rendered discovery hint is an explicit unresolved measurement opportunity.")
    )
    parser.add_argument(
        "discovery_report",
        type=Path,
        nargs="+",
        help="One or more same-site discovery reports from the same fresh run.",
    )
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--source-id", default="live_site")
    parser.add_argument("--target-state", choices=["as_is", "to_be", "hybrid"], default="as_is")
    parser.add_argument("--scope-claim", choices=["whole_site", "journey_subset"], default="whole_site")
    parser.add_argument("--language", help="Explicit workbook language, for example fr or en-GB.")
    parser.add_argument(
        "--language-basis",
        choices=["user", "template", "team", "audience", "website"],
        help="Evidence that takes precedence for the workbook language.",
    )
    parser.add_argument("--language-reasoning", help="Concise explanation for the language decision.")
    return parser.parse_args()


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not slug or not slug[0].isalpha():
        slug = f"{fallback}_{slug}".rstrip("_")
    return slug[:79]


def build_analysis_context_seed(
    report: dict[str, Any],
    report_path: Path,
    *,
    source_id: str = "live_site",
    target_state: str = "as_is",
    scope_claim: str = "whole_site",
    language: str | None = None,
    language_basis: str | None = None,
    language_reasoning: str | None = None,
) -> dict[str, Any]:
    observed_language = str(report["language_summary"]["primary_language"])
    if language_basis and language_basis != "website" and not language:
        raise ValueError("An explicit --language is required when language basis is not website.")
    selected_language = language or observed_language
    selected_basis = language_basis or ("user" if language else "website")
    report_id = str(report["report_id"])
    run_id = str(report.get("run_id", ""))
    ledger = [item for item in report.get("journey_coverage_ledger", []) if isinstance(item, dict)]
    hints = [item for item in report.get("measurement_opportunity_hints", []) if isinstance(item, dict)]
    opportunities: list[dict[str, Any]] = []
    opportunity_ids_by_journey: dict[str, list[str]] = {}
    for hint in hints:
        hint_id = str(hint["hint_id"])
        hint_key = str(hint.get("hint_key", hint_id))
        journey_id = str(hint["journey_id"])
        variant_id = str(hint.get("variant_id", ""))
        opportunity_id = _slug(f"opportunity_{hint_id}", "opportunity")
        opportunities.append(
            {
                "opportunity_id": opportunity_id,
                "journey_id": journey_id,
                **({"variant_id": variant_id} if variant_id else {}),
                "name": hint_key.replace("_", " ").title(),
                "category": hint["category"],
                "material": hint.get("materiality") == "material",
                "evidence_status": "observed",
                "evidence_refs": [source_id],
                "business_question": f"What decision should the observed {hint_key.replace('_', ' ')} support?",
                "official_candidate": "pending_official_evaluation",
                "official_fit": "not_applicable",
                "decision": "unresolved",
                "decision_reason": "Pending analyst review against current official GA4 semantics and the business need.",
                "event_names": [],
                "discovery_hint_ids": [hint_id],
            }
        )
        opportunity_ids_by_journey.setdefault(journey_id, []).append(opportunity_id)

    journey_coverage: list[dict[str, Any]] = []
    for item in ledger:
        journey_id = str(item["journey_id"])
        status = str(item.get("status", "partial"))
        variant_coverage = [
            {
                "variant_id": str(variant["variant_id"]),
                "material": bool(variant.get("material")),
                "status": str(variant.get("status", "partial")),
                "evidence_refs": [source_id] if variant.get("evidence_urls") else [],
                "entry_points": variant.get("entry_points", []),
                "states_covered": variant.get("states_covered", []),
                "notes": "Seeded from the rendered discovery report.",
            }
            for variant in item.get("variant_coverage", [])
            if isinstance(variant, dict) and variant.get("variant_id")
        ]
        journey_coverage.append(
            {
                "journey_id": journey_id,
                "material": bool(item.get("material")),
                "status": status,
                "evidence_refs": [source_id] if item.get("evidence_urls") else [],
                "entry_points": item.get("entry_points", []),
                "states_covered": item.get("states_covered", []),
                "variants": item.get("variants", []),
                "variant_coverage": variant_coverage,
                "opportunity_ids": sorted(opportunity_ids_by_journey.get(journey_id, [])),
                "notes": "Seeded from the hash-bound rendered discovery report; resolve opportunities before delivery.",
            }
        )

    coverage_gaps = []
    for index, gap in enumerate(report.get("coverage_gaps", []), start=1):
        if not isinstance(gap, dict):
            continue
        coverage_gaps.append(
            {
                "gap_id": _slug(str(gap.get("gap_id", f"discovery_gap_{index}")), "gap"),
                **({"journey_id": str(gap["journey_id"])} if gap.get("journey_id") else {}),
                **({"variant_id": str(gap["variant_id"])} if gap.get("variant_id") else {}),
                "material": bool(gap.get("material", True)),
                **({"evidence_state": str(gap["evidence_state"])} if gap.get("evidence_state") else {}),
                "resolution": "unresolved",
                "description": str(gap.get("description", "Discovery coverage gap.")),
                "evidence_refs": [source_id],
            }
        )

    language_source_id = "language_decision_context"
    if language_source_id == source_id:
        language_source_id = "workbook_language_context"
    language_evidence_refs = [source_id] if selected_basis == "website" else [language_source_id]
    language_reason = language_reasoning or (
        "Selected from the rendered html lang evidence summarized by website discovery."
        if selected_basis == "website"
        else f"Selected from explicit {selected_basis} context, which takes precedence over website language evidence."
    )
    sources = [
        {
            "source_id": source_id,
            "source_type": "live_website",
            "reference": report["root_url"],
            "sha256": sha256_file(report_path),
            "evidence_role": "live_behavior",
            "state": "as_is",
            "supports": sorted(
                [*report_journey_ids(report), *report_variant_ids(report), *report_hint_ids(report)]
            )
            or ["rendered_site_discovery"],
        }
    ]
    if selected_basis != "website":
        sources.append(
            {
                "source_id": language_source_id,
                "source_type": "business_document" if selected_basis == "template" else "user_input",
                "reference": f"Explicit workbook language decision: {selected_language}",
                "evidence_role": "historical_contract" if selected_basis == "template" else "business_requirement",
                "state": "both",
                "supports": ["workbook_language"],
            }
        )

    return {
        **(
            {
                "context_version": "1.0.0",
                "run_id": run_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
            if run_id
            else {}
        ),
        "target_state": target_state,
        "scope_claim": scope_claim,
        "language_decision": {
            "language": selected_language,
            "basis": selected_basis,
            "evidence_refs": language_evidence_refs,
            "observed_website_languages": report["language_summary"]["observed_languages"],
            "reasoning": language_reason,
        },
        "sources": sources,
        "discovery_reports": [
            {
                "report_id": report_id,
                **({"run_id": run_id} if run_id else {}),
                "source_id": source_id,
                "reference": str(report_path.resolve()),
                "sha256": sha256_file(report_path),
                "generated_at": report["generated_at"],
                "outcome": report["outcome"],
                "hint_ids": report_hint_ids(report),
                "journey_ids": report_journey_ids(report),
                "variant_ids": report_variant_ids(report),
            }
        ],
        "journey_coverage": journey_coverage,
        "coverage_gaps": coverage_gaps,
        "measurement_opportunities": opportunities,
        "value_domains": [],
        "assumptions": [],
        "official_checks": [],
    }


def build_analysis_context_seed_from_reports(
    reports: list[tuple[dict[str, Any], Path]],
    *,
    source_id: str = "live_site",
    target_state: str = "as_is",
    scope_claim: str = "whole_site",
    language: str | None = None,
    language_basis: str | None = None,
    language_reasoning: str | None = None,
) -> dict[str, Any]:
    ordered = sorted(reports, key=lambda item: (str(item[0].get("report_id", "")), str(item[1].resolve())))
    if not ordered:
        raise ValueError("At least one discovery report is required.")
    if len(ordered) > 1:
        run_ids = [str(report.get("run_id", "")) for report, _ in ordered]
        if not all(run_ids) or len(set(run_ids)) != 1:
            raise ValueError("Multiple discovery reports require one explicit shared run_id.")
    primary_languages = {
        str(report["language_summary"]["primary_language"])
        for report, _ in ordered
    }
    if len(primary_languages) > 1 and not language:
        raise ValueError("Discovery reports disagree on website language; provide an explicit language decision.")
    merged = merge_discovery_reports([report for report, _ in ordered])
    context = build_analysis_context_seed(
        merged,
        ordered[0][1],
        source_id=source_id,
        target_state=target_state,
        scope_claim=scope_claim,
        language=language,
        language_basis=language_basis,
        language_reasoning=language_reasoning,
    )
    context["discovery_reports"] = [
        {
            "report_id": str(report["report_id"]),
            **({"run_id": str(context["run_id"])} if context.get("run_id") else {}),
            "source_id": source_id,
            "reference": str(path.resolve()),
            "sha256": sha256_file(path),
            "generated_at": report["generated_at"],
            "outcome": report["outcome"],
            "hint_ids": report_hint_ids(report),
            "journey_ids": report_journey_ids(report),
            "variant_ids": report_variant_ids(report),
        }
        for report, path in ordered
    ]
    supports = sorted(
        {
            value
            for report, _ in ordered
            for value in [
                *report_journey_ids(report),
                *report_variant_ids(report),
                *report_hint_ids(report),
            ]
        }
    ) or ["rendered_site_discovery"]
    live_source = next(
        source
        for source in context["sources"]
        if source.get("source_id") == source_id
    )
    live_source["reference"] = str(merged["root_url"])
    live_source["supports"] = supports
    if len(ordered) > 1:
        live_source.pop("sha256", None)
    return context


def main() -> int:
    args = parse_args()
    try:
        reports = [
            (load_discovery_report(path), path)
            for path in args.discovery_report
        ]
        context = build_analysis_context_seed_from_reports(
            reports,
            source_id=args.source_id,
            target_state=args.target_state,
            scope_claim=args.scope_claim,
            language=args.language,
            language_basis=args.language_basis,
            language_reasoning=args.language_reasoning,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(context, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
