from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urljoin

from journey_evidence import evidence_claim, explicit_failure_evidence, rendered_state_evidence


@dataclass(frozen=True)
class ProbeDefinition:
    family: str
    execution: str
    safe_action: str
    reset_state: bool = True


PROBE_REGISTRY: dict[str, ProbeDefinition] = {
    "tabbed_form": ProbeDefinition("tabbed_form", "execute", "click"),
    "faq_accordion": ProbeDefinition("faq_accordion", "execute", "click"),
    "modal_dialog": ProbeDefinition("modal_dialog", "execute", "click"),
    "coupon_application": ProbeDefinition("coupon_application", "execute", "coupon_failure"),
    "filter_sort": ProbeDefinition("filter_sort", "execute", "choice"),
    "configurator_progression": ProbeDefinition("configurator_progression", "execute", "choice"),
    "locator_selection": ProbeDefinition("locator_selection", "execute", "click"),
    "download": ProbeDefinition("download", "detect_only", "inspect_href"),
    "meaningful_error": ProbeDefinition("meaningful_error", "detect_only", "inspect_state"),
    "iframe_form": ProbeDefinition("iframe_form", "execute", "frame_progression"),
    "video_media": ProbeDefinition("video_media", "execute", "play_pause"),
    "deliberate_contact_handoff": ProbeDefinition("deliberate_contact_handoff", "detect_only", "inspect_href"),
    "navigation_surface": ProbeDefinition("navigation_surface", "execute", "click"),
    "search_result_selection": ProbeDefinition("search_result_selection", "execute", "click"),
    "pagination_load_more": ProbeDefinition("pagination_load_more", "execute", "click"),
    "custom_aria_control": ProbeDefinition("custom_aria_control", "execute", "choice"),
    "print_share": ProbeDefinition("print_share", "detect_only", "inspect_control"),
    "carousel_selection": ProbeDefinition("carousel_selection", "detect_only", "inspect_control"),
}


def _identifier(value: str, maximum: int = 119) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "probe"
    if not normalized[0].isalpha():
        normalized = "probe_" + normalized
    return normalized[:maximum].rstrip("_")


def _candidate_controls(page: dict[str, Any]) -> list[dict[str, Any]]:
    controls = [
        item
        for collection in ("button_controls", "interactive_controls", "navigation_controls", "link_controls", "media_controls")
        for item in page.get(collection, [])
        if isinstance(item, dict) and item.get("selector")
    ]
    controls.extend(
        {**item, "surface": "form", "form_id": str(form.get("id") or form.get("name") or "")}
        for form in page.get("forms", [])
        if isinstance(form, dict)
        for collection in ("fields", "submit_controls")
        for item in form.get(collection, [])
        if isinstance(item, dict) and item.get("selector")
    )
    return controls


def _first_matching_control(page: dict[str, Any], family: str) -> dict[str, Any] | None:
    controls = _candidate_controls(page)
    patterns = {
        "tabbed_form": r"(?:tab|onglet)",
        "faq_accordion": r"(?:faq|question|accordion)",
        "modal_dialog": r"(?:dialog|modal)",
        "coupon_application": r"(?:coupon|promo|voucher|reduction)",
        "filter_sort": r"(?:filter|filtre|sort|tri|trier)",
        "configurator_progression": r"(?:configur|option|variant|choice|choix)",
        "locator_selection": r"(?:store|station|map|carte|result|magasin|agence)",
        "video_media": r"(?:video|play|lecture)",
        "navigation_surface": r"(?:header|footer|menu|navigation)",
        "search_result_selection": r"(?:result|resultat|search|recherche)",
        "pagination_load_more": r"(?:next|more|load|suivant|plus|pagination)",
        "custom_aria_control": r"(?:combobox|toggle|switch|listbox)",
        "print_share": r"(?:print|share|imprimer|partager)",
        "carousel_selection": r"(?:carousel|slide|next|previous|suivant|precedent)",
    }
    for control in controls:
        corpus = " ".join(
            str(control.get(key, ""))
            for key in ("type", "role", "label", "name", "surface", "aria_haspopup", "aria_controls")
        )
        if family == "tabbed_form" and str(control.get("type", "")) == "tab" and str(control.get("aria_selected", "")) != "true":
            return control
        if family == "faq_accordion" and str(control.get("aria_expanded", "")) == "false":
            return control
        if family == "modal_dialog" and (
            str(control.get("aria_haspopup", "")) == "dialog" or control.get("aria_controls")
        ):
            return control
        if family == "custom_aria_control" and str(control.get("type", "")) in {"combobox", "listbox", "switch"}:
            return control
        if family == "search_result_selection" and control.get("search_result"):
            return control
        if family == "locator_selection" and control.get("locator_result"):
            return control
        if family == "pagination_load_more" and control.get("pagination"):
            return control
        if family == "download" and control.get("download"):
            return control
        if family == "deliberate_contact_handoff" and control.get("contact_handoff"):
            return control
        if family == "carousel_selection" and control.get("carousel_selection"):
            return control
        pattern = patterns.get(family)
        if pattern and re.search(pattern, corpus, re.I):
            return control
    return None


def build_probe_recipes(pages: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    """Build one bounded probe per detected family and page state, never one per control."""
    recipes: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for page in pages:
        url = str(page.get("url", ""))
        state_id = str(page.get("state_id", "entry"))
        for capability in page.get("interaction_capabilities", []):
            if not isinstance(capability, dict):
                continue
            family = str(capability.get("family", ""))
            definition = PROBE_REGISTRY.get(family)
            if not definition:
                continue
            identity = (url, state_id, family)
            if identity in seen:
                continue
            control = _first_matching_control(page, family)
            execution = definition.execution
            if execution == "execute" and not control and family not in {"iframe_form", "video_media"}:
                execution = "detect_only"
            digest = hashlib.sha256("|".join(identity).encode("utf-8")).hexdigest()[:12]
            recipes.append(
                {
                    "probe_id": _identifier(f"probe_{family}_{digest}"),
                    "capability_id": str(capability.get("capability_id", "")),
                    "family": family,
                    "materiality": str(capability.get("materiality", "candidate")),
                    "start_url": url,
                    "state_id": state_id,
                    "template": str(page.get("template", "content_or_other")),
                    "access_profile_id": str(page.get("access_profile_id", "public")),
                    "role": str(page.get("role", "public")),
                    "execution": execution,
                    "safe_action": definition.safe_action,
                    "reset_state": definition.reset_state,
                    "selector": str((control or {}).get("selector", "")),
                    "control_label": str((control or {}).get("label", "")),
                    "detected_evidence": [str(value) for value in capability.get("evidence", [])],
                    "detected_families_before": sorted(
                        {
                            str(item.get("family", ""))
                            for item in page.get("interaction_capabilities", [])
                            if isinstance(item, dict) and item.get("family")
                        }
                    ),
                    **(
                        {"frame_url": str(page.get("embedded_frames", [{}])[0].get("url", ""))}
                        if family == "iframe_form" and page.get("embedded_frames")
                        else {}
                    ),
                }
            )
            seen.add(identity)
            if limit is not None and len(recipes) >= max(0, limit):
                return recipes
    return recipes


def _safe_rescan(page: Any, allowed_url: Callable[[str], bool]) -> dict[str, Any]:
    try:
        value = page.evaluate(
            r"""() => {
                const visible = element => !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length));
                return {
                    links: [...document.querySelectorAll("a[href]")].filter(visible).slice(0, 100).map(element => new URL(element.href, document.baseURI).href),
                    visible_form_count: [...document.querySelectorAll("form")].filter(visible).length,
                    visible_dialog_count: [...document.querySelectorAll("dialog, [role='dialog'], [aria-modal='true']")].filter(visible).length,
                    visible_action_count: [...document.querySelectorAll("button, [role='button'], a[href]")].filter(visible).length,
                    forms: [...document.querySelectorAll("form")].filter(visible).slice(0, 20).map((form, index) => ({
                        id: form.id || form.getAttribute("name") || `form_${index + 1}`,
                        action_path: (() => { try { return new URL(form.action || document.location.href, document.baseURI).pathname; } catch (_) { return ""; } })(),
                        visible_field_count: [...form.querySelectorAll("input, select, textarea, button")].filter(visible).length
                    })),
                    controls: [...document.querySelectorAll("button, [role='button'], [role='tab'], [role='combobox'], [role='switch'], select")]
                        .filter(visible).slice(0, 50).map((element, index) => ({
                            index,
                            role: element.getAttribute("role") || element.tagName.toLowerCase(),
                            label: (element.innerText || element.getAttribute("aria-label") || element.getAttribute("name") || "").trim().slice(0, 160),
                            expanded: element.getAttribute("aria-expanded"),
                            selected: element.getAttribute("aria-selected")
                        })),
                    finite_values: [...document.querySelectorAll("select")].filter(visible).slice(0, 20).map((element, index) => ({
                        control: element.getAttribute("name") || element.id || `select_${index + 1}`,
                        values: [...element.options].filter(option => !option.disabled).slice(0, 50).map(option => ({
                            value: String(option.value || "").slice(0, 160),
                            label: String(option.textContent || "").trim().slice(0, 160)
                        }))
                    })),
                    embedded_frame_count: [...document.querySelectorAll("iframe")].filter(visible).length,
                    semantic_counts: {
                        tab: [...document.querySelectorAll("[role='tab']")].filter(visible).length,
                        accordion: [...document.querySelectorAll("details, [aria-expanded][aria-controls]")].filter(visible).length,
                        dialog: [...document.querySelectorAll("dialog, [role='dialog'], [aria-modal='true']")].filter(visible).length,
                        search_result: [...document.querySelectorAll("[data-search-result], [class*='search-result' i], main [role='listitem']")].filter(visible).length,
                        locator_result: [...document.querySelectorAll("[data-store-id], [data-station-id], [class*='store-result' i], [class*='station-result' i], [class*='locator-result' i]")].filter(visible).length,
                        pagination: [...document.querySelectorAll("[rel='next'], [aria-label*='next' i], [aria-label*='suivant' i], [class*='pagination' i], [data-load-more]")].filter(visible).length,
                        video: [...document.querySelectorAll("video, iframe[src*='youtube' i], iframe[src*='vimeo' i]")].filter(visible).length,
                        error: [...document.querySelectorAll("[role='alert'], [aria-invalid='true'], [data-error], .error-message, .form-error")].filter(visible).length
                    }
                };
            }"""
        )
    except Exception:
        value = {}
    links = sorted({str(url).split("#", 1)[0] for url in value.get("links", []) if allowed_url(str(url))})
    result = {
        "url": str(page.url),
        "links": links,
        "visible_form_count": int(value.get("visible_form_count", 0) or 0),
        "visible_dialog_count": int(value.get("visible_dialog_count", 0) or 0),
        "visible_action_count": int(value.get("visible_action_count", 0) or 0),
        "forms": [item for item in value.get("forms", []) if isinstance(item, dict)],
        "controls": [item for item in value.get("controls", []) if isinstance(item, dict)],
        "finite_values": [item for item in value.get("finite_values", []) if isinstance(item, dict)],
        "embedded_frame_count": int(value.get("embedded_frame_count", 0) or 0),
        "semantic_counts": {
            str(name): int(count or 0)
            for name, count in (value.get("semantic_counts", {}) or {}).items()
        },
    }
    family_by_count = {
        "tab": "tabbed_form",
        "accordion": "faq_accordion",
        "dialog": "modal_dialog",
        "search_result": "search_result_selection",
        "locator_result": "locator_selection",
        "pagination": "pagination_load_more",
        "video": "video_media",
        "error": "meaningful_error",
    }
    result["interaction_families"] = sorted(
        family_by_count[name]
        for name, count in result["semantic_counts"].items()
        if count and name in family_by_count
    )
    result["rescan_sha256"] = hashlib.sha256(repr(sorted(result.items())).encode("utf-8")).hexdigest()
    return result


def _frame_progression(
    page: Any,
    recipe: dict[str, Any],
    timeout_ms: int,
    allowed_url: Callable[[str], bool],
) -> dict[str, Any]:
    frame_url = str(recipe.get("frame_url", ""))
    frame = next((candidate for candidate in page.frames if frame_url and candidate.url == frame_url), None)
    if frame is None:
        frame = next((candidate for candidate in page.frames if candidate != page.main_frame), None)
    if frame is None:
        raise ValueError("The detected embedded frame is no longer available.")
    if not allowed_url(str(frame.url)):
        raise ValueError("Embedded form is outside allowed_hosts.")
    form = frame.locator("form").first
    form.wait_for(state="visible", timeout=timeout_ms)
    form_action = str(form.get_attribute("action") or "")
    if form_action and not allowed_url(urljoin(str(frame.url), form_action)):
        raise ValueError("Embedded form action is outside allowed_hosts.")
    before_state = {
        "url": str(frame.url),
        "visible_form": True,
        "visible_success": False,
    }
    fields = form.locator("input, textarea, select")
    filled_kinds: list[str] = []
    for index in range(min(fields.count(), 20)):
        field = fields.nth(index)
        if not field.is_visible(timeout=100):
            continue
        field_type = str(field.get_attribute("type") or field.evaluate("element => element.tagName.toLowerCase()")).casefold()
        try:
            if field_type in {"email"}:
                field.fill("ga4-synthetic-frame@example.com")
                filled_kinds.append("email")
            elif field_type in {"text", "textarea", "tel"}:
                field.fill("Test analytics")
                filled_kinds.append("text")
            elif field_type == "select":
                options = field.locator("option:not([disabled])")
                if options.count():
                    value = options.nth(0).get_attribute("value")
                    if value:
                        field.select_option(value)
                        filled_kinds.append("finite_option")
        except Exception:
            continue
    control = form.locator("button, input[type='submit'], [role='button']").first
    if not control.is_visible(timeout=500):
        return {"filled_kinds": filled_kinds, "clicked": False, "frame_url": frame.url}
    label = str(control.inner_text(timeout=500) or control.get_attribute("value") or "")
    control_type = str(control.get_attribute("type") or control.evaluate("element => element.tagName.toLowerCase()")).casefold()
    if re.search(r"(?:pay|purchase|order|book|contract|payer|commander|rendez-vous|signature)", label, re.I):
        return {"filled_kinds": filled_kinds, "clicked": False, "frame_url": frame.url, "boundary": "consequential_action"}
    control.click(timeout=timeout_ms)
    frame.wait_for_timeout(500)
    if not allowed_url(str(frame.url)):
        raise ValueError("Embedded form redirected outside allowed_hosts.")
    try:
        visible_form = form.is_visible(timeout=200)
    except Exception:
        visible_form = False
    success_selector = "[data-success], [data-confirmation], [data-status='success'], .form-success, .confirmation-message, #success, #confirmation"
    try:
        visible_success = frame.locator(success_selector).first.is_visible(timeout=300)
    except Exception:
        visible_success = False
    after_state = {
        "url": str(frame.url),
        "visible_form": bool(visible_form),
        "visible_success": bool(visible_success),
    }
    return {
        "filled_kinds": filled_kinds,
        "clicked": True,
        "control_type": control_type,
        "frame_url": frame.url,
        "frame_state_before": before_state,
        "frame_state_after": after_state,
        **({"success_selector": success_selector} if visible_success else {}),
    }


def execute_probe(
    page: Any,
    recipe: dict[str, Any],
    *,
    timeout_ms: int,
    allowed_url: Callable[[str], bool],
    consequential_pattern: re.Pattern[str],
) -> dict[str, Any]:
    claims = [
        evidence_claim(
            "inventory_observed",
            evidence_type="rendered_capability",
            locator=str(recipe.get("capability_id") or recipe["probe_id"]),
            evidence={"detected_evidence": recipe.get("detected_evidence", []), "family": recipe["family"]},
        )
    ]
    result = {**recipe, "outcome": "observed", "evidence_claims": claims, "actions": []}
    if recipe.get("execution") == "detect_only":
        result["evidence_state"] = "inventory_observed"
        result["rescan"] = {}
        return result
    if not allowed_url(str(recipe["start_url"])):
        return {**result, "outcome": "blocked", "blocker": "start_url_outside_allowed_hosts", "evidence_state": "inventory_observed"}
    try:
        page.goto(str(recipe["start_url"]), wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(300)
        before = rendered_state_evidence(page)
        action: dict[str, Any] = {
            "action_type": str(recipe["safe_action"]),
            "before_url": str(page.url),
            "before_state_sha256": before["state_sha256"],
            "status": "completed",
        }
        if recipe["safe_action"] == "frame_progression":
            action.update(_frame_progression(page, recipe, timeout_ms, allowed_url))
        elif recipe["safe_action"] == "play_pause":
            selector = str(recipe.get("selector") or "video")
            media = page.locator(selector).first
            media.wait_for(state="visible", timeout=timeout_ms)
            action["media_evidence"] = media.evaluate(
                """async element => {
                    if (element.tagName.toLowerCase() !== 'video') return { supported: false };
                    const before = Number(element.currentTime || 0);
                    element.muted = true;
                    let playResolved = false;
                    try {
                        await Promise.race([
                            element.play().then(() => { playResolved = true; }),
                            new Promise(resolve => setTimeout(resolve, 500))
                        ]);
                    } catch (_) {}
                    await new Promise(resolve => setTimeout(resolve, 250));
                    const after = Number(element.currentTime || 0);
                    element.pause();
                    return { supported: true, before, after, play_resolved: playResolved };
                }"""
            )
        elif recipe["safe_action"] == "choice":
            control = page.locator(str(recipe["selector"])).first
            control.wait_for(state="visible", timeout=timeout_ms)
            tag = str(control.evaluate("element => element.tagName.toLowerCase()"))
            if tag == "select":
                values = control.locator("option:not([disabled])")
                selected = next(
                    (str(values.nth(index).get_attribute("value") or "") for index in range(values.count()) if values.nth(index).get_attribute("value")),
                    "",
                )
                if not selected:
                    raise ValueError("No safe non-empty choice was available.")
                control.select_option(selected)
            else:
                control.click(timeout=timeout_ms)
        elif recipe["safe_action"] == "coupon_failure":
            control = page.locator(str(recipe["selector"])).first
            control.wait_for(state="visible", timeout=timeout_ms)
            tag = str(control.evaluate("element => element.tagName.toLowerCase()"))
            if tag in {"input", "textarea"}:
                control.fill("synthetic_invalid_coupon")
                form = control.locator("xpath=ancestor::form[1]")
                form_action = str(form.get_attribute("action") or "")
                if form_action and not allowed_url(urljoin(str(page.url), form_action)):
                    raise ValueError("Coupon form action is outside allowed_hosts.")
                submit = form.locator("button, input[type='submit'], [role='button']").first
                if submit.is_visible(timeout=500):
                    submit.click(timeout=timeout_ms)
            else:
                control.click(timeout=timeout_ms)
        else:
            control = page.locator(str(recipe["selector"])).first
            control.wait_for(state="visible", timeout=timeout_ms)
            label = str(control.inner_text(timeout=500) or control.get_attribute("aria-label") or "")
            if consequential_pattern.search(label):
                raise ValueError("Probe reached a consequential-action boundary.")
            target = str(control.get_attribute("href") or "")
            if target and not allowed_url(urljoin(str(page.url), target)):
                raise ValueError("Probe navigation target is outside allowed_hosts.")
            control.click(timeout=timeout_ms)
        page.wait_for_timeout(500)
        if not allowed_url(str(page.url)):
            raise ValueError("Probe navigated outside allowed_hosts.")
        after = rendered_state_evidence(page)
        action.update(
            {
                "after_url": str(page.url),
                "after_state_sha256": after["state_sha256"],
            }
        )
        result["actions"].append(action)
        frame_changed = (
            action.get("frame_state_before")
            and action.get("frame_state_before") != action.get("frame_state_after")
        )
        media_progressed = bool(
            action.get("media_evidence", {}).get("supported")
            and (
                action.get("media_evidence", {}).get("play_resolved")
                or float(action.get("media_evidence", {}).get("after", 0)) > float(action.get("media_evidence", {}).get("before", 0))
            )
        )
        if before["state_sha256"] != after["state_sha256"] or frame_changed or media_progressed:
            claims.append(
                evidence_claim(
                    "progression_observed",
                    evidence_type="before_after_state",
                    locator="actions/0",
                    evidence={
                        "before_state_sha256": before["state_sha256"],
                        "after_state_sha256": after["state_sha256"],
                        "before_url": before["url"],
                        "after_url": after["url"],
                        **(
                            {
                                "frame_state_before": action.get("frame_state_before"),
                                "frame_state_after": action.get("frame_state_after"),
                            }
                            if frame_changed
                            else {}
                        ),
                        **({"media_evidence": action.get("media_evidence")} if media_progressed else {}),
                    },
                )
            )
            result["evidence_state"] = "progression_observed"
            result["state_id_after"] = _identifier(f"state_{recipe['family']}_{recipe['probe_id']}")
        else:
            result["outcome"] = "partial"
            result["evidence_state"] = "inventory_observed"
            result["blocker"] = "action_completed_without_material_state_change"
        failure = explicit_failure_evidence(page)
        if failure:
            claims.append(
                evidence_claim(
                    "failure_observed",
                    evidence_type="explicit_failure_component",
                    locator=str(failure["selector"]),
                    evidence=failure,
                )
            )
            result["evidence_state"] = "failure_observed"
        if action.get("control_type") in {"submit", "image"}:
            claims.append(
                evidence_claim(
                    "submission_observed",
                    evidence_type="action_window",
                    locator="actions/0",
                    evidence={"control_type": action.get("control_type"), "before_url": action["before_url"], "after_url": action["after_url"]},
                )
            )
            result["evidence_state"] = "submission_observed"
        if action.get("success_selector"):
            claims.append(
                evidence_claim(
                    "success_confirmed",
                    evidence_type="positive_outcome_oracle",
                    locator="actions/0",
                    evidence={"oracle_type": "explicit_success_selector", "selector": action["success_selector"]},
                )
            )
            result["outcome"] = "completed"
            result["evidence_state"] = "success_confirmed"
        result["rescan"] = _safe_rescan(page, allowed_url)
        return result
    except Exception as error:
        return {
            **result,
            "outcome": "blocked",
            "evidence_state": "inventory_observed",
            "blocker": f"{type(error).__name__}: {error}",
        }


def capability_families() -> tuple[str, ...]:
    return tuple(sorted(PROBE_REGISTRY))
