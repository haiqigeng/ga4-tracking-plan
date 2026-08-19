from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlparse

FORM_EVIDENCE_STATES = (
    "inventory_observed",
    "progression_observed",
    "failure_observed",
    "submission_observed",
    "success_confirmed",
)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def rendered_state_evidence(page: Any) -> dict[str, Any]:
    """Return a bounded, non-PII fingerprint of the current material page state."""
    try:
        state = page.evaluate(
            r"""() => {
                const visible = element => !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length));
                const text = value => String(value || "").replace(/\s+/g, " ").trim();
                const selectorFor = element => {
                    if (!element) return "";
                    if (element.id) return `#${String(element.id).replace(/[^a-zA-Z0-9_-]/g, "")}`;
                    const role = element.getAttribute("role");
                    const name = element.getAttribute("name");
                    return `${element.tagName.toLowerCase()}${role ? `[role="${role}"]` : ""}${name ? `[name="${name}"]` : ""}`;
                };
                const main = document.querySelector("main, [role='main'], article") || document.body;
                return {
                    url: document.location.href,
                    title: text(document.title).slice(0, 240),
                    headings: [...document.querySelectorAll("h1, h2, [role='heading']")]
                        .filter(visible).map(element => text(element.textContent)).filter(Boolean).slice(0, 20),
                    visible_forms: [...document.querySelectorAll("form")].filter(visible).slice(0, 20).map(form => ({
                        selector: selectorFor(form),
                        method: String(form.method || "get").toLowerCase(),
                        action_path: (() => { try { return new URL(form.action || document.location.href, document.baseURI).pathname; } catch (_) { return ""; } })(),
                        field_types: [...form.querySelectorAll("input, select, textarea")].slice(0, 30).map(field => String(field.type || field.tagName).toLowerCase()),
                        control_types: [...form.querySelectorAll("button, input[type='submit'], [role='button']")].slice(0, 20).map(control => String(control.type || control.getAttribute("role") || control.tagName).toLowerCase())
                    })),
                    visible_dialogs: [...document.querySelectorAll("dialog, [role='dialog'], [aria-modal='true']")]
                        .filter(visible).map(selectorFor).slice(0, 20),
                    active_controls: [...document.querySelectorAll("[aria-selected='true'], [aria-expanded='true'], [aria-pressed='true']")]
                        .filter(visible).map(selectorFor).slice(0, 30),
                    main_text_length: text(main && main.innerText).length,
                    action_count: [...document.querySelectorAll("a[href], button, [role='button']")].filter(visible).length
                };
            }"""
        )
    except Exception:
        state = {"url": str(getattr(page, "url", ""))}
    if not isinstance(state, dict):
        state = {"url": str(getattr(page, "url", ""))}
    return {
        "url": str(state.get("url", getattr(page, "url", ""))),
        "state_sha256": _fingerprint(state),
        "rendered_state": {
            "title_sha256": _fingerprint(str(state.get("title", ""))),
            "heading_sha256": [
                _fingerprint(str(value)) for value in state.get("headings", [])
            ],
            "visible_forms": [
                value for value in state.get("visible_forms", []) if isinstance(value, dict)
            ],
            "visible_dialogs": [str(value) for value in state.get("visible_dialogs", [])],
            "active_controls": [str(value) for value in state.get("active_controls", [])],
            "main_text_length": int(state.get("main_text_length", 0) or 0),
            "action_count": int(state.get("action_count", 0) or 0),
        },
    }


def explicit_failure_evidence(page: Any) -> dict[str, Any] | None:
    """Observe an explicit validation/error component without matching generic body words."""
    selectors = (
        "[role='alert']",
        "[aria-invalid='true']",
        "[data-error]",
        ".error-message",
        ".form-error",
        ".erreur",
    )
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 10)):
                candidate = locator.nth(index)
                if candidate.is_visible(timeout=150):
                    return {
                        "oracle_type": "explicit_failure_selector",
                        "selector": selector,
                        "locator_index": index,
                    }
        except Exception:
            continue
    return None


def _configured_success_oracle(page: Any, predicate: dict[str, Any]) -> dict[str, Any] | None:
    selector = str(predicate.get("selector_visible", "")).strip()
    if selector:
        try:
            if page.locator(selector).first.is_visible(timeout=1200):
                return {"oracle_type": "configured_selector", "selector": selector}
        except Exception:
            pass
    url_contains = str(predicate.get("url_contains", "")).strip()
    if url_contains and url_contains in str(getattr(page, "url", "")):
        return {"oracle_type": "configured_route", "url_contains": url_contains}
    return None


def _explicit_success_component(page: Any) -> dict[str, Any] | None:
    """Require an explicit success component, never a generic word in body text."""
    selectors = (
        "[data-success]",
        "[data-confirmation]",
        "[data-status='success']",
        "[role='status'][data-state='success']",
        ".form-success",
        ".confirmation-message",
        "#success",
        "#confirmation",
    )
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 10)):
                if locator.nth(index).is_visible(timeout=150):
                    return {
                        "oracle_type": "explicit_success_selector",
                        "selector": selector,
                        "locator_index": index,
                    }
        except Exception:
            continue
    return None


def _expected_form_action_route(
    before_url: str,
    after_url: str,
    form_action: str,
) -> dict[str, Any] | None:
    before = urlparse(before_url)
    after = urlparse(after_url)
    action = urlparse(form_action)
    if not after_url or after_url == before_url:
        return None
    same_action_host = not action.hostname or action.hostname == after.hostname
    action_path_matches = bool(action.path and action.path != "/" and action.path.rstrip("/") == after.path.rstrip("/"))
    material_route_change = (before.path, before.fragment) != (after.path, after.fragment)
    if same_action_host and action_path_matches and material_route_change:
        return {
            "oracle_type": "expected_form_action_route",
            "expected_path": action.path,
            "observed_path": after.path,
        }
    return None


def _backend_success_oracle(
    responses: list[dict[str, Any]],
    form_action: str,
) -> dict[str, Any] | None:
    expected = urlparse(form_action)
    for response in responses:
        status = int(response.get("status", 0) or 0)
        path = str(response.get("path", ""))
        method = str(response.get("method", "")).upper()
        if status in {201, 202, 204} and method in {"POST", "PUT", "PATCH"} and expected.path and path == expected.path:
            return {
                "oracle_type": "allowlisted_backend_response",
                "method": method,
                "path": path,
                "status": status,
            }
    return None


def positive_success_oracle(
    page: Any,
    *,
    before_url: str,
    form_action: str,
    configured_predicate: dict[str, Any] | None = None,
    responses: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Return a recorded positive outcome oracle, or None when success is unproven."""
    predicate_oracle = _configured_success_oracle(page, configured_predicate or {})
    if predicate_oracle:
        return predicate_oracle
    component_oracle = _explicit_success_component(page)
    if component_oracle:
        return component_oracle
    route_oracle = _expected_form_action_route(
        before_url,
        str(getattr(page, "url", "")),
        form_action,
    )
    if route_oracle:
        return route_oracle
    return _backend_success_oracle(responses or [], form_action)


def evidence_claim(
    claim: str,
    *,
    evidence_type: str,
    locator: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "claim": claim,
        "evidence_type": evidence_type,
        "locator": locator,
        "evidence": evidence,
    }


def highest_form_evidence_state(claims: list[dict[str, Any]]) -> str:
    observed = {str(item.get("claim", "")) for item in claims if isinstance(item, dict)}
    if "success_confirmed" in observed:
        return "success_confirmed"
    if "submission_observed" in observed:
        return "submission_observed"
    if "failure_observed" in observed:
        return "failure_observed"
    if "progression_observed" in observed:
        return "progression_observed"
    return "inventory_observed"


def validate_interaction_run_evidence(run: dict[str, Any]) -> list[str]:
    """Validate direct evidence for each asserted form claim."""
    errors: list[str] = []
    claims = [item for item in run.get("evidence_claims", []) if isinstance(item, dict)]
    claimed = {str(item.get("claim", "")) for item in claims}
    for index, claim in enumerate(claims):
        if not str(claim.get("locator", "")).strip() or not isinstance(claim.get("evidence"), dict) or not claim["evidence"]:
            errors.append(
                f"OBSERVED_WITHOUT_DIRECT_EVIDENCE evidence_claims/{index}: "
                f"'{claim.get('claim', '')}' needs a concrete locator and evidence record"
            )
    state = str(run.get("evidence_state", ""))
    if state and state not in claimed:
        errors.append(
            f"OBSERVED_WITHOUT_DIRECT_EVIDENCE evidence_state '{state}' has no matching claim"
        )
    if run.get("outcome") == "completed":
        success_claims = [item for item in claims if item.get("claim") == "success_confirmed"]
        if not success_claims:
            errors.append(
                "OBSERVED_WITHOUT_DIRECT_EVIDENCE completed interaction has no success_confirmed claim"
            )
        for claim in success_claims:
            oracle_type = str((claim.get("evidence") or {}).get("oracle_type", ""))
            if oracle_type not in {
                "configured_selector",
                "configured_route",
                "explicit_success_selector",
                "expected_form_action_route",
                "allowlisted_backend_response",
            }:
                errors.append(
                    "OBSERVED_WITHOUT_DIRECT_EVIDENCE success_confirmed lacks an approved positive oracle"
                )
    return errors
