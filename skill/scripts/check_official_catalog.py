from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

OFFICIAL_URL = "https://developers.google.com/analytics/devguides/collection/ga4/reference/events"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the bundled GA4 recommended-event catalog against official Google documentation.")
    parser.add_argument("--offline", action="store_true", help="Validate bundled metadata without requesting the official page.")
    return parser.parse_args()


def references_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "03-rules"


def parse_event_names(page: str) -> set[str]:
    return {
        html.unescape(name).strip()
        for name in re.findall(r'<h3[^>]*id="[^"]+"[^>]*>\s*<code[^>]*>([^<]+)</code>\s*</h3>', page, re.S)
    }


def parse_last_updated(page: str) -> str:
    match = re.search(r"Last updated\s+(\d{4}-\d{2}-\d{2})\s+UTC", page)
    return match.group(1) if match else ""


def load_local_catalog() -> tuple[dict, set[str]]:
    rules = references_dir()
    library = json.loads((rules / "library-ga4-event-scenarios.json").read_text(encoding="utf-8-sig"))
    recommended = json.loads((rules / "library-ga4-recommended-events.json").read_text(encoding="utf-8-sig"))
    return library, {str(item["event"]) for item in recommended if isinstance(item, dict) and item.get("event")}


def validate_metadata(library: dict) -> list[str]:
    errors: list[str] = []
    metadata = library.get("catalog_metadata", {})
    for field in ("catalog_schema_version", "generated_date", "generator_version", "official_source_last_updated"):
        if not str(metadata.get(field, "")).strip():
            errors.append(f"Missing catalog_metadata.{field}")
    sources = [source for source in library.get("sources", []) if source.get("url") == OFFICIAL_URL]
    if not sources:
        errors.append("Official GA4 recommended-event source is missing")
    return errors


def fetch_official_page() -> str:
    request = Request(OFFICIAL_URL, headers={"User-Agent": "ga4-tracking-plan-catalog-check/1.0"})
    return urlopen(request, timeout=45).read().decode("utf-8", "ignore")


def main() -> int:
    args = parse_args()
    library, local_events = load_local_catalog()
    errors = validate_metadata(library)
    if not args.offline:
        page = fetch_official_page()
        official_events = parse_event_names(page)
        if not official_events:
            errors.append("Could not parse official recommended-event names")
        missing = sorted(official_events - local_events)
        extra = sorted(local_events - official_events)
        if missing:
            errors.append(f"Events missing from bundled catalog: {', '.join(missing)}")
        if extra:
            errors.append(f"Bundled events absent from official catalog: {', '.join(extra)}")
        official_updated = parse_last_updated(page)
        bundled_updated = str(library.get("catalog_metadata", {}).get("official_source_last_updated", ""))
        if official_updated and bundled_updated != official_updated:
            errors.append(f"Official source date changed from {bundled_updated} to {official_updated}")
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print("GA4 official catalog check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
