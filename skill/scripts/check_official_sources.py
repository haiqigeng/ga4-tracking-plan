from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlparse
from urllib.request import Request, urlopen

from official_ga4_catalog import normalize, normalize_type, parse_catalog_html
from tracking_plan_model import load_json

ALLOWED_HOSTS = {"developers.google.com", "support.google.com"}
RECOMMENDED_EVENTS_BASE = (
    "https://developers.google.com/analytics/devguides/collection/ga4/reference/events"
)
ROOT = Path(__file__).resolve().parents[1]
LOCAL_CATALOG = ROOT / "references" / "library-ga4-recommended-events.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify every selected official GA4 source used by a tracking plan."
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Validate source declarations without requesting Google documentation.",
    )
    return parser.parse_args()


def source_declarations(plan: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for event in plan.get("events", []):
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event_name", ""))
        source = event.get("official_source")
        if isinstance(source, dict):
            result.append(
                {
                    "owner": f"event:{event_name}",
                    "url": str(source.get("url", "")),
                    "section": str(source.get("section", "")),
                    "wording_origin": str(source.get("wording_origin", "")),
                }
            )
        for parameter in event.get("parameters", []):
            if not isinstance(parameter, dict):
                continue
            source = parameter.get("official_source")
            if isinstance(source, dict):
                result.append(
                    {
                        "owner": (
                            f'parameter:{event_name}:{parameter.get("name", "")}:'
                            f'{parameter.get("scope", "")}'
                        ),
                        "url": str(source.get("url", "")),
                        "section": str(source.get("section", "")),
                        "wording_origin": str(source.get("wording_origin", "")),
                    }
                )
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in result:
        unique[(item["owner"], item["url"], item["section"])] = item
    return list(unique.values())


def fetch(url: str) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={"User-Agent": "ga4-tracking-plan-official-source-check/2.0"},
    )
    with urlopen(request, timeout=45) as response:
        content = response.read().decode("utf-8", "ignore")
        return int(getattr(response, "status", 200)), response.geturl(), content


def anchor_present(content: str, fragment: str) -> bool:
    if not fragment:
        return True
    escaped = re.escape(fragment)
    return bool(
        re.search(rf'\bid=["\']{escaped}["\']', content, flags=re.IGNORECASE)
        or re.search(rf'\bname=["\']{escaped}["\']', content, flags=re.IGNORECASE)
    )


def catalog_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(record.get("event")): record
        for record in records
        if isinstance(record, dict) and record.get("event")
    }


def parameter_index(record: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(parameter.get("name")), str(parameter.get("scope", "event"))): parameter
        for parameter in record.get("parameters", [])
        if isinstance(parameter, dict) and parameter.get("name")
    }


def semantic_errors(
    plan: dict[str, Any],
    pages: dict[str, dict[str, Any]],
) -> list[str]:
    page = pages.get(RECOMMENDED_EVENTS_BASE, {})
    content = str(page.get("content", ""))
    if not content:
        return []
    live_records = parse_catalog_html(content)
    live = catalog_index(live_records)
    local_records = json.loads(LOCAL_CATALOG.read_text(encoding="utf-8-sig"))
    local = catalog_index(local_records)
    errors: list[str] = []
    checked_names: set[str] = set()
    for event in plan.get("events", []):
        if not isinstance(event, dict) or event.get("classification") not in {
            "official",
            "official_ecommerce",
        }:
            continue
        event_name = str(event.get("event_name", ""))
        source_base, _ = urldefrag(str(event.get("official_source", {}).get("url", "")))
        if source_base != RECOMMENDED_EVENTS_BASE:
            continue
        checked_names.add(event_name)
        live_event = live.get(event_name)
        if not live_event:
            errors.append(
                f'Selected official event "{event_name}" is absent from the current recommended-events page.'
            )
            continue
        if (
            event.get("official_source", {}).get("wording_origin") == "exact"
            and normalize(event.get("definition")) != normalize(live_event.get("description"))
        ):
            errors.append(
                f'Event "{event_name}" no longer matches the current official definition.'
            )
        live_parameters = parameter_index(live_event)
        for parameter in event.get("parameters", []):
            if not isinstance(parameter, dict) or parameter.get("classification") != "official":
                continue
            parameter_source_base, _ = urldefrag(
                str(parameter.get("official_source", {}).get("url", ""))
            )
            if parameter_source_base != RECOMMENDED_EVENTS_BASE:
                continue
            key = (
                str(parameter.get("name", "")),
                str(parameter.get("scope", "event")),
            )
            live_parameter = live_parameters.get(key)
            if not live_parameter:
                errors.append(
                    f'Official parameter "{key[0]}" ({key[1]}) is absent from the current "{event_name}" table.'
                )
                continue
            if normalize_type(parameter.get("type")) != normalize_type(live_parameter.get("type")):
                errors.append(
                    f'Parameter "{event_name}.{key[0]}" no longer matches the current official type.'
                )
            if (
                parameter.get("official_source", {}).get("wording_origin") == "exact"
                and normalize(parameter.get("definition"))
                != normalize(live_parameter.get("description"))
            ):
                errors.append(
                    f'Parameter "{event_name}.{key[0]}" no longer matches the current official definition.'
                )
    for event_name in sorted(checked_names):
        live_event = live.get(event_name)
        local_event = local.get(event_name)
        if not live_event or not local_event:
            if live_event and not local_event:
                errors.append(
                    f'The bundled official library is missing selected event "{event_name}".'
                )
            continue
        if (
            normalize(live_event.get("description"))
            != normalize(local_event.get("description"))
            or {
                key: (
                    normalize_type(value.get("type")),
                    normalize(value.get("required")),
                    normalize(value.get("description")),
                )
                for key, value in parameter_index(live_event).items()
            }
            != {
                key: (
                    normalize_type(value.get("type")),
                    normalize(value.get("required")),
                    normalize(value.get("description")),
                )
                for key, value in parameter_index(local_event).items()
            }
        ):
            errors.append(
                f'The bundled official library has drifted from Google for selected event "{event_name}".'
            )
    return errors


def check(plan: dict[str, Any], offline: bool = False) -> dict[str, Any]:
    declarations = source_declarations(plan)
    errors: list[str] = []
    pages: dict[str, dict[str, Any]] = {}
    for declaration in declarations:
        base_url, _ = urldefrag(declaration["url"])
        host = (urlparse(base_url).hostname or "").lower()
        if host not in ALLOWED_HOSTS:
            errors.append(
                f'{declaration["owner"]} references a non-official host: {host or "(missing)"}'
            )
            continue
        if offline or base_url in pages:
            continue
        try:
            status, final_url, content = fetch(base_url)
            pages[base_url] = {
                "status": status,
                "final_url": final_url,
                "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "content": content,
            }
            if status != 200:
                errors.append(f"Official source returned HTTP {status}: {base_url}")
        except Exception as error:
            pages[base_url] = {
                "status": 0,
                "final_url": "",
                "content_sha256": "",
                "content": "",
            }
            errors.append(
                f"Could not fetch official source {base_url}: {type(error).__name__}: {error}"
            )

    checks: list[dict[str, Any]] = []
    for declaration in declarations:
        base_url, fragment = urldefrag(declaration["url"])
        page = pages.get(base_url, {})
        anchor_ok = True if offline else anchor_present(str(page.get("content", "")), fragment)
        if not anchor_ok:
            errors.append(
                f'{declaration["owner"]} references missing section "#{fragment}" at {base_url}'
            )
        checks.append(
            {
                **declaration,
                "base_url": base_url,
                "fragment": fragment,
                "reachable": None if offline else page.get("status") == 200,
                "anchor_found": None if offline else anchor_ok,
            }
        )
    if not offline:
        errors.extend(semantic_errors(plan, pages))
    public_pages = [
        {key: value for key, value in page.items() if key != "content"}
        | {"url": url}
        for url, page in pages.items()
    ]
    return {
        "status": "passed" if not errors else "failed",
        "mode": "offline" if offline else "live",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "selected_source_count": len(declarations),
        "pages": public_pages,
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.plan)
        result = check(plan, args.offline)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if result["errors"]:
        print("\n".join(f"ERROR {value}" for value in result["errors"]), file=sys.stderr)
        return 1
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
