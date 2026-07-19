from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from official_ga4_catalog import (
    AUTOMATIC_EVENTS_URL,
    ECOMMERCE_IMPLEMENTATION_URL,
    ECOMMERCE_TRIGGER_GUIDANCE,
    ENHANCED_MEASUREMENT_URL,
    STANDARD_EVENT_OFFICIAL_SEMANTICS,
    catalog_receipt_signature,
    catalog_semantic_signature,
    catalog_signature,
    clean_html,
    normalize_text,
    parse_catalog_html,
)
from official_source_receipt import new_receipt, tracking_plan_sha256

OFFICIAL_URL = "https://developers.google.com/analytics/devguides/collection/ga4/reference/events"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the bundled GA4 recommended-event catalog against official Google documentation.")
    parser.add_argument("--offline", action="store_true", help="Validate bundled metadata without requesting the official page.")
    parser.add_argument("--plan", type=Path, help="Also fetch every official source referenced by this tracking plan.")
    parser.add_argument("--receipt", type=Path, help="Write a machine-verifiable JSON receipt for this check.")
    return parser.parse_args()


def references_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "03-rules"


def load_local_catalog() -> tuple[dict, list[dict]]:
    rules = references_dir()
    library = json.loads((rules / "library-ga4-event-scenarios.json").read_text(encoding="utf-8-sig"))
    recommended = json.loads((rules / "library-ga4-recommended-events.json").read_text(encoding="utf-8-sig"))
    return library, recommended


def validate_metadata(library: dict) -> list[str]:
    errors: list[str] = []
    metadata = library.get("catalog_metadata", {})
    for field in (
        "catalog_schema_version",
        "generated_date",
        "generator_version",
        "official_source_last_updated",
        "ecommerce_source_last_updated",
        "automatic_enhanced_checked_date",
    ):
        if not str(metadata.get(field, "")).strip():
            errors.append(f"Missing catalog_metadata.{field}")
    source_urls = {str(source.get("url", "")) for source in library.get("sources", []) if isinstance(source, dict)}
    missing_sources = sorted({OFFICIAL_URL, ECOMMERCE_IMPLEMENTATION_URL, AUTOMATIC_EVENTS_URL, ENHANCED_MEASUREMENT_URL} - source_urls)
    if missing_sources:
        errors.append(f"Official GA4 sources are missing: {', '.join(missing_sources)}")
    local_standard = {
        str(event.get("event")): event
        for event in library.get("standard_events", [])
        if isinstance(event, dict) and event.get("event")
    }
    missing_standard = sorted(set(STANDARD_EVENT_OFFICIAL_SEMANTICS) - set(local_standard))
    extra_standard = sorted(set(local_standard) - set(STANDARD_EVENT_OFFICIAL_SEMANTICS))
    if missing_standard:
        errors.append(f"Automatic or enhanced-measurement events missing from bundled catalog: {', '.join(missing_standard)}")
    if extra_standard:
        errors.append(f"Bundled standard events have no governed official semantics: {', '.join(extra_standard)}")
    for event_name in sorted(set(STANDARD_EVENT_OFFICIAL_SEMANTICS) & set(local_standard)):
        expected = STANDARD_EVENT_OFFICIAL_SEMANTICS[event_name]
        actual = local_standard[event_name]
        mismatched_fields = [
            field
            for field in ("description", "trigger", "official_trigger", "source_url", "source_section")
            if normalize_text(actual.get(field)) != normalize_text(expected["definition" if field == "description" else field])
        ]
        actual_parameters = tuple(part.strip() for part in str(actual.get("parameters", "")).split(",") if part.strip())
        if actual_parameters != tuple(expected["parameters"]):
            mismatched_fields.append("parameters")
        if mismatched_fields:
            errors.append(f"Bundled official semantics differ for {event_name}: {', '.join(mismatched_fields)}")
    return errors


def fetch_official_page(url: str = OFFICIAL_URL) -> str:
    request = Request(url, headers={"User-Agent": "ga4-tracking-plan-catalog-check/1.0"})
    return urlopen(request, timeout=45).read().decode("utf-8", "ignore")


def fetch_and_record(url: str, pages: dict[str, str], errors: list[str]) -> str:
    try:
        content = fetch_official_page(url)
    except Exception as error:
        errors.append(f"Could not fetch official source {url}: {type(error).__name__}: {error}")
        return ""
    pages[url] = content
    return content


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    args = parse_args()
    library, local_catalog = load_local_catalog()
    errors = validate_metadata(library)
    fetched_pages: dict[str, str] = {}
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig")) if args.plan else None
    if not args.offline:
        page = fetch_and_record(OFFICIAL_URL, fetched_pages, errors)
        official_catalog, official_updated = parse_catalog_html(page)
        official_signature = catalog_signature(official_catalog)
        local_signature = catalog_signature(local_catalog)
        missing = sorted(set(official_signature) - set(local_signature))
        extra = sorted(set(local_signature) - set(official_signature))
        changed = sorted(
            name
            for name in set(official_signature) & set(local_signature)
            if official_signature[name] != local_signature[name]
        )
        official_semantics = catalog_semantic_signature(official_catalog)
        local_semantics = catalog_semantic_signature(local_catalog)
        wording_changed = sorted(
            name
            for name in set(official_semantics) & set(local_semantics)
            if official_semantics[name] != local_semantics[name]
        )
        bundled_updated = str(library.get("catalog_metadata", {}).get("official_source_last_updated", ""))
        ecommerce_page = fetch_and_record(ECOMMERCE_IMPLEMENTATION_URL, fetched_pages, errors)
        ecommerce_text = normalize_text(clean_html(ecommerce_page))
        missing_trigger_guidance = sorted(
            event_name
            for event_name, guidance in ECOMMERCE_TRIGGER_GUIDANCE.items()
            if normalize_text(guidance) not in ecommerce_text
        )
        ecommerce_updated_match = re.search(r"Last updated\s+(\d{4}-\d{2}-\d{2})\s+UTC", ecommerce_page)
        ecommerce_updated = ecommerce_updated_match.group(1) if ecommerce_updated_match else ""
        bundled_ecommerce_updated = str(library.get("catalog_metadata", {}).get("ecommerce_source_last_updated", ""))
        errors.extend(
            message
            for condition, message in (
                (not official_signature, "Could not parse official recommended-event catalog"),
                (missing, f"Events missing from bundled catalog: {', '.join(missing)}"),
                (extra, f"Bundled events absent from official catalog: {', '.join(extra)}"),
                (changed, f"Bundled event parameter definitions differ from official documentation: {', '.join(changed)}"),
                (wording_changed, f"Bundled event or parameter wording differs from official documentation: {', '.join(wording_changed)}"),
                (official_updated not in {"", bundled_updated}, f"Official source date changed from {bundled_updated} to {official_updated}"),
                (
                    missing_trigger_guidance,
                    "Bundled ecommerce trigger guidance differs from official implementation documentation: "
                    + ", ".join(missing_trigger_guidance),
                ),
                (
                    ecommerce_updated not in {"", bundled_ecommerce_updated},
                    f"Official ecommerce source date changed from {bundled_ecommerce_updated} to {ecommerce_updated}",
                ),
            )
            if condition
        )
        for source_url in (AUTOMATIC_EVENTS_URL, ENHANCED_MEASUREMENT_URL):
            fetch_and_record(source_url, fetched_pages, errors)
        standard_pages = {
            source_url: normalize_text(clean_html(fetched_pages.get(source_url, "")))
            for source_url in (AUTOMATIC_EVENTS_URL, ENHANCED_MEASUREMENT_URL)
        }
        for event_name, semantics in STANDARD_EVENT_OFFICIAL_SEMANTICS.items():
            source_text = standard_pages[str(semantics["source_url"])]
            trigger_text = normalize_text(semantics["official_trigger"])
            trigger_position = source_text.find(trigger_text)
            if trigger_position < 0:
                errors.append(f"Bundled {event_name} trigger wording differs from current automatic/enhanced-measurement documentation")
                continue
            evidence_window = source_text[trigger_position : trigger_position + 3000]
            missing_parameters = [
                parameter
                for parameter in semantics["parameters"]
                if normalize_text(parameter) not in evidence_window
            ]
            if missing_parameters:
                errors.append(
                    f"Bundled {event_name} parameters differ from current automatic/enhanced-measurement documentation: "
                    + ", ".join(missing_parameters)
                )
        if isinstance(plan, dict):
            for source in plan.get("documentation_sources_checked", []):
                if not isinstance(source, dict) or source.get("source_type") != "official":
                    continue
                source_url = str(source.get("url", "")).split("#", 1)[0]
                if source_url and source_url not in fetched_pages:
                    fetch_and_record(source_url, fetched_pages, errors)
    if args.receipt:
        receipt = new_receipt(
            status="failed" if errors else "passed",
            mode="offline" if args.offline else "live",
            sources=[
                {"url": url, "content_sha256": _sha256_text(content)}
                for url, content in fetched_pages.items()
            ],
            catalog_signature_sha256=catalog_receipt_signature(local_catalog),
            draft_plan_sha256=tracking_plan_sha256(plan) if isinstance(plan, dict) else "",
            resolved_plan_sha256="",
            errors=errors,
        )
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failure_message = "\n".join(map("ERROR {}".format, errors))
    print(failure_message or "GA4 recommended, ecommerce, automatic, and enhanced-measurement official-source checks passed.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
