from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from browser_environment import (
    inspect_browser_environment,
    load_playwright_sync_api,
    resolve_browser_channel,
)
from discover_site_journeys import canonical_url, same_host
from discover_site_journeys_playwright import (
    accept_privacy_statement,
    launch_browser,
)
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "references" / "schema-interactive-journey.json"
TRANSACTION_PATTERN = re.compile(
    r"(?:place\s+order|pay\s+now|confirm\s+order|commander|payer|confirmer\s+la\s+commande)",
    re.I,
)
COLLECT_HOST_PATTERN = re.compile(r"(?:google-analytics\.com|analytics\.google\.com)$", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute a bounded, synthetic, non-transactional browser journey and capture "
            "action-window dataLayer and GA4 request evidence."
        )
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--screenshot-dir", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=20000)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument(
        "--browser",
        choices=["auto", "chromium", "chrome", "msedge", "firefox", "webkit"],
        default="auto",
    )
    return parser.parse_args()


def load_and_validate_spec(path: Path) -> dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(spec),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        rendered = "\n".join(
            f"- {'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Interactive journey specification is invalid:\n{rendered}")
    if any(action.get("action") == "submit" for action in spec["actions"]):
        if spec.get("submission_kind") not in {
            "lead",
            "authentication",
            "search",
            "other_non_transactional",
        }:
            raise ValueError("Transactional or unclassified form submission is not allowed.")
    return spec


def synthetic_value(kind: str) -> str:
    values = {
        "first_name": "Test",
        "last_name": "Analytics",
        "email": "ga4-synthetic-journey@example.com",
        "phone": "0600000000",
        "postal_code": "75001",
        "city": "Paris",
        "address": "1 rue du Test",
        "text": "Test analytics",
        "integer": "1",
    }
    return values[kind]


def _safe_measurement_request(url: str) -> dict[str, Any] | None:
    parsed = urlparse(url)
    if not COLLECT_HOST_PATTERN.search(parsed.hostname or "") or not parsed.path.endswith(
        "/collect"
    ):
        return None
    query = parse_qs(parsed.query)
    return {
        "host": parsed.hostname,
        "path": parsed.path,
        "measurement_id": (query.get("tid") or [None])[0],
        "event_name": (query.get("en") or [None])[0],
        "parameter_names": sorted(
            key for key in query if key.startswith(("ep.", "epn.", "up.", "upn."))
        ),
    }


def _expected_result(page: Any, expected: dict[str, Any] | None) -> dict[str, Any]:
    if not expected:
        return {"declared": False, "passed": None, "checks": []}
    checks: list[dict[str, Any]] = []
    if expected.get("url_contains"):
        passed = str(expected["url_contains"]) in page.url
        checks.append({"check": "url_contains", "value": expected["url_contains"], "passed": passed})
    if expected.get("selector_visible"):
        try:
            passed = page.locator(str(expected["selector_visible"])).first.is_visible(timeout=1500)
        except Exception:
            passed = False
        checks.append(
            {"check": "selector_visible", "value": expected["selector_visible"], "passed": passed}
        )
    if expected.get("text_visible"):
        try:
            passed = page.get_by_text(str(expected["text_visible"]), exact=False).first.is_visible(
                timeout=1500
            )
        except Exception:
            passed = False
        checks.append({"check": "text_visible", "value": expected["text_visible"], "passed": passed})
    return {
        "declared": True,
        "passed": bool(checks) and all(item["passed"] for item in checks),
        "checks": checks,
    }


def _guard_click(locator: Any, *, allow_submit: bool, explicit_submit: bool) -> None:
    tag = str(locator.evaluate("element => element.tagName.toLowerCase()"))
    element_type = str(
        locator.evaluate("element => (element.getAttribute('type') || '').toLowerCase()")
    )
    label = str(
        locator.evaluate(
            "element => (element.innerText || element.value || element.getAttribute('aria-label') || '').trim()"
        )
    )
    form_action = str(
        locator.evaluate(
            "element => element.form ? (element.form.action || document.location.href) : ''"
        )
    )
    is_submit = tag == "input" and element_type == "submit" or (
        tag == "button" and element_type in {"", "submit"}
    )
    if TRANSACTION_PATTERN.search(f"{label} {form_action}"):
        raise ValueError("Purchase/payment confirmation is never allowed by this helper.")
    if is_submit and (not explicit_submit or not allow_submit):
        raise ValueError(
            "A form-submit control must use action=submit and allow_form_submission=true."
        )


CAPTURE_INIT_SCRIPT = r"""
(() => {
  const sensitiveKey = /(?:^|_)(?:email|e_mail|phone|mobile|first_name|last_name|firstname|lastname|address|postal|postcode|zip|user_id|customer_id)(?:$|_)/i;
  const sanitize = (value, key = "", depth = 0) => {
    if (sensitiveKey.test(key)) return "[redacted]";
    if (depth > 6) return "[depth-limited]";
    if (value === null || ["string", "number", "boolean"].includes(typeof value)) return value;
    if (Array.isArray(value)) return value.slice(0, 25).map(item => sanitize(item, key, depth + 1));
    if (typeof value === "object") {
      const result = {};
      Object.entries(value).slice(0, 50).forEach(([childKey, child]) => {
        result[childKey] = sanitize(child, childKey, depth + 1);
      });
      return result;
    }
    return `[${typeof value}]`;
  };
  window.dataLayer = Array.isArray(window.dataLayer) ? window.dataLayer : [];
  const originalPush = window.dataLayer.push.bind(window.dataLayer);
  window.dataLayer.push = (...items) => {
    items.forEach(item => {
      try { window.__ga4SkillCapture(sanitize(item)); } catch (_) {}
    });
    return originalPush(...items);
  };
})();
"""


def run(spec: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    root_url = canonical_url(str(spec["root_url"]))
    sync_playwright = load_playwright_sync_api()
    browser_environment = inspect_browser_environment()
    channel = resolve_browser_channel(args.browser, browser_environment)
    captured_pushes: list[dict[str, Any]] = []
    captured_requests: list[dict[str, Any]] = []
    active_action = {"index": -1}

    def receive_push(_source: Any, payload: Any) -> None:
        captured_pushes.append({"action_index": active_action["index"], "payload": payload})

    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = launch_browser(playwright, channel, headless=not args.headful)
        context = browser.new_context()
        context.expose_binding("__ga4SkillCapture", receive_push)
        context.add_init_script(CAPTURE_INIT_SCRIPT)
        page = context.new_page()

        def capture_request(request: Any) -> None:
            evidence = _safe_measurement_request(request.url)
            if evidence:
                captured_requests.append({"action_index": active_action["index"], **evidence})

        page.on("request", capture_request)
        for index, action in enumerate(spec["actions"]):
            active_action["index"] = index
            before_push = len(captured_pushes)
            before_request = len(captured_requests)
            before_url = page.url
            action_type = str(action["action"])
            result: dict[str, Any] = {
                "index": index,
                "action": action_type,
                "before_url": before_url,
                "status": "completed",
            }
            try:
                if action_type == "goto":
                    target = canonical_url(str(action["url"]))
                    if not same_host(target, root_url):
                        raise ValueError(f"Cross-host navigation is outside scope: {target}")
                    page.goto(target, wait_until="domcontentloaded", timeout=args.timeout_ms)
                    page.wait_for_timeout(350)
                    result["privacy_statement_accepted"] = accept_privacy_statement(page)
                elif action_type == "accept_privacy":
                    result["privacy_statement_accepted"] = accept_privacy_statement(page)
                elif action_type == "wait":
                    page.wait_for_timeout(int(action["milliseconds"]))
                else:
                    locator = page.locator(str(action["selector"])).first
                    locator.wait_for(state="visible", timeout=args.timeout_ms)
                    if action_type in {"click", "submit"}:
                        _guard_click(
                            locator,
                            allow_submit=bool(spec.get("allow_form_submission")),
                            explicit_submit=action_type == "submit",
                        )
                        locator.click(timeout=args.timeout_ms)
                    elif action_type == "fill":
                        locator.fill(synthetic_value(str(action["value_kind"])))
                        result["synthetic_value_kind"] = action["value_kind"]
                    elif action_type == "select":
                        locator.select_option(str(action["select_value"]))
                    elif action_type == "check":
                        locator.check(timeout=args.timeout_ms)
                page.wait_for_timeout(500)
                result["expected"] = _expected_result(page, action.get("expected"))
                if result["expected"].get("passed") is False:
                    result["status"] = "failed_expectation"
            except Exception as error:
                result["status"] = "blocked"
                result["error"] = f"{type(error).__name__}: {error}"
            result["after_url"] = page.url
            result["data_layer_pushes"] = captured_pushes[before_push:]
            result["ga4_requests"] = captured_requests[before_request:]
            if args.screenshot_dir:
                args.screenshot_dir.mkdir(parents=True, exist_ok=True)
                screenshot = args.screenshot_dir / f"{index + 1:02d}-{action_type}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                result["screenshot"] = str(screenshot)
            results.append(result)
            if result["status"] == "blocked":
                break
        context.close()
        browser.close()

    blocked = any(item["status"] == "blocked" for item in results)
    failed_expectation = any(
        item["status"] == "failed_expectation" for item in results
    )
    return {
        "journey_id": spec["journey_id"],
        "root_url": root_url,
        "outcome": "blocked" if blocked else ("partial" if failed_expectation else "completed"),
        "browser": {"requested": args.browser, "selected_channel": channel},
        "used_synthetic_value_kinds": sorted(
            {
                str(action["value_kind"])
                for action in spec["actions"]
                if action.get("value_kind")
            }
        ),
        "privacy_acceptance_default": True,
        "form_submission_authorized": bool(spec.get("allow_form_submission")),
        "submission_kind": spec.get("submission_kind"),
        "actions": results,
        "summary": {
            "completed_action_count": sum(item["status"] == "completed" for item in results),
            "captured_data_layer_push_count": len(captured_pushes),
            "captured_ga4_request_count": len(captured_requests),
        },
    }


def main() -> int:
    args = parse_args()
    try:
        spec = load_and_validate_spec(args.spec)
        output = run(spec, args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0 if output["outcome"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
