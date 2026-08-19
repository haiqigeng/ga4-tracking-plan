from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "references" / "schema-access-profiles.json"
MFA_PATTERN = re.compile(
    r"(?:multi[- ]factor|two[- ]factor|verification code|one[- ]time password|"
    r"authenticator|mfa|2fa|code de verification|double authentification)",
    re.I,
)
BUILT_IN_CONSEQUENTIAL_PATTERN = re.compile(
    r"(?:pay|payment|payer|paiement|place\s+order|confirm\s+order|commander|"
    r"book\s+appointment|confirmer\s+le\s+rendez-vous|sign\s+contract|signature|"
    r"delete|remove\s+account|supprimer|resilier|cancel\s+contract)",
    re.I,
)


def load_access_profiles(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8-sig"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    messages = [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    ]
    profiles = value.get("profiles", []) if isinstance(value, dict) else []
    identifiers = [str(item.get("profile_id", "")) for item in profiles if isinstance(item, dict)]
    duplicates = sorted({identifier for identifier in identifiers if identifiers.count(identifier) > 1})
    if duplicates:
        messages.append("profiles: duplicate profile_id values: " + ", ".join(duplicates))
    if messages:
        raise ValueError("Access-profile contract is invalid:\n- " + "\n- ".join(messages))
    return value


def normalized_allowed_hosts(profile: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({str(host).strip().casefold().rstrip(".") for host in profile.get("allowed_hosts", []) if str(host).strip()}))


def host_is_allowed(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    candidate = host.casefold().rstrip(".")
    for allowed in allowed_hosts:
        if allowed.startswith("*."):
            suffix = allowed[2:]
            if candidate.endswith("." + suffix) and candidate != suffix:
                return True
        elif candidate == allowed:
            return True
    return False


def url_is_allowed(url: str, profile: dict[str, Any]) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and host_is_allowed(
        parsed.hostname or "",
        normalized_allowed_hosts(profile),
    )


def _synthetic_value(kind: str) -> str:
    return {
        "first_name": "Test",
        "last_name": "Analytics",
        "email": "ga4-synthetic-access@example.com",
        "phone": "0100000000",
        "postal_code": "75001",
        "city": "Paris",
        "address": "1 rue du Test",
        "password": "Synthetic-Analytics-123!",
        "text": "Test analytics",
        "integer": "1",
    }[kind]


def success_predicate_result(page: Any, predicate: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    url_contains = str(predicate.get("url_contains", ""))
    if url_contains:
        checks.append(
            {
                "kind": "url_contains",
                "locator": url_contains,
                "passed": url_contains in str(page.url),
            }
        )
    selector = str(predicate.get("selector_visible", ""))
    if selector:
        try:
            passed = page.locator(selector).first.is_visible(timeout=1500)
        except Exception:
            passed = False
        checks.append(
            {
                "kind": "selector_visible",
                "locator": selector,
                "passed": bool(passed),
            }
        )
    return {"passed": bool(checks) and all(item["passed"] for item in checks), "checks": checks}


def _consequential_pattern(profile: dict[str, Any]) -> re.Pattern[str]:
    extra = [str(value) for value in profile.get("consequential_action_patterns", []) if str(value)]
    if not extra:
        return BUILT_IN_CONSEQUENTIAL_PATTERN
    try:
        return re.compile(
            f"(?:{BUILT_IN_CONSEQUENTIAL_PATTERN.pattern}|{'|'.join(f'(?:{value})' for value in extra)})",
            re.I,
        )
    except re.error as error:
        raise ValueError(f"Invalid consequential_action_patterns expression: {error}") from error


def _run_login_recipe(page: Any, profile: dict[str, Any], timeout_ms: int) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    unsafe = _consequential_pattern(profile)
    for index, action in enumerate(profile.get("login_recipe", [])):
        action_type = str(action["action"])
        result: dict[str, Any] = {
            "index": index,
            "action": action_type,
            "before_url": str(page.url),
            "status": "completed",
        }
        try:
            if action_type == "goto":
                target = str(action["url"])
                if not url_is_allowed(target, profile):
                    raise ValueError("Login recipe target is outside allowed_hosts.")
                page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
            elif action_type == "wait":
                page.wait_for_timeout(int(action["milliseconds"]))
            else:
                selector = str(action["selector"])
                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=timeout_ms)
                if action_type == "click":
                    label = str(
                        locator.evaluate(
                            "element => (element.innerText || element.value || element.getAttribute('aria-label') || '').trim()"
                        )
                    )
                    if unsafe.search(label):
                        raise ValueError("Login recipe reached a configured consequential-action boundary.")
                    locator.click(timeout=timeout_ms)
                elif action_type == "fill":
                    if action.get("value_source") == "environment":
                        environment_name = str(action["environment_name"])
                        if environment_name not in os.environ:
                            raise ValueError(f"Required credential environment variable is unavailable: {environment_name}")
                        value = os.environ[environment_name]
                        result["value_source"] = "environment"
                        result["environment_name"] = environment_name
                    else:
                        value = _synthetic_value(str(action["value_kind"]))
                        result["value_source"] = "synthetic"
                        result["value_kind"] = str(action["value_kind"])
                    locator.fill(value)
                elif action_type == "select":
                    locator.select_option(str(action["select_value"]))
                elif action_type == "check":
                    locator.check(timeout=timeout_ms)
            page.wait_for_timeout(350)
            if not url_is_allowed(str(page.url), profile):
                raise ValueError("Login recipe navigated outside allowed_hosts.")
        except Exception as error:
            result["status"] = "blocked"
            result["error"] = f"{type(error).__name__}: {error}"
        result["after_url"] = str(page.url)
        trace.append(result)
        if result["status"] == "blocked":
            break
        try:
            body = str(page.locator("body").inner_text(timeout=500))
        except Exception:
            body = ""
        if MFA_PATTERN.search(body):
            trace.append(
                {
                    "index": index + 1,
                    "action": "human_verification_boundary",
                    "before_url": str(page.url),
                    "after_url": str(page.url),
                    "status": "blocked",
                    "error": "mfa_or_human_verification_requires_explicit_handoff",
                }
            )
            break
    return trace


def bootstrap_access_profile(
    browser: Any,
    profile: dict[str, Any],
    *,
    headful: bool,
    timeout_ms: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Acquire an in-memory Playwright state and return only a sanitised summary."""
    method = str(profile["access_method"])
    summary: dict[str, Any] = {
        "profile_id": str(profile["profile_id"]),
        "role": str(profile["role"]),
        "access_method": method,
        "entry_urls": [str(value) for value in profile["entry_urls"]],
        "allowed_hosts": list(normalized_allowed_hosts(profile)),
        "status": "blocked",
        "attempt_count": 1,
        "session_disposition": str(profile["session_disposition"]),
        "final_disposition": "no_state_acquired",
    }
    context = None
    try:
        if method == "storage_state":
            environment_name = str(profile["storage_state_env"])
            state_path_value = os.environ.get(environment_name)
            if not state_path_value:
                raise ValueError(f"Storage-state path environment variable is unavailable: {environment_name}")
            state_path = Path(state_path_value).expanduser()
            if not state_path.is_file():
                raise ValueError("The supplied storage-state file does not exist.")
            context = browser.new_context(storage_state=str(state_path))
            summary["storage_state_source"] = "environment_path"
            summary["storage_state_env"] = environment_name
        else:
            context = browser.new_context()
        page = context.new_page()
        login_url = str(profile.get("login_url") or profile["entry_urls"][0])
        if not url_is_allowed(login_url, profile):
            raise ValueError("Access entry URL is outside allowed_hosts.")
        page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(350)
        if not url_is_allowed(str(page.url), profile):
            raise ValueError("Access entry redirected outside allowed_hosts.")
        trace: list[dict[str, Any]] = []
        if method in {"login_recipe", "public_registration"}:
            trace = _run_login_recipe(page, profile, timeout_ms)
            if trace and trace[-1].get("status") == "blocked":
                raise ValueError(str(trace[-1].get("error", "login_recipe_blocked")))
        elif method == "headful_handoff":
            if not headful:
                raise ValueError("Headful handoff requires --headful.")
            if not sys.stdin.isatty():
                raise ValueError("Headful handoff requires an interactive terminal for explicit continue.")
            input(
                f"Complete login/MFA for access profile '{profile['profile_id']}' in the browser, "
                "then press Enter to continue: "
            )
            trace = [
                {
                    "index": 0,
                    "action": "headful_handoff",
                    "before_url": login_url,
                    "after_url": str(page.url),
                    "status": "completed",
                }
            ]
        entry_url = str(profile["entry_urls"][0])
        if str(page.url) != entry_url:
            page.goto(entry_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(350)
        if not url_is_allowed(str(page.url), profile):
            raise ValueError("Authenticated entry redirected outside allowed_hosts.")
        predicate = success_predicate_result(page, profile["success_predicate"])
        if not predicate["passed"]:
            raise ValueError("The explicit post-login success predicate did not pass.")
        state = context.storage_state()
        summary.update(
            {
                "status": "authenticated",
                "success_predicate": predicate,
                "login_trace": trace,
                "final_disposition": "in_memory_state_discard_after_run",
            }
        )
        return state, summary
    except Exception as error:
        summary["blocker"] = f"{type(error).__name__}: {error}"
        return None, summary
    finally:
        if context is not None:
            context.close()


def session_is_valid(page: Any, profile: dict[str, Any], timeout_ms: int) -> dict[str, Any]:
    entry_url = str(profile["entry_urls"][0])
    try:
        page.goto(entry_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(250)
        if not url_is_allowed(str(page.url), profile):
            raise ValueError("Session validation redirected outside allowed_hosts.")
        return success_predicate_result(page, profile["success_predicate"])
    except Exception as error:
        return {
            "passed": False,
            "checks": [],
            "error": f"{type(error).__name__}: {error}",
        }
