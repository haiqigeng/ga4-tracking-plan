from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from browser_capture import data_layer_capture_init_script, measurement_evidence_script
from browser_environment import inspect_browser_environment, load_playwright_sync_api, resolve_browser_channel
from discover_site_journeys import (
    USER_AGENT,
    SourceError,
    canonical_url,
    classify_page_archetype,
    clean_text,
    discover_robots,
    infer_journey,
    infer_template,
    parse_sitemap,
    same_host,
    signal_contains_phrase,
    summarize_journeys,
)
from discovery_contract import validate_discovery_report
from discovery_quality import aggregate_coverage_statuses, relevant_forms

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a rendered-DOM URL and journey discovery JSON for dynamic websites with Playwright.")
    parser.add_argument("url", help="Website root URL, for example https://www.example.com/")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    parser.add_argument(
        "--run-id",
        help="Optional shared fresh-task ID in run_<32 lowercase hex> format for separately captured reports.",
    )
    parser.add_argument("--limit", type=int, default=75, help="Maximum rendered pages to inspect.")
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum automatic targeted discovery rounds; --limit applies per round.",
    )
    parser.add_argument(
        "--sitemap-limit",
        type=int,
        default=10000,
        help="Maximum sitemap URLs used to build the candidate universe.",
    )
    parser.add_argument(
        "--seed-url",
        action="append",
        default=[],
        help="Additional known journey entry point. May be repeated.",
    )
    parser.add_argument("--timeout-ms", type=int, default=20000, help="Navigation timeout in milliseconds.")
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=250,
        help="Politeness delay between rendered page requests in milliseconds.",
    )
    parser.add_argument("--headful", action="store_true", help="Run the selected browser with a visible window.")
    parser.add_argument(
        "--browser",
        choices=["auto", "chromium", "chrome", "msedge", "firefox", "webkit"],
        default="auto",
        help="Browser channel. Auto prefers the eligible system default browser.",
    )
    parser.add_argument(
        "--interaction-limit",
        type=int,
        default=12,
        help="Maximum representative safe form journeys to execute automatically.",
    )
    parser.add_argument(
        "--no-auto-interact",
        action="store_true",
        help="Disable safe synthetic form progression and record the resulting coverage boundary.",
    )
    return parser.parse_args()


JOURNEY_TOKENS = {
    "checkout": 950,
    "commande": 950,
    "payment": 950,
    "paiement": 950,
    "cart": 900,
    "panier": 900,
    "basket": 900,
    "devis": 900,
    "quote": 900,
    "estimate": 900,
    "projet": 850,
    "appointment": 850,
    "rendez-vous": 850,
    "catalogue": 800,
    "catalog": 800,
    "configurateur": 800,
    "configurator": 800,
    "login": 750,
    "connexion": 750,
    "account": 750,
    "compte": 750,
    "product": 650,
    "produit": 650,
    "search": 625,
    "recherche": 625,
    "contact": 600,
    "newsletter": 600,
    "infolettre": 600,
    "wishlist": 650,
    "favori": 650,
    "order history": 850,
    "mes commandes": 850,
    "retour": 850,
    "return": 850,
    "annulation": 850,
    "cancellation": 850,
    "promotion": 700,
    "promo": 700,
    "offre": 700,
    "filter": 600,
    "filtre": 600,
    "sort": 600,
    "trier": 600,
    "store": 575,
    "magasin": 575,
}

UNSAFE_ACTION_PATTERN = re.compile(
    r"(?:pay|payment|payer|paiement|place\s+order|confirm\s+order|commander|"
    r"confirmer\s+la\s+commande|book\s+appointment|confirmer\s+le\s+rendez-vous|"
    r"sign\s+contract|signature|delete\s+account|supprimer\s+le\s+compte)",
    re.I,
)
CAPTCHA_PATTERN = re.compile(r"(?:captcha|recaptcha|hcaptcha|turnstile)", re.I)
SAFE_SUBMISSION_KINDS = {
    "lead_form": "lead",
    "catalogue": "lead",
    "newsletter": "lead",
    "support_or_contact": "lead",
    "account": "authentication",
    "search_results": "search",
}
COLLECT_HOST_PATTERN = re.compile(r"(?:^|\.)(?:google-analytics\.com|analytics\.google\.com)$", re.I)


CAPTURE_INIT_SCRIPT = data_layer_capture_init_script("__ga4DiscoveryCapture")


def candidate_priority(
    candidate: dict[str, str],
    root_url: str,
    observed_templates: set[str] | dict[str, int] | Counter[str] | None = None,
    observed_families: set[str] | None = None,
) -> int:
    url = str(candidate.get("url", ""))
    if canonical_url(url) == canonical_url(root_url):
        return 10_000
    corpus = f"{url} {candidate.get('text', '')}"
    score = max((weight for token, weight in JOURNEY_TOKENS.items() if signal_contains_phrase(corpus, token)), default=250)
    template = infer_template(url, str(candidate.get("text", "")))
    observed_count = 0
    if isinstance(observed_templates, dict):
        observed_count = int(observed_templates.get(template, 0))
    elif observed_templates is not None and template in observed_templates:
        observed_count = 1
    if observed_count == 0 and template != "unknown":
        score += 2_000
    else:
        # Breadth before repetition: after a representative template is seen,
        # near-duplicates lose priority instead of retaining a permanent
        # product/list token advantage.
        score -= min(2_000, 700 * observed_count)
    family = candidate_family(url, str(candidate.get("text", "")))
    if observed_families is not None and family not in observed_families:
        score += 900
    path = urlparse(url).path.strip("/")
    score -= min(150, path.count("/") * 20)
    if urlparse(url).query:
        score -= 50
    if candidate.get("source") == "explicit_seed":
        score += 4_000
    return score


def material_unvisited_candidates(
    candidates: list[dict[str, str]],
    root_url: str,
    observed_templates: set[str] | dict[str, int] | Counter[str],
    observed_families: set[str] | None = None,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    representatives: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        template = infer_template(
            str(candidate.get("url", "")),
            str(candidate.get("text", "")),
        )
        priority = candidate_priority(
            candidate,
            root_url,
            observed_templates,
            observed_families,
        )
        observed_count = int(observed_templates.get(template, 0)) if isinstance(observed_templates, dict) else int(template in observed_templates)
        family = candidate_family(
            str(candidate.get("url", "")),
            str(candidate.get("text", "")),
        )
        if (observed_count and (observed_families is None or family in observed_families)) or priority < 550:
            continue
        enriched = {
            **candidate,
            "template": template,
            "family": family,
            "priority": priority,
        }
        previous = representatives.get(family)
        if previous is None or priority > int(previous["priority"]):
            representatives[family] = enriched
    return sorted(
        representatives.values(),
        key=lambda item: (-int(item["priority"]), str(item["url"])),
    )[:limit]


def discovery_outcome(
    pages: list[dict],
    errors: list[SourceError],
    material_unvisited: list[dict[str, Any]] | None = None,
    universe_truncated: bool = False,
) -> tuple[str, int, str]:
    usable = sum(not page.get("fetch_error") for page in pages)
    root_failed = bool(pages and pages[0].get("fetch_error"))
    if usable == 0:
        return "blocked", usable, "Rendered discovery produced no usable page evidence."
    if errors or root_failed or material_unvisited or universe_truncated:
        return "partial", usable, ("Rendered discovery is partial; inspect source_errors and coverage_gaps before claiming website coverage.")
    return "completed", usable, "Rendered discovery covered the material public candidates in the sampled universe."


def discovery_exit_code(outcome: str) -> int:
    """Keep usable partial evidence in the pipeline; only blocked discovery stops it."""
    return 1 if outcome == "blocked" else 0


def discovery_round_stop_reason(
    material_unvisited_count: int,
    round_number: int,
    max_rounds: int,
    queue_count: int,
) -> str:
    if material_unvisited_count == 0:
        return "material_coverage_complete"
    if round_number >= max_rounds:
        return "max_rounds_reached"
    if queue_count == 0:
        return "candidate_queue_exhausted"
    return "continue_targeted_discovery"


def _route_variant(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return "/" + "/".join(parts[:2]) if parts else "/"


def _identifier(value: str, *, maximum: int = 79) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"id_{normalized}".rstrip("_")
    return normalized[:maximum]


def family_for_template(template: str, url: str) -> str:
    if template in {
        "lead_form",
        "appointment",
        "catalogue",
        "account",
        "post_purchase",
        "support_or_contact",
        "configurator",
    }:
        return f"{template}:{_route_variant(url)}"
    if template in {"content_or_other", "unknown"}:
        return f"{template}:{_route_variant(url)}"
    return template


def journey_variant_id(template: str, url: str) -> str:
    """Return a stable variant identity at the same grain used for discovery."""
    family = family_for_template(template, url)
    digest = hashlib.sha256(family.encode("utf-8")).hexdigest()[:8]
    prefix = _identifier(f"{infer_journey(template)}_{family}", maximum=70)
    return f"{prefix}_{digest}"


def candidate_family(url: str, text: str = "") -> str:
    return family_for_template(infer_template(url, text), url)


def _capability_context(page: dict[str, Any]) -> dict[str, Any]:
    surfaces = page.get("page_surfaces", {}) if isinstance(page.get("page_surfaces"), dict) else {}
    counts = surfaces.get("semantic_counts", {}) if isinstance(surfaces.get("semantic_counts"), dict) else {}
    forms = relevant_forms(page)
    controls = [item for item in page.get("interactive_controls", []) if isinstance(item, dict)]
    control_parts = [
        " ".join(
            [
                str(item.get("type", "")),
                str(item.get("name", "")),
                str(item.get("id", "")),
                str(item.get("label", "")),
                " ".join(str(value) for value in item.get("option_labels", [])),
            ]
        )
        for item in controls
    ]
    form_parts = [
        " ".join(
            [
                str(form.get("id", "")),
                str(form.get("name", "")),
                *[
                    " ".join(str(field.get(key, "")) for key in ("name", "id", "label"))
                    for field in form.get("fields", [])
                    if isinstance(field, dict)
                ],
            ]
        )
        for form in forms
    ]
    corpus = " ".join(
        [
            str(surfaces.get("title", "")),
            " ".join(str(value) for value in surfaces.get("headings", [])),
            str(surfaces.get("main_text", "")),
            *control_parts,
            *form_parts,
        ]
    )
    return {
        "url": str(page.get("url", "")),
        "template": str(page.get("template", "unknown")),
        "counts": counts,
        "forms": forms,
        "controls": controls,
        "corpus": corpus,
        "tab_count": int(counts.get("tab", 0) or 0) + sum(str(item.get("type", "")) == "tab" for item in controls),
        "tablist_count": int(counts.get("tablist", 0) or 0) + sum(str(item.get("type", "")) == "tablist" for item in controls),
    }


def _semantic_count(context: dict[str, Any], name: str) -> int:
    return int(context["counts"].get(name, 0) or 0)


def _has_local_phrase(context: dict[str, Any], phrases: tuple[str, ...]) -> bool:
    return any(signal_contains_phrase(context["corpus"], phrase) for phrase in phrases)


def _capability(
    context: dict[str, Any],
    family: str,
    category: str,
    materiality: str,
    reason: str,
    evidence: list[str],
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{family}|{context['url']}".encode("utf-8")).hexdigest()[:10]
    return {
        "capability_id": _identifier(f"capability_{family}_{digest}", maximum=119),
        "family": family,
        "category": category,
        "materiality": materiality,
        "reason": reason,
        "evidence": sorted(set(evidence)),
    }


def _tabbed_form_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    if not context["forms"] or (context["tab_count"] < 2 and context["tablist_count"] < 1):
        return None
    return _capability(
        context,
        "tabbed_form",
        "outcome",
        "material",
        "Distinct form tabs can represent different intents or outcomes and require an explicit shared-versus-separate measurement decision.",
        [f"forms:{len(context['forms'])}", f"tabs:{max(context['tab_count'], _semantic_count(context, 'tab'))}"],
    )


def _locator_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    locator_language = _has_local_phrase(context, ("sur la carte", "on the map", "selectionnez une station", "select a store"))
    if context["template"] != "store_locator" or not (_semantic_count(context, "map") or _semantic_count(context, "locator_result") or locator_language):
        return None
    return _capability(
        context,
        "locator_selection",
        "interaction",
        "material",
        "A locator result or map selection is a distinct decision point after the search itself.",
        [f"maps:{_semantic_count(context, 'map')}", f"results:{_semantic_count(context, 'locator_result')}"],
    )


def _faq_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    has_accordion = _semantic_count(context, "details") or _semantic_count(context, "accordion")
    has_faq_context = context["template"] == "support_or_contact" or _has_local_phrase(context, ("faq",))
    if not has_accordion or not has_faq_context:
        return None
    return _capability(
        context,
        "faq_accordion",
        "interaction",
        "candidate",
        "FAQ expansion may reveal unresolved support needs, but should be measured only when the resulting question is useful.",
        [f"details:{_semantic_count(context, 'details')}", f"accordions:{_semantic_count(context, 'accordion')}"],
    )


def _coupon_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    if not _has_local_phrase(context, ("code promo", "promotion code", "coupon", "voucher")):
        return None
    return _capability(
        context,
        "coupon_application",
        "diagnostic",
        "material" if context["template"] in {"cart", "checkout"} else "candidate",
        "Coupon submission success and failure can explain conversion friction and discount use.",
        ["local control or field mentions a coupon/promotion code"],
    )


def _counted_capability(
    context: dict[str, Any],
    count_name: str,
    family: str,
    category: str,
    reason: str,
    evidence_label: str,
) -> dict[str, Any] | None:
    count = _semantic_count(context, count_name)
    if not count:
        return None
    return _capability(context, family, category, "candidate", reason, [f"{evidence_label}:{count}"])


def _error_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    error_language = _has_local_phrase(
        context,
        ("payment failed", "paiement refuse", "erreur de paiement", "une erreur est survenue"),
    )
    if not _semantic_count(context, "error") and not error_language:
        return None
    return _capability(
        context,
        "meaningful_error",
        "diagnostic",
        "material",
        "An observed business-process error can explain funnel loss and requires an explicit diagnostic decision.",
        [f"visible_error_regions:{_semantic_count(context, 'error')}"],
    )


def _filter_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    if not _has_local_phrase(context, ("filter", "filtre", "sort", "trier", "tri")):
        return None
    return _capability(
        context,
        "filter_sort",
        "interaction",
        "candidate",
        "Applied filters or sorting may explain discovery behavior without requiring one event per control.",
        ["local filter or sort control"],
    )


def _configurator_capability(context: dict[str, Any]) -> dict[str, Any] | None:
    if context["template"] != "configurator" or not (context["forms"] or context["controls"]):
        return None
    return _capability(
        context,
        "configurator_progression",
        "progression",
        "material",
        "Meaningful configurator progression and completion require an explicit measurement decision.",
        [f"forms:{len(context['forms'])}", f"controls:{len(context['controls'])}"],
    )


def detect_interaction_capabilities(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one evidence record per family, never one event per control."""
    context = _capability_context(page)
    capabilities = [
        _tabbed_form_capability(context),
        _locator_capability(context),
        _faq_capability(context),
        _coupon_capability(context),
        _counted_capability(
            context,
            "dialog",
            "modal_dialog",
            "interaction",
            "A modal can contain a material gated choice or form; its business purpose must be reviewed before measurement.",
            "dialogs",
        ),
        _counted_capability(
            context,
            "download",
            "download",
            "outcome",
            "A download can be a meaningful outcome such as an application, brochure, or document acquisition.",
            "download_links",
        ),
        _error_capability(context),
        _filter_capability(context),
        _configurator_capability(context),
    ]
    return sorted(
        (item for item in capabilities if item is not None),
        key=lambda item: str(item["family"]),
    )


def _interaction_run_coverage(run: dict[str, Any]) -> tuple[str | None, str | None]:
    if run.get("outcome") == "completed":
        return "observed", "success"
    if run.get("observed_state") == "failure":
        return "partial", "failure"
    if run.get("outcome") == "blocked":
        return "externally_blocked", None
    if run.get("outcome") in {"partial", "stopped_before_consequential_action"}:
        return "partial", None
    return None, None


def journey_coverage_ledger(
    pages: list[dict[str, Any]],
    candidates: list[dict[str, str]],
    material_unvisited: list[dict[str, Any]],
    blocked_candidates: list[dict[str, str]],
    root_url: str,
    interaction_runs: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    def group(journey_id: str) -> dict[str, Any]:
        return groups.setdefault(
            journey_id,
            {
                "journey_id": journey_id,
                "material": journey_id not in {"content_navigation", "unknown"},
                "status": "not_tested",
                "entry_points": set(),
                "states_covered": set(),
                "variants": set(),
                "evidence_urls": set(),
                "unvisited_material_candidates": set(),
                "variant_coverage": {},
            },
        )

    def variant(item: dict[str, Any], template: str, url: str) -> dict[str, Any]:
        variant_id = journey_variant_id(template, url)
        return item["variant_coverage"].setdefault(
            variant_id,
            {
                "variant_id": variant_id,
                "material": infer_journey(template) not in {"content_navigation", "unknown"},
                "status": "not_tested",
                "entry_points": set(),
                "states_covered": set(),
                "evidence_urls": set(),
                "unvisited_material_candidates": set(),
            },
        )

    for candidate in candidates:
        url = str(candidate.get("url", ""))
        journey_id = infer_journey(infer_template(url, str(candidate.get("text", ""))))
        item = group(journey_id)
        template = infer_template(url, str(candidate.get("text", "")))
        variant_item = variant(item, template, url)
        item["entry_points"].add(url)
        item["variants"].add(_route_variant(url))
        variant_item["entry_points"].add(url)
        if candidate_priority(candidate, root_url) >= 550:
            item["material"] = True
            variant_item["material"] = True
    for page in pages:
        url = str(page.get("url", ""))
        template = str(page.get("template", infer_template(url)))
        item = group(infer_journey(template))
        variant_item = variant(item, template, url)
        item["entry_points"].add(url)
        item["variants"].add(_route_variant(url))
        item["evidence_urls"].add(url)
        variant_item["entry_points"].add(url)
        variant_item["evidence_urls"].add(url)
        if not page.get("fetch_error"):
            item["states_covered"].add("entry")
            variant_item["states_covered"].add("entry")
            needs_interaction = template in SAFE_SUBMISSION_KINDS and bool(relevant_forms(page))
            variant_item["status"] = "not_tested" if needs_interaction else "observed"
            if page.get("forms") or page.get("interactive_controls"):
                item["states_covered"].add("progression")
                variant_item["states_covered"].add("progression")
        else:
            variant_item["status"] = "externally_blocked"
    for run in interaction_runs or []:
        if not isinstance(run, dict):
            continue
        journey_id = str(run.get("journey_id", "content_navigation"))
        item = group(journey_id)
        start_url = str(run.get("start_url", ""))
        template = str(run.get("template", infer_template(start_url)))
        variant_id = str(run.get("variant_id", "")) or journey_variant_id(template, start_url)
        variant_item = item["variant_coverage"].setdefault(
            variant_id,
            {
                "variant_id": variant_id,
                "material": journey_id not in {"content_navigation", "unknown"},
                "status": "not_tested",
                "entry_points": {start_url} if start_url else set(),
                "states_covered": set(),
                "evidence_urls": set(),
                "unvisited_material_candidates": set(),
            },
        )
        item["evidence_urls"].add(str(run.get("start_url", "")))
        variant_item["evidence_urls"].add(start_url)
        if run.get("actions"):
            item["states_covered"].add("progression")
            variant_item["states_covered"].add("progression")
        run_status, state = _interaction_run_coverage(run)
        if state:
            item["states_covered"].add(state)
            variant_item["states_covered"].add(state)
        if run_status:
            current_status = str(variant_item.get("status", "not_tested"))
            variant_item["status"] = (
                run_status
                if current_status == "not_tested"
                else aggregate_coverage_statuses([current_status, run_status])
            )
    for candidate in material_unvisited:
        url = str(candidate.get("url", ""))
        template = str(candidate.get("template", infer_template(url)))
        item = group(infer_journey(template))
        variant_item = variant(item, template, url)
        item["unvisited_material_candidates"].add(url)
        variant_item["unvisited_material_candidates"].add(url)
        variant_item["status"] = "not_tested"
    for candidate in blocked_candidates:
        url = str(candidate.get("url", ""))
        template = str(
            candidate.get(
                "template",
                infer_template(url, str(candidate.get("text", ""))),
            )
        )
        item = group(infer_journey(template))
        variant_item = variant(item, template, url)
        item["entry_points"].add(url)
        item["variants"].add(_route_variant(url))
        item["unvisited_material_candidates"].add(url)
        variant_item["entry_points"].add(url)
        variant_item["unvisited_material_candidates"].add(url)
        if variant_item["status"] == "observed":
            variant_item["status"] = "partial"
        elif variant_item["status"] == "not_tested":
            variant_item["status"] = "externally_blocked"
    result: list[dict[str, Any]] = []
    for item in groups.values():
        variant_rows = []
        for variant_item in item.pop("variant_coverage").values():
            variant_rows.append(
                {
                    **variant_item,
                    "entry_points": sorted(variant_item["entry_points"])[:25],
                    "states_covered": sorted(variant_item["states_covered"]),
                    "evidence_urls": sorted(value for value in variant_item["evidence_urls"] if value)[:25],
                    "unvisited_material_candidates": sorted(variant_item["unvisited_material_candidates"])[:25],
                }
            )
        variant_rows.sort(key=lambda record: str(record["variant_id"]))
        material_variants = [record for record in variant_rows if record["material"]]
        assessed_variants = material_variants or variant_rows
        item["status"] = aggregate_coverage_statuses(
            [str(record["status"]) for record in assessed_variants]
        )
        item["states_covered"] = {
            state
            for record in variant_rows
            for state in record["states_covered"]
        }
        result.append(
            {
                **item,
                "entry_points": sorted(item["entry_points"])[:25],
                "states_covered": sorted(item["states_covered"]),
                "variants": sorted(item["variants"])[:25],
                "evidence_urls": sorted(value for value in item["evidence_urls"] if value)[:25],
                "unvisited_material_candidates": sorted(item["unvisited_material_candidates"])[:25],
                "variant_coverage": variant_rows,
            }
        )
    return sorted(result, key=lambda item: str(item["journey_id"]))


def require_playwright():
    try:
        return load_playwright_sync_api()
    except Exception as error:
        raise SystemExit(
            f"Playwright is required and must be importable for rendered-DOM discovery ({type(error).__name__}: {error}). "
            f'Repair the skill runtime with `python -m pip install --upgrade --force-reinstall -r "{REQUIREMENTS}"`. Then run '
            "`python scripts/inspect_browser_environment.py` to reuse an eligible installed browser or identify the browser build still needed."
        ) from error


def launch_browser(playwright: Any, channel: str, headless: bool):
    if channel in {"chrome", "msedge"}:
        return playwright.chromium.launch(channel=channel, headless=headless)
    if channel == "firefox":
        return playwright.firefox.launch(headless=headless)
    if channel == "webkit":
        return playwright.webkit.launch(headless=headless)
    return playwright.chromium.launch(headless=headless)


def accept_privacy_statement(page: Any) -> str | None:
    """Accept a visible CMP choice so rendered discovery can inspect the actual site."""
    selectors = [
        "#onetrust-accept-btn-handler",
        "button[id*='accept'][id*='cookie' i]",
        "button[class*='accept'][class*='cookie' i]",
        "button[data-testid*='accept' i]",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.is_visible(timeout=350):
                label = clean_text(locator.inner_text(timeout=350)) or selector
                locator.click(timeout=1200)
                page.wait_for_timeout(250)
                return label
        except Exception:
            continue
    patterns = [
        r"^(tout accepter|accepter tout|j'accepte|accepter|allow all|accept all|i agree|agree)$",
    ]
    for pattern in patterns:
        try:
            locator = page.get_by_role("button", name=re.compile(pattern, re.I)).first
            if locator.is_visible(timeout=350):
                label = clean_text(locator.inner_text(timeout=350))
                locator.click(timeout=1200)
                page.wait_for_timeout(250)
                return label
        except Exception:
            continue
    return None


def reveal_lazy_content(page: Any) -> None:
    try:
        page.evaluate(
            """async () => {
                const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
                const step = Math.max(500, Math.floor(window.innerHeight * 0.8));
                for (let y = 0; y < height; y += step) {
                    window.scrollTo(0, y);
                    await new Promise(resolve => setTimeout(resolve, 60));
                }
                window.scrollTo(0, 0);
            }"""
        )
    except Exception:
        pass


def collect_rendered_page(page: Any, url: str, root_url: str, timeout_ms: int) -> dict[str, Any]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(min(1500, max(250, timeout_ms // 10)))
    except Exception as error:
        return {"url": url, "template": infer_template(url), "fetch_error": str(error), "links": [], "forms": [], "buttons": []}

    privacy_acceptance = accept_privacy_statement(page)
    reveal_lazy_content(page)

    try:
        page_surfaces = page.evaluate(
            r"""() => {
                const text = value => String(value || "").replace(/\s+/g, " ").trim();
                const visible = element => !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length));
                const main = document.querySelector("main, [role='main'], article");
                const mainText = main ? text(main.innerText).slice(0, 5000) : "";
                const countVisible = selector => [...document.querySelectorAll(selector)].filter(visible).length;
                const localControls = main
                    ? [...main.querySelectorAll("form, [role='tab'], button, [data-product-id], [class*='product-card' i], [itemtype*='Product']")]
                        .filter(visible)
                    : [];
                const componentEvidence = localControls.slice(0, 40).map(element => text(
                    element.getAttribute("aria-label") || element.getAttribute("title") ||
                    element.getAttribute("name") || element.id || element.innerText
                )).filter(Boolean);
                const productCardCount = main
                    ? [...main.querySelectorAll("[data-product-id], [class*='product-card' i], [itemtype*='Product']")].filter(visible).length
                    : 0;
                if (productCardCount > 1) componentEvidence.push("product listing category");
                return {
                    title: text(document.title).slice(0, 300),
                    headings: [...document.querySelectorAll("main h1, main h2, [role='main'] h1, [role='main'] h2, article h1, article h2, body > h1")]
                        .filter(visible).map(element => text(element.innerText)).filter(Boolean).slice(0, 30),
                    main_text: mainText,
                    component_evidence: componentEvidence,
                    semantic_counts: {
                        form: countVisible("form"),
                        tab: countVisible("[role='tab']"),
                        tablist: countVisible("[role='tablist']"),
                        dialog: countVisible("dialog, [role='dialog'], [aria-modal='true']"),
                        details: countVisible("details"),
                        accordion: countVisible("[aria-expanded][aria-controls]"),
                        map: countVisible("[data-map], [id*='map' i], [class*='map' i], iframe[src*='maps' i]"),
                        locator_result: countVisible("[data-store-id], [data-station-id], [class*='store-result' i], [class*='station-result' i], [class*='locator-result' i]"),
                        download: countVisible("a[download], a[href$='.pdf' i], a[href$='.doc' i], a[href$='.docx' i], a[href$='.zip' i], a[href*='download' i]"),
                        video: countVisible("video, iframe[src*='youtube' i], iframe[src*='vimeo' i]"),
                        error: countVisible("[role='alert'], [aria-invalid='true'], .error, .erreur, [class*='error-message' i]")
                    }
                };
            }"""
        )
        if not isinstance(page_surfaces, dict):
            page_surfaces = {}
    except Exception:
        page_surfaces = {}

    links = page.eval_on_selector_all(
        "a[href]",
        """elements => elements.map(element => ({
            url: new URL(element.getAttribute("href"), document.baseURI).href,
            text: (element.innerText || element.getAttribute("aria-label") || element.getAttribute("title") || "").trim()
        }))""",
    )
    forms = page.eval_on_selector_all(
        "form",
        r"""elements => {
            const visible = element => !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length));
            const esc = value => (window.CSS && CSS.escape) ? CSS.escape(value) : value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
            const attr = value => String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
            const selectorFor = element => {
                if (element.id) return `#${esc(element.id)}`;
                const parts = [];
                let node = element;
                while (node && node.nodeType === 1 && node !== document.documentElement) {
                    if (node.id) {
                        parts.unshift(`#${esc(node.id)}`);
                        break;
                    }
                    let part = node.tagName.toLowerCase();
                    const name = node.getAttribute("name");
                    if (name) {
                        part += `[name="${attr(name)}"]`;
                    } else if (node.parentElement) {
                        const siblings = [...node.parentElement.children].filter(child => child.tagName === node.tagName);
                        if (siblings.length > 1) {
                            part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                        }
                    }
                    parts.unshift(part);
                    const candidate = parts.join(" > ");
                    if (document.querySelectorAll(candidate).length === 1) return candidate;
                    node = node.parentElement;
                }
                return parts.join(" > ");
            };
            const labelFor = field => (
                field.getAttribute("aria-label") || field.getAttribute("title") ||
                (field.labels && field.labels[0] && field.labels[0].innerText) ||
                field.getAttribute("placeholder") || field.getAttribute("name") || ""
            ).trim();
            return elements.map(element => ({
                action: new URL(element.getAttribute("action") || document.location.href, document.baseURI).href,
                method: (element.getAttribute("method") || "get").toLowerCase(),
                id: element.id || "",
                name: element.getAttribute("name") || "",
                selector: selectorFor(element),
                visible: visible(element),
                inside_main: !!element.closest("main, [role='main'], article"),
                fields: [...element.querySelectorAll("input, select, textarea")].slice(0, 50).map(field => ({
                    name: field.getAttribute("name") || "",
                    id: field.id || "",
                    selector: selectorFor(field),
                    label: labelFor(field),
                    type: (field.getAttribute("type") || field.tagName).toLowerCase(),
                    value: field.value || field.getAttribute("data-value") || "",
                    required: !!field.required,
                    disabled: !!field.disabled,
                    autocomplete: field.getAttribute("autocomplete") || "",
                    option_values: field.tagName === "SELECT"
                        ? [...field.options].filter(option => !option.disabled && String(option.value || "").trim()).slice(0, 50).map(option => option.value)
                        : (["radio", "checkbox"].includes((field.type || "").toLowerCase())
                            ? [field.value || labelFor(field)].filter(Boolean)
                            : []),
                    option_count: field.tagName === "SELECT"
                        ? [...field.options].filter(option => !option.disabled && String(option.value || "").trim()).length
                        : (["radio", "checkbox"].includes((field.type || "").toLowerCase()) && field.name
                            ? [...element.querySelectorAll("input[type='radio'], input[type='checkbox']")]
                                .filter(candidate => candidate.name === field.name).length
                            : 0),
                    option_labels: field.tagName === "SELECT"
                        ? [...field.options].filter(option => !option.disabled && String(option.value || "").trim()).slice(0, 50).map(option => option.textContent.trim() || option.value)
                        : (["radio", "checkbox"].includes((field.type || "").toLowerCase())
                            ? [labelFor(field) || field.value].filter(Boolean)
                            : [])
                })),
                submit_controls: [...element.querySelectorAll("button, input[type='submit'], [role='button']")].slice(0, 20).map(control => ({
                    selector: selectorFor(control),
                    label: (control.innerText || control.value || control.getAttribute("aria-label") || control.getAttribute("title") || "").trim(),
                    type: (control.getAttribute("type") || control.getAttribute("role") || "button").toLowerCase(),
                    disabled: !!control.disabled
                }))
            }));
        }""",
    )
    buttons = page.eval_on_selector_all(
        "button, [role='button'], input[type='submit'], input[type='button']",
        """elements => elements.map(element =>
            (element.innerText || element.value || element.getAttribute("aria-label") || element.getAttribute("title") || element.id || "").trim()
        ).filter(Boolean)""",
    )
    button_controls = page.eval_on_selector_all(
        "button, [role='button'], input[type='submit'], input[type='button']",
        r"""elements => {
            const esc = value => (window.CSS && CSS.escape) ? CSS.escape(value) : value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
            const attr = value => String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
            const selectorFor = element => {
                if (element.id) return `#${esc(element.id)}`;
                const parts = [];
                let node = element;
                while (node && node.nodeType === 1 && node !== document.documentElement) {
                    if (node.id) {
                        parts.unshift(`#${esc(node.id)}`);
                        break;
                    }
                    let part = node.tagName.toLowerCase();
                    const name = node.getAttribute("name");
                    if (name) {
                        part += `[name="${attr(name)}"]`;
                    } else if (node.parentElement) {
                        const siblings = [...node.parentElement.children].filter(child => child.tagName === node.tagName);
                        if (siblings.length > 1) {
                            part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                        }
                    }
                    parts.unshift(part);
                    const candidate = parts.join(" > ");
                    if (document.querySelectorAll(candidate).length === 1) return candidate;
                    node = node.parentElement;
                }
                return parts.join(" > ");
            };
            return elements.slice(0, 100).map(element => ({
                selector: selectorFor(element),
                label: (element.innerText || element.value || element.getAttribute("aria-label") || element.getAttribute("title") || "").trim(),
                type: (element.getAttribute("type") || element.getAttribute("role") || "button").toLowerCase(),
                form_action: element.form ? (element.form.action || document.location.href) : "",
                disabled: !!element.disabled
            })).filter(item => item.label);
        }""",
    )
    controls = page.eval_on_selector_all(
        "select, input[type='checkbox'], input[type='radio'], [role='combobox'], [role='listbox'], [role='radiogroup'], [role='tablist'], [role='tab'], [role='option'], [role='radio'], [role='checkbox'], [role='menuitemradio'], [data-option-group], [aria-pressed], button[data-value]",
        r"""elements => {
            const visible = element => !!(element && (element.offsetWidth || element.offsetHeight || element.getClientRects().length));
            const esc = value => (window.CSS && CSS.escape) ? CSS.escape(value) : value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
            const attr = value => String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
            const selectorFor = element => {
                if (element.id) return `#${esc(element.id)}`;
                const parts = [];
                let node = element;
                while (node && node.nodeType === 1 && node !== document.documentElement) {
                    if (node.id) {
                        parts.unshift(`#${esc(node.id)}`);
                        break;
                    }
                    let part = node.tagName.toLowerCase();
                    const name = node.getAttribute("name");
                    if (name) {
                        part += `[name="${attr(name)}"]`;
                    } else if (node.parentElement) {
                        const siblings = [...node.parentElement.children].filter(child => child.tagName === node.tagName);
                        if (siblings.length > 1) {
                            part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                        }
                    }
                    parts.unshift(part);
                    const candidate = parts.join(" > ");
                    if (document.querySelectorAll(candidate).length === 1) return candidate;
                    node = node.parentElement;
                }
                return parts.join(" > ");
            };
            const labelFor = element => (element.getAttribute("aria-label") || element.getAttribute("title") ||
                (element.labels && element.labels[0] && element.labels[0].innerText) || element.innerText || "").trim();
            const optionsFor = element => {
                if (element.tagName === "SELECT") return [...element.options];
                const type = (element.getAttribute("type") || "").toLowerCase();
                if (["radio", "checkbox"].includes(type) && element.name) {
                    return [...document.querySelectorAll("input[type='radio'], input[type='checkbox']")]
                        .filter(candidate => candidate.name === element.name);
                }
                if (["combobox", "listbox", "radiogroup", "tablist"].includes((element.getAttribute("role") || "").toLowerCase()) ||
                    element.hasAttribute("data-option-group")) {
                    return [...element.querySelectorAll(
                        "[role='option'], [role='radio'], [role='tab'], [data-value], [data-option-value], [data-variant-value]"
                    )];
                }
                return [element];
            };
            return elements.slice(0, 100).map(element => {
                const allOptions = optionsFor(element);
                const options = allOptions.slice(0, 50);
                return {
                    tag: element.tagName.toLowerCase(),
                    type: (element.getAttribute("type") || element.getAttribute("role") || "").toLowerCase(),
                    name: element.getAttribute("name") || element.getAttribute("data-name") || "",
                    id: element.id || "",
                    selector: selectorFor(element),
                    visible: visible(element),
                    inside_main: !!element.closest("main, [role='main'], article"),
                    label: labelFor(element),
                    value: element.value || element.getAttribute("data-value") || element.getAttribute("aria-label") || "",
                    option_count: allOptions.filter(option => !option.disabled && String(option.value || option.getAttribute("data-value") ||
                        option.getAttribute("aria-label") || option.textContent.trim()).trim()).length,
                    option_values: options.filter(option => !option.disabled).map(option => option.value || option.getAttribute("data-value") ||
                        option.getAttribute("aria-label") || option.textContent.trim()).filter(Boolean),
                    option_labels: options.filter(option => !option.disabled).map(option => labelFor(option) || option.value || option.getAttribute("data-value") || "").filter(Boolean)
                };
            });
        }""",
    )
    try:
        measurement_evidence = page.evaluate(measurement_evidence_script())
    except Exception as error:
        measurement_evidence = {"capture_error": f"{type(error).__name__}: {error}"}
    clean_links = [
        {"url": canonical_url(item["url"]), "text": clean_text(item.get("text", "")), "source": url}
        for item in links
        if isinstance(item, dict) and item.get("url") and same_host(str(item["url"]), root_url)
    ]
    classification = classify_page_archetype(
        url,
        {
            "title": page_surfaces.get("title", ""),
            "headings": page_surfaces.get("headings", []),
            "main": page_surfaces.get("main_text", ""),
            "components": page_surfaces.get("component_evidence", []),
        },
    )
    record = {
        "url": url,
        "template": classification["primary"],
        "classification_diagnostic": classification,
        "page_surfaces": page_surfaces,
        "language": str(page.evaluate("() => document.documentElement.lang || ''") or ""),
        "links": clean_links[:100],
        "forms": forms[:25] if isinstance(forms, list) else [],
        "buttons": [clean_text(str(button)) for button in buttons[:50]] if isinstance(buttons, list) else [],
        "button_controls": button_controls[:100] if isinstance(button_controls, list) else [],
        "interactive_controls": controls[:100] if isinstance(controls, list) else [],
        "privacy_statement_accepted": privacy_acceptance,
        "measurement_evidence": (measurement_evidence if isinstance(measurement_evidence, dict) else {}),
    }
    record["interaction_capabilities"] = detect_interaction_capabilities(record)
    structure = {
        "url": record["url"],
        "template": record["template"],
        "classification_diagnostic": record["classification_diagnostic"],
        "page_surfaces": record["page_surfaces"],
        "links": record["links"],
        "forms": record["forms"],
        "buttons": record["buttons"],
        "button_controls": record["button_controls"],
        "interactive_controls": record["interactive_controls"],
        "interaction_capabilities": record["interaction_capabilities"],
    }
    record["rendered_structure_sha256"] = hashlib.sha256(
        json.dumps(
            structure,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    try:
        record["rendered_dom_sha256"] = hashlib.sha256(page.content().encode("utf-8")).hexdigest()
    except Exception:
        record["rendered_dom_sha256"] = ""
    return record


def summarize_measurement_evidence(
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    gtm_ids: set[str] = set()
    google_tag_ids: set[str] = set()
    measurement_ids: set[str] = set()
    push_count = 0
    pages_with_data_layer = 0
    for page in pages:
        evidence = page.get("measurement_evidence", {})
        if not isinstance(evidence, dict):
            continue
        if evidence.get("data_layer_present"):
            pages_with_data_layer += 1
        push_count += int(evidence.get("data_layer_push_count", 0) or 0)
        gtm_ids.update(str(value) for value in evidence.get("gtm_container_ids", []))
        google_tag_ids.update(str(value) for value in evidence.get("google_tag_ids", []))
        measurement_ids.update(str(value) for value in evidence.get("ga4_measurement_ids", []))
    return {
        "pages_with_data_layer": pages_with_data_layer,
        "observed_data_layer_push_count": push_count,
        "gtm_container_ids": sorted(gtm_ids),
        "google_tag_ids": sorted(google_tag_ids),
        "ga4_measurement_ids": sorted(measurement_ids),
    }


def normalize_language(value: str, root_url: str = "") -> str:
    raw = value.strip().replace("_", "-")
    match = re.fullmatch(r"([A-Za-z]{2})(?:-([A-Za-z]{2}))?", raw)
    if match:
        language = match.group(1).lower()
        region = match.group(2)
        return f"{language}-{region.upper()}" if region else language
    hostname = urlparse(root_url).hostname or ""
    tld = hostname.rsplit(".", 1)[-1].lower()
    if re.fullmatch(r"[a-z]{2}", tld):
        return tld
    return "en"


def summarize_languages(pages: list[dict[str, Any]], root_url: str) -> dict[str, Any]:
    usable = [page for page in pages if not page.get("fetch_error")]
    normalized = [normalize_language(str(page.get("language", "")), root_url) for page in usable]
    counts = Counter(value.split("-", 1)[0] for value in normalized)
    primary = counts.most_common(1)[0][0] if counts else normalize_language("", root_url).split("-", 1)[0]
    evidence_urls = [str(page.get("url")) for page in usable if normalize_language(str(page.get("language", "")), root_url).split("-", 1)[0] == primary][:25]
    return {
        "primary_language": primary,
        "observed_languages": sorted(set(normalized)) or [primary],
        "evidence_urls": evidence_urls or [root_url],
    }


def _synthetic_kind(field: dict[str, Any]) -> str | None:
    field_type = str(field.get("type", "")).casefold()
    corpus = " ".join(str(field.get(key, "")) for key in ("name", "id", "label", "autocomplete")).casefold()
    if field_type in {"hidden", "file", "submit", "button", "reset", "image"}:
        return None
    if field_type == "email" or "email" in corpus or "e-mail" in corpus:
        return "email"
    if field_type == "tel" or re.search(r"phone|mobile|telephone|t[eé]l[eé]phone", corpus):
        return "phone"
    if field_type == "password":
        return "password"
    if re.search(r"first.?name|pr[eé]nom", corpus):
        return "first_name"
    if re.search(r"last.?name|surname|nom(?:\s+de\s+famille)?", corpus):
        return "last_name"
    if re.search(r"postal|postcode|zip|code.?postal", corpus):
        return "postal_code"
    if re.search(r"city|ville", corpus):
        return "city"
    if re.search(r"address|adresse", corpus):
        return "address"
    if field_type in {"number", "range"}:
        return "integer"
    if field_type in {"text", "textarea", "search", "url"}:
        return "text"
    return None


def build_auto_interaction_recipes(
    pages: list[dict[str, Any]],
    *,
    limit: int | None = 12,
) -> list[dict[str, Any]]:
    recipes: list[dict[str, Any]] = []
    seen_forms: set[tuple[str, str]] = set()
    for page in pages:
        if page.get("fetch_error") or not page.get("forms"):
            continue
        template = str(page.get("template", ""))
        submission_kind = SAFE_SUBMISSION_KINDS.get(template)
        if not submission_kind:
            continue
        journey_id = infer_journey(template)
        variant_id = journey_variant_id(template, str(page.get("url", "")))
        for form in relevant_forms(page):
            form_selector = str(form.get("selector", "form"))
            form_key = (variant_id, form_selector)
            if form_key in seen_forms:
                continue
            form_signature = " ".join(
                [
                    str(form.get("action", "")),
                    str(form.get("name", "")),
                    str(form.get("id", "")),
                    *[
                        str(control.get("label", ""))
                        for control in form.get("submit_controls", [])
                        if isinstance(control, dict)
                    ],
                ]
            )
            if UNSAFE_ACTION_PATTERN.search(form_signature):
                continue
            fields = [
                {
                    "selector": str(field.get("selector", "")),
                    "kind": _synthetic_kind(field),
                    "type": field.get("type"),
                    "required": bool(field.get("required")),
                    "option_values": field.get("option_values", []),
                }
                for field in form.get("fields", [])
                if isinstance(field, dict) and not field.get("disabled")
            ]
            form_id = _identifier(
                str(form.get("id") or form.get("name") or form_selector),
                maximum=60,
            )
            recipes.append(
                {
                    "recipe_id": _identifier(f"auto_{variant_id}_{form_id}", maximum=119),
                    "journey_id": journey_id,
                    "variant_id": variant_id,
                    "form_id": form_id,
                    "start_url": str(page.get("url")),
                    "template": template,
                    "submission_kind": submission_kind,
                    "form_selector": form_selector,
                    "initially_visible": bool(form.get("visible", True)),
                    "fields": fields,
                    "maximum_steps": 5,
                }
            )
            seen_forms.add(form_key)
            if limit is not None and len(recipes) >= max(0, limit):
                return recipes
    return recipes


def _synthetic_value(kind: str) -> str:
    return {
        "first_name": "Test",
        "last_name": "Analytics",
        "email": "ga4-synthetic-journey@example.com",
        "phone": "0100000000",
        "postal_code": "75001",
        "city": "Paris",
        "address": "1 rue du Test",
        "password": "Synthetic-Analytics-123!",
        "text": "Test analytics",
        "integer": "1",
    }[kind]


def _safe_measurement_request(request: Any) -> dict[str, Any] | None:
    parsed = urlparse(str(request.url))
    if not COLLECT_HOST_PATTERN.search(parsed.hostname or "") or not parsed.path.endswith("/collect"):
        return None
    query = parse_qs(parsed.query)
    post_data = str(getattr(request, "post_data", "") or "")
    if post_data:
        for key, values in parse_qs(post_data).items():
            query.setdefault(key, []).extend(values)
    return {
        "host": parsed.hostname,
        "path": parsed.path,
        "measurement_id": (query.get("tid") or [None])[0],
        "event_name": (query.get("en") or [None])[0],
        "parameter_names": sorted(key for key in query if key.startswith(("ep.", "epn.", "up.", "upn."))),
    }


def _visible_form_snapshot(page: Any, preferred_selector: str) -> dict[str, Any] | None:
    try:
        forms = page.locator(preferred_selector)
        form = next(
            (forms.nth(index) for index in range(forms.count()) if forms.nth(index).is_visible()),
            None,
        )
        if form is None and preferred_selector.strip() in {"", "form"}:
            all_forms = page.locator("form")
            form = next(
                (all_forms.nth(index) for index in range(all_forms.count()) if all_forms.nth(index).is_visible()),
                None,
            )
        if form is None:
            return None
        return form.evaluate(
            r"""element => {
                const esc = value => (window.CSS && CSS.escape) ? CSS.escape(value) : value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
                const attr = value => String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
                const selectorFor = element => {
                    if (element.id) return `#${esc(element.id)}`;
                    const parts = [];
                    let node = element;
                    while (node && node.nodeType === 1 && node !== document.documentElement) {
                        if (node.id) {
                            parts.unshift(`#${esc(node.id)}`);
                            break;
                        }
                        let part = node.tagName.toLowerCase();
                        const name = node.getAttribute("name");
                        if (name) {
                            part += `[name="${attr(name)}"]`;
                        } else if (node.parentElement) {
                            const siblings = [...node.parentElement.children].filter(child => child.tagName === node.tagName);
                            if (siblings.length > 1) {
                                part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                            }
                        }
                        parts.unshift(part);
                        const candidate = parts.join(" > ");
                        if (document.querySelectorAll(candidate).length === 1) return candidate;
                        node = node.parentElement;
                    }
                    return parts.join(" > ");
                };
                const labelFor = field => (
                    field.getAttribute("aria-label") || field.getAttribute("title") ||
                    (field.labels && field.labels[0] && field.labels[0].innerText) ||
                    field.getAttribute("placeholder") || field.getAttribute("name") || ""
                ).trim();
                return {
                    selector: selectorFor(element),
                    action: element.action || document.location.href,
                    fields: [...element.querySelectorAll("input, select, textarea")].map(field => ({
                        selector: selectorFor(field), name: field.name || "", id: field.id || "",
                        label: labelFor(field), type: (field.type || field.tagName).toLowerCase(),
                        required: !!field.required, disabled: !!field.disabled,
                        autocomplete: field.autocomplete || "",
                        option_values: field.tagName === "SELECT"
                            ? [...field.options].filter(option => !option.disabled).map(option => option.value || option.textContent.trim())
                            : []
                    })),
                    controls: [...element.querySelectorAll("button, input[type='submit'], [role='button']")].map(control => ({
                        selector: selectorFor(control),
                        label: (control.innerText || control.value || control.getAttribute("aria-label") || "").trim(),
                        disabled: !!control.disabled
                    }))
                };
            }"""
        )
    except Exception:
        return None


def execute_auto_interaction(
    page: Any,
    recipe: dict[str, Any],
    *,
    timeout_ms: int,
    active_action: dict[str, int],
    captured_pushes: list[dict[str, Any]],
    captured_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    try:
        page.goto(str(recipe["start_url"]), wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(350)
        accepted = accept_privacy_statement(page)
    except Exception as error:
        return {
            **recipe,
            "outcome": "blocked",
            "actions": [],
            "blocker": f"navigation: {type(error).__name__}: {error}",
        }
    for step in range(int(recipe.get("maximum_steps", 5))):
        page_text = ""
        try:
            page_text = str(page.locator("body").inner_text(timeout=1500))
        except Exception:
            pass
        if CAPTCHA_PATTERN.search(page_text):
            return {
                **recipe,
                "outcome": "blocked",
                "privacy_statement_accepted": accepted,
                "actions": actions,
                "blocker": "captcha_or_human_verification",
            }
        snapshot = _visible_form_snapshot(page, str(recipe.get("form_selector", "form")))
        if snapshot is None:
            outcome = "completed" if actions else "partial"
            return {
                **recipe,
                "outcome": outcome,
                "privacy_statement_accepted": accepted,
                "actions": actions,
            }
        filled: list[dict[str, str]] = []
        for field in snapshot.get("fields", []):
            if not isinstance(field, dict) or field.get("disabled"):
                continue
            field_type = str(field.get("type", "")).casefold()
            selector = str(field.get("selector", ""))
            if not selector:
                continue
            try:
                locator = page.locator(selector).first
                if not locator.is_visible(timeout=250):
                    continue
                if field_type == "select-one" or field_type == "select":
                    values = [str(value) for value in field.get("option_values", []) if str(value).strip()]
                    if values:
                        locator.select_option(values[0])
                        filled.append({"selector": selector, "kind": "finite_option"})
                elif field_type in {"checkbox", "radio"}:
                    if field.get("required") or field_type == "radio":
                        locator.check(timeout=1000)
                        filled.append({"selector": selector, "kind": field_type})
                else:
                    kind = _synthetic_kind(field)
                    if kind:
                        locator.fill(_synthetic_value(kind))
                        filled.append({"selector": selector, "kind": kind})
            except Exception:
                continue
        controls = [item for item in snapshot.get("controls", []) if isinstance(item, dict) and not item.get("disabled") and item.get("selector")]
        preferred = next(
            (
                item
                for item in controls
                if re.search(
                    r"(?:next|continue|submit|send|search|login|sign\s*in|"
                    r"suivant|continuer|valider|envoyer|rechercher|connexion|devis)",
                    str(item.get("label", "")),
                    re.I,
                )
                and not re.search(r"(?:back|previous|cancel|retour|pr[eé]c[eé]dent|annuler)", str(item.get("label", "")), re.I)
            ),
            controls[0] if controls else None,
        )
        if preferred is None:
            return {
                **recipe,
                "outcome": "partial",
                "privacy_statement_accepted": accepted,
                "actions": actions,
                "blocker": "no_safe_progression_control",
            }
        label = str(preferred.get("label", ""))
        if UNSAFE_ACTION_PATTERN.search(f"{label} {snapshot.get('action', '')}"):
            return {
                **recipe,
                "outcome": "stopped_before_consequential_action",
                "privacy_statement_accepted": accepted,
                "actions": actions,
                "stopped_control": label,
            }
        active_action["index"] += 1
        action_index = active_action["index"]
        before_push = len(captured_pushes)
        before_request = len(captured_requests)
        before_url = page.url
        action: dict[str, Any] = {
            "action_index": action_index,
            "step": step + 1,
            "before_url": before_url,
            "control_label": label,
            "filled_fields": filled,
        }
        try:
            page.locator(str(preferred["selector"])).first.click(timeout=timeout_ms)
            page.wait_for_timeout(800)
            action["status"] = "completed"
        except Exception as error:
            action["status"] = "blocked"
            action["error"] = f"{type(error).__name__}: {error}"
        action["after_url"] = page.url
        action["data_layer_pushes"] = captured_pushes[before_push:]
        action["ga4_requests"] = captured_requests[before_request:]
        actions.append(action)
        if action["status"] == "blocked":
            return {
                **recipe,
                "outcome": "blocked",
                "privacy_statement_accepted": accepted,
                "actions": actions,
                "blocker": action["error"],
            }
        try:
            after_text = str(page.locator("body").inner_text(timeout=1500)).casefold()
        except Exception:
            after_text = ""
        if re.search(
            r"(?:thank\s+you|success|confirmed|request\s+received|merci|confirmation|"
            r"demande\s+(?:a\s+bien\s+ete|re[cç]ue)|connexion\s+r[eé]ussie)",
            after_text,
            re.I,
        ):
            return {
                **recipe,
                "outcome": "completed",
                "privacy_statement_accepted": accepted,
                "actions": actions,
            }
        if re.search(r"(?:invalid|required|error|invalide|obligatoire|erreur)", after_text, re.I):
            return {
                **recipe,
                "outcome": "partial",
                "privacy_statement_accepted": accepted,
                "actions": actions,
                "observed_state": "failure",
            }
    return {
        **recipe,
        "outcome": "partial",
        "privacy_statement_accepted": accepted,
        "actions": actions,
        "blocker": "maximum_safe_steps_reached",
    }


def measurement_opportunity_hints(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return evidence-backed prompts for analyst review, never automatic events."""
    hints: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add(
        hint_key: str,
        page: dict[str, Any],
        category: str,
        reason: str,
        materiality: str,
        capability_ids: list[str] | None = None,
    ) -> None:
        template = str(page.get("template", ""))
        journey_id = infer_journey(template)
        variant_id = journey_variant_id(template, str(page.get("url", "")))
        key = (hint_key, journey_id, variant_id)
        suffix = hashlib.sha256(f"{journey_id}|{variant_id}".encode("utf-8")).hexdigest()[:8]
        hint_id = _identifier(f"{hint_key}_{suffix}")
        hint = hints.setdefault(
            key,
            {
                "hint_id": hint_id,
                "hint_key": hint_key,
                "journey_id": journey_id,
                "variant_id": variant_id,
                "category": category,
                "materiality": materiality,
                "evidence_urls": set(),
                "evidence_structure_hashes": set(),
                "capability_ids": set(),
                "reason": reason,
                "requires_interactive_review": True,
            },
        )
        hint["capability_ids"].update(str(value) for value in (capability_ids or []) if value)
        hint["evidence_urls"].add(str(page.get("url", "")))
        structure_hash = str(page.get("rendered_structure_sha256", ""))
        if structure_hash:
            hint["evidence_structure_hashes"].add(structure_hash)

    baseline = {
        "homepage": (
            "homepage_navigation_and_campaign_entry",
            "context",
            "The homepage exposes campaign entry points and primary journey navigation.",
        ),
        "listing": (
            "item_list_discovery",
            "interaction",
            "A rendered listing can support impression-to-selection analysis.",
        ),
        "product_detail": (
            "item_consideration",
            "interaction",
            "A rendered item detail exposes product consideration and option decisions.",
        ),
        "cart": (
            "cart_management",
            "progression",
            "A rendered cart exposes cart review, removal, and checkout-entry decisions.",
        ),
        "checkout": (
            "checkout_progression_and_outcome",
            "outcome",
            "A checkout requires progression, failure, and confirmed-success review.",
        ),
        "lead_form": (
            "lead_funnel_progression_and_success",
            "outcome",
            "A rendered lead or quote form requires start, useful progression, error, and confirmed-success review.",
        ),
        "catalogue": (
            "catalogue_request_progression_and_success",
            "outcome",
            "A catalogue journey may contain a distinct request funnel and outcome.",
        ),
        "appointment": (
            "appointment_progression_and_success",
            "outcome",
            "An appointment journey requires safe progression and confirmed-outcome review.",
        ),
        "account": (
            "authentication_and_account_entry",
            "outcome",
            "Account entry requires successful authentication and gated-capability review.",
        ),
        "post_purchase": (
            "post_purchase_self_service",
            "outcome",
            "Order, return, cancellation, refund, and reorder capabilities need separate decisions.",
        ),
        "newsletter": (
            "newsletter_confirmation",
            "outcome",
            "Newsletter signup is useful only at confirmed subscription success.",
        ),
        "wishlist": (
            "wishlist_management",
            "interaction",
            "Wishlist addition or removal may represent product intent.",
        ),
        "promotion": (
            "promotion_exposure_and_selection",
            "interaction",
            "A merchandising promotion needs exposure and selection review.",
        ),
        "support_or_contact": (
            "support_and_contact_outcomes",
            "outcome",
            "Support and contact surfaces require intent and confirmed-outcome decisions.",
        ),
        "search_results": (
            "site_search_and_result_quality",
            "interaction",
            "Rendered search results support search usage, result quality, and empty-state decisions.",
        ),
        "store_locator": (
            "store_discovery_and_contact",
            "interaction",
            "Store discovery exposes location selection and local contact intent.",
        ),
        "configurator": (
            "configuration_progression_and_completion",
            "progression",
            "A configurator requires meaningful step and completion decisions.",
        ),
    }
    signal_patterns = [
        (
            "filter_and_sort_usage",
            "interaction",
            r"\b(filter|filtre|sort|trier|tri)\b",
            "Rendered controls indicate filtering or sorting that may affect discovery decisions.",
        ),
        (
            "variant_and_size_guidance",
            "interaction",
            r"\b(size|taille|color|couleur|variant|pointure|guide des tailles)\b",
            "Rendered controls indicate product options or guidance requiring item-level modeling review.",
        ),
        (
            "payment_failure",
            "diagnostic",
            r"\b(payment error|payment failed|paiement refuse|paiement échoué|erreur de paiement)\b",
            "Payment-failure language indicates a potentially actionable checkout diagnostic.",
        ),
    ]
    for page in pages:
        if page.get("fetch_error"):
            continue
        template = str(page.get("template", ""))
        if template in baseline:
            hint_key, category, reason = baseline[template]
            add(hint_key, page, category, reason, "material")
        surfaces = page.get("page_surfaces", {}) if isinstance(page.get("page_surfaces"), dict) else {}
        corpus_parts = [
            str(page.get("url", "")),
            str(surfaces.get("title", "")),
            " ".join(str(value) for value in surfaces.get("headings", [])),
            str(surfaces.get("main_text", "")),
            *[
                " ".join(
                    [
                        str(control.get("label", "")),
                        str(control.get("name", "")),
                        " ".join(str(value) for value in control.get("option_values", [])),
                    ]
                )
                for control in page.get("interactive_controls", [])
                if isinstance(control, dict)
            ],
        ]
        if not surfaces:
            # Compatibility for imported/static evidence that predates local
            # page surfaces. Rendered v1.2 reports always use the scoped branch.
            corpus_parts.extend(str(value) for value in page.get("buttons", []))
            corpus_parts.extend(
                str(link.get("text", ""))
                for link in page.get("links", [])
                if isinstance(link, dict)
            )
        corpus = " ".join(corpus_parts).casefold()
        for hint_key, category, pattern, reason in signal_patterns:
            if re.search(pattern, corpus, re.I):
                add(hint_key, page, category, reason, "candidate")
        capability_hints = {
            "tabbed_form": (
                "tabbed_form_outcomes",
                "outcome",
                "Distinct form tabs need an explicit decision on shared versus separate progression and success measurement.",
            ),
            "locator_selection": (
                "locator_result_selection",
                "interaction",
                "Selection of a locator result or map marker is a separate decision point after search.",
            ),
            "faq_accordion": (
                "faq_content_usage",
                "interaction",
                "FAQ expansion may answer a support question and needs a measure-or-exclude decision at family level.",
            ),
            "coupon_application": (
                "coupon_application_outcome",
                "diagnostic",
                "Coupon success and failure may explain discount use and checkout friction.",
            ),
            "modal_dialog": (
                "modal_business_outcome",
                "interaction",
                "The modal's business purpose must be evaluated before deciding whether its outcome merits measurement.",
            ),
            "download": (
                "meaningful_download_outcome",
                "outcome",
                "A meaningful application, brochure, or document download may be a business outcome.",
            ),
            "meaningful_error": (
                "business_process_error",
                "diagnostic",
                "An observed business-process error may explain abandonment and requires an explicit decision.",
            ),
            "filter_sort": (
                "filter_and_sort_usage",
                "interaction",
                "Applied filters or sorting may explain product or content discovery.",
            ),
            "configurator_progression": (
                "configuration_progression_and_completion",
                "progression",
                "Meaningful configuration progression and completion require an explicit decision.",
            ),
        }
        capabilities = page.get("interaction_capabilities")
        if not isinstance(capabilities, list):
            capabilities = detect_interaction_capabilities(page)
        for capability in capabilities:
            if not isinstance(capability, dict):
                continue
            family = str(capability.get("family", ""))
            mapped = capability_hints.get(family)
            if not mapped:
                continue
            hint_key, category, reason = mapped
            add(
                hint_key,
                page,
                category,
                reason,
                str(capability.get("materiality", "candidate")),
                [str(capability.get("capability_id", ""))],
            )

    result: list[dict[str, Any]] = []
    for hint in hints.values():
        result.append(
            {
                **hint,
                "evidence_urls": sorted(hint["evidence_urls"])[:10],
                "evidence_structure_hashes": sorted(hint["evidence_structure_hashes"])[:10],
                "capability_ids": sorted(hint["capability_ids"]),
            }
        )
    return sorted(result, key=lambda item: str(item["hint_id"]))


def finite_value_candidates(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect finite UI choices without deciding their analytics parameter."""
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    for page in pages:
        if page.get("fetch_error"):
            continue
        template = str(page.get("template", "content_or_other"))
        journey_id = infer_journey(template)
        variant_id = journey_variant_id(template, str(page.get("url", "")))
        controls = [
            item
            for item in page.get("interactive_controls", [])
            if isinstance(item, dict)
            and (bool(item.get("visible", True)) or int(item.get("option_count") or 0) > 0)
            and (
                bool(item.get("inside_main", True))
                or not page.get("page_surfaces", {}).get("main_text")
            )
        ]
        for form in relevant_forms(page):
            controls.extend(item for item in form.get("fields", []) if isinstance(item, dict))
        for control in controls:
            raw_values = [str(value).strip() for value in control.get("option_values", []) if str(value).strip()]
            raw_labels = [str(value).strip() for value in control.get("option_labels", []) if str(value).strip()]
            if not raw_values:
                continue
            descriptor = clean_text(
                str(control.get("name") or control.get("id") or control.get("label") or control.get("selector") or "finite choice")
            )
            descriptor_key = _identifier(descriptor or "finite_choice")
            key = (journey_id, variant_id, descriptor_key)
            candidate = candidates.setdefault(
                key,
                {
                    "candidate_id": _identifier(f"values_{descriptor_key}_{hashlib.sha256('|'.join(key).encode('utf-8')).hexdigest()[:8]}", maximum=119),
                    "journey_id": journey_id,
                    "variant_id": variant_id,
                    "source_label": descriptor or "Finite choice",
                    "values": {},
                    "declared_counts": [],
                    "instance_value_sets": [],
                    "evidence_urls": set(),
                },
            )
            candidate["declared_counts"].append(int(control.get("option_count") or len(raw_values)))
            candidate["instance_value_sets"].append(tuple(sorted(set(raw_values))))
            for index, value in enumerate(raw_values):
                label = raw_labels[index] if index < len(raw_labels) else value
                candidate["values"].setdefault(value, label)
            candidate["evidence_urls"].add(str(page.get("url", "")))

    result: list[dict[str, Any]] = []
    for candidate in candidates.values():
        ordered = sorted(candidate.pop("values").items(), key=lambda item: item[0].casefold())
        retained = ordered[:50]
        declared_counts = [int(value) for value in candidate.pop("declared_counts")]
        instance_sets = [tuple(values) for values in candidate.pop("instance_value_sets")]
        captured_value_count = len(retained)
        observed_value_count = max([len(ordered), *declared_counts])
        every_instance_captured = all(
            len(values) == declared_count
            for values, declared_count in zip(instance_sets, declared_counts, strict=True)
        )
        stable_instances = len(set(instance_sets)) <= 1
        if observed_value_count > 50:
            capture_status = "over_50"
        elif every_instance_captured and stable_instances and captured_value_count == observed_value_count:
            capture_status = "complete"
        else:
            capture_status = "incomplete"
        result.append(
            {
                **candidate,
                "capture_status": capture_status,
                "complete": capture_status == "complete",
                "observed_value_count": observed_value_count,
                "captured_value_count": captured_value_count,
                "values": [{"value": value, "label": label} for value, label in retained],
                "evidence_urls": sorted(value for value in candidate["evidence_urls"] if value)[:25],
            }
        )
    return sorted(result, key=lambda item: str(item["candidate_id"]))


def _interaction_gap_id(prefix: str, record: dict[str, Any]) -> str:
    identity = str(record.get("recipe_id") or record.get("variant_id") or "variant")
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    stem = _identifier(f"{prefix}_{record.get('variant_id', 'variant')}", maximum=68)
    return f"{stem}_{digest}"[:79]


def interaction_coverage_gaps(
    unexecuted_recipes: list[dict[str, Any]],
    interaction_runs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gaps = [
        {
            "gap_id": _interaction_gap_id("interaction_not_executed", recipe),
            "journey_id": recipe["journey_id"],
            "variant_id": recipe["variant_id"],
            "material": True,
            "evidence_state": "not_tested",
            "description": (
                "Safe synthetic interaction was not executed for this material funnel form; "
                "success, failure, and gated states remain unconfirmed."
            ),
            "candidate_urls": [recipe["start_url"]],
        }
        for recipe in unexecuted_recipes
    ]
    gaps.extend(
        {
            "gap_id": _interaction_gap_id("interaction_incomplete", run),
            "journey_id": str(run.get("journey_id")),
            "variant_id": str(run.get("variant_id")),
            "material": True,
            "evidence_state": "externally_blocked" if run.get("outcome") == "blocked" else "partial",
            "description": "The safe synthetic form run was partial, blocked, or stopped before a consequential action.",
            "candidate_urls": [str(run.get("start_url"))],
        }
        for run in interaction_runs
        if run.get("outcome") != "completed"
    )
    return gaps


def main() -> int:
    args = parse_args()
    if args.limit <= 0 or args.max_rounds <= 0 or args.interaction_limit < 0:
        raise SystemExit("--limit and --max-rounds must be positive; --interaction-limit cannot be negative.")
    if args.run_id and not re.fullmatch(r"run_[a-f0-9]{32}", args.run_id):
        raise SystemExit("--run-id must use run_<32 lowercase hex> format.")
    root_url = canonical_url(args.url if "://" in args.url else f"https://{args.url}")
    sync_playwright = require_playwright()
    browser_environment = inspect_browser_environment()
    try:
        browser_channel = resolve_browser_channel(args.browser, browser_environment)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    pages: list[dict[str, Any]] = []
    errors: list[SourceError] = []
    blocked_candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    queued: set[str] = set()
    queue: list[dict[str, str]] = []
    candidate_universe: dict[str, dict[str, str]] = {}
    rounds: list[dict[str, Any]] = []
    automatic_interaction_runs: list[dict[str, Any]] = []
    robots_url, robots_sitemaps, robots_rules = discover_robots(
        root_url,
        errors,
    )
    delay_seconds = max(0, args.delay_ms) / 1000
    sitemap_candidates = robots_sitemaps or [root_url.rstrip("/") + "/sitemap.xml"]
    sitemap_urls: list[str] = []
    for sitemap in sitemap_candidates:
        sitemap_urls.extend(
            parse_sitemap(
                sitemap,
                max(0, args.sitemap_limit - len(sitemap_urls)),
                errors,
                delay_seconds=delay_seconds,
            )
        )
        if len(sitemap_urls) >= args.sitemap_limit:
            break
    sitemap_universe_truncated = args.sitemap_limit > 0 and len(sitemap_urls) >= args.sitemap_limit

    def enqueue(url: str, text: str, source: str) -> None:
        candidate_url = canonical_url(url)
        if not candidate_url or candidate_url in seen or not same_host(candidate_url, root_url):
            return
        normalized_text = clean_text(text)
        if candidate_url in queued:
            for record in queue:
                if record["url"] != candidate_url:
                    continue
                if normalized_text and not record.get("text"):
                    record["text"] = normalized_text
                    record["source"] = source
                break
            existing = candidate_universe[candidate_url]
            if normalized_text and not existing.get("text"):
                existing["text"] = normalized_text
                existing["source"] = source
            return
        queued.add(candidate_url)
        record = {"url": candidate_url, "text": normalized_text, "source": source}
        queue.append(record)
        candidate_universe[candidate_url] = dict(record)

    enqueue(root_url, "homepage", "root")
    for seed in args.seed_url:
        enqueue(seed, "explicit journey entry point", "explicit_seed")
    for sitemap_url in sitemap_urls:
        enqueue(sitemap_url, "", "sitemap")
    with sync_playwright() as playwright:
        browser = launch_browser(playwright, browser_channel, headless=not args.headful)
        context = browser.new_context()
        captured_pushes: list[dict[str, Any]] = []
        captured_requests: list[dict[str, Any]] = []
        active_action = {"index": -1}

        def receive_push(_source: Any, payload: Any) -> None:
            if active_action["index"] >= 0:
                captured_pushes.append({"action_index": active_action["index"], "payload": payload})

        context.expose_binding("__ga4DiscoveryCapture", receive_push)
        context.add_init_script(CAPTURE_INIT_SCRIPT)
        page = context.new_page()

        def capture_request(request: Any) -> None:
            if active_action["index"] < 0:
                return
            evidence = _safe_measurement_request(request)
            if evidence:
                captured_requests.append({"action_index": active_action["index"], **evidence})

        page.on("request", capture_request)
        material_unvisited: list[dict[str, Any]] = []
        for round_number in range(1, args.max_rounds + 1):
            page_count_before = len(pages)
            candidate_count_before = len(candidate_universe)
            attempted = 0
            while queue and attempted < args.limit:
                observed_template_counts = Counter(str(item.get("template")) for item in pages if not item.get("fetch_error"))
                observed_families = {
                    family_for_template(
                        str(item.get("template", "content_or_other")),
                        str(item.get("url", "")),
                    )
                    for item in pages
                    if not item.get("fetch_error")
                }
                queue.sort(
                    key=lambda item: candidate_priority(
                        item,
                        root_url,
                        observed_template_counts,
                        observed_families,
                    ),
                    reverse=True,
                )
                selected = queue.pop(0)
                attempted += 1
                current_url = canonical_url(selected["url"])
                queued.discard(current_url)
                seen.add(current_url)
                if robots_rules is not None and not robots_rules.can_fetch(USER_AGENT, current_url):
                    errors.append(
                        SourceError(
                            "robots_disallow",
                            current_url,
                            "Skipped because robots.txt disallows this crawler.",
                        )
                    )
                    blocked_candidates.append(
                        {
                            **selected,
                            "template": infer_template(
                                current_url,
                                str(selected.get("text", "")),
                            ),
                            "reason": "robots_disallow",
                        }
                    )
                    continue
                rendered = collect_rendered_page(page, current_url, root_url, args.timeout_ms)
                pages.append(rendered)
                if delay_seconds:
                    time.sleep(delay_seconds)
                if rendered.get("fetch_error"):
                    errors.append(
                        SourceError(
                            "playwright_crawl",
                            current_url,
                            str(rendered["fetch_error"]),
                        )
                    )
                    continue
                for link in rendered.get("links", []):
                    href = canonical_url(str(link.get("url", "")))
                    enqueue(href, str(link.get("text", "")), "rendered_link")

            observed_template_counts = Counter(str(item.get("template")) for item in pages if not item.get("fetch_error"))
            observed_families = {
                family_for_template(
                    str(item.get("template", "content_or_other")),
                    str(item.get("url", "")),
                )
                for item in pages
                if not item.get("fetch_error")
            }
            remaining = [candidate for url, candidate in candidate_universe.items() if url not in seen]
            material_unvisited = material_unvisited_candidates(
                remaining,
                root_url,
                observed_template_counts,
                observed_families,
            )
            stop_reason = discovery_round_stop_reason(
                len(material_unvisited),
                round_number,
                args.max_rounds,
                len(queue),
            )
            round_pages = pages[page_count_before:]
            rounds.append(
                {
                    "round_number": round_number,
                    "attempted_page_count": attempted,
                    "usable_page_count": sum(not item.get("fetch_error") for item in round_pages),
                    "new_candidate_count": max(0, len(candidate_universe) - candidate_count_before),
                    "material_unvisited_candidate_count": len(material_unvisited),
                    "stop_reason": stop_reason,
                }
            )
            if stop_reason != "continue_targeted_discovery":
                break

        all_recipes = build_auto_interaction_recipes(pages, limit=None)
        recipes = all_recipes[: args.interaction_limit]
        unexecuted_recipes = all_recipes[args.interaction_limit :]
        if not args.no_auto_interact:
            for recipe in recipes:
                automatic_interaction_runs.append(
                    execute_auto_interaction(
                        page,
                        recipe,
                        timeout_ms=args.timeout_ms,
                        active_action=active_action,
                        captured_pushes=captured_pushes,
                        captured_requests=captured_requests,
                    )
                )
        context.close()
        browser.close()

    observed_template_counts = Counter(str(item.get("template")) for item in pages if not item.get("fetch_error"))
    observed_families = {
        family_for_template(
            str(item.get("template", "content_or_other")),
            str(item.get("url", "")),
        )
        for item in pages
        if not item.get("fetch_error")
    }
    remaining_candidates = [candidate for url, candidate in candidate_universe.items() if url not in seen]
    material_unvisited = material_unvisited_candidates(
        remaining_candidates,
        root_url,
        observed_template_counts,
        observed_families,
    )
    outcome, usable_page_count, delivery_notice = discovery_outcome(
        pages,
        errors,
        material_unvisited,
        sitemap_universe_truncated,
    )
    coverage_gaps: list[dict[str, Any]] = []
    if material_unvisited:
        coverage_gaps.append(
            {
                "gap_id": "material_candidates_not_rendered",
                "material": True,
                "evidence_state": "not_tested",
                "description": (f"{len(material_unvisited)} prioritized candidate URLs remain unvisited within the reported sample."),
                "candidate_urls": [item["url"] for item in material_unvisited],
            }
        )
    if sitemap_universe_truncated:
        coverage_gaps.append(
            {
                "gap_id": "sitemap_candidate_cap_reached",
                "material": True,
                "evidence_state": "not_tested",
                "description": (f"The sitemap candidate universe reached the configured cap of {args.sitemap_limit} URLs."),
            }
        )
    if blocked_candidates:
        coverage_gaps.append(
            {
                "gap_id": "robots_blocked_material_candidates",
                "material": True,
                "evidence_state": "externally_blocked",
                "description": (f"{len(blocked_candidates)} candidate URLs were blocked by robots.txt and require interactive or other confirming evidence."),
                "candidate_urls": [item["url"] for item in blocked_candidates[:50]],
            }
        )
    all_recipes = build_auto_interaction_recipes(pages, limit=None)
    recipes = all_recipes[: args.interaction_limit]
    unexecuted_recipes = all_recipes[args.interaction_limit :]
    if args.no_auto_interact:
        unexecuted_recipes = all_recipes
    coverage_gaps.extend(
        interaction_coverage_gaps(unexecuted_recipes, automatic_interaction_runs)
    )
    if coverage_gaps and outcome == "completed":
        outcome = "partial"
        delivery_notice = "Rendered discovery has explicit coverage boundaries; resolve them before claiming complete website coverage."
    generated_at = datetime.now(timezone.utc).isoformat()
    run_id = args.run_id or f"run_{uuid4().hex}"
    host_slug = re.sub(
        r"[^a-z0-9]+",
        "_",
        (urlparse(root_url).hostname or "website").casefold(),
    ).strip("_")
    report_id = (f"discovery_{host_slug}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")[:119].rstrip("_")
    output = {
        "discovery_version": "1.3.0",
        "run_id": run_id,
        "report_id": report_id,
        "generated_at": generated_at,
        "root_url": root_url,
        "generated_by": "discover_site_journeys_playwright.py",
        "crawl_mode": "playwright_rendered_dom",
        "outcome": outcome,
        "attempted_page_count": len(pages),
        "usable_page_count": usable_page_count,
        "candidate_url_count": len(candidate_universe),
        "candidate_family_count": len({candidate_family(item["url"], item.get("text", "")) for item in candidate_universe.values()}),
        "sitemap_url_count": len(sitemap_urls),
        "rounds": rounds,
        "page_limit_reached": bool(rounds and rounds[-1]["attempted_page_count"] >= args.limit and material_unvisited),
        "sitemap_candidate_cap_reached": sitemap_universe_truncated,
        "delivery_notice": delivery_notice,
        "browser": {
            "requested": args.browser,
            "selected_channel": browser_channel,
            "default_browser": browser_environment.get("default_browser"),
            "default_browser_eligible": browser_environment.get("default_browser_eligible"),
        },
        "sources_checked": [
            {
                "source_type": "robots_txt",
                "source_ref": robots_url,
                "used_for": "crawler access rules",
            },
            {
                "source_type": "playwright_crawl",
                "source_ref": root_url,
                "used_for": ("rendered DOM journey discovery and internal dataLayer, GTM, Google tag, and GA4 identifier evidence"),
            },
            *[
                {
                    "source_type": "sitemap",
                    "source_ref": sitemap,
                    "used_for": "prioritized rendered candidate discovery",
                }
                for sitemap in sitemap_candidates
            ],
        ],
        "source_errors": [asdict(error) for error in errors],
        "coverage_gaps": coverage_gaps,
        "material_unvisited_candidates": material_unvisited,
        "blocked_candidates": blocked_candidates,
        "pages_sampled": pages,
        "language_summary": summarize_languages(pages, root_url),
        "measurement_evidence_summary": summarize_measurement_evidence(pages),
        "finite_value_candidates": finite_value_candidates(pages),
        "journeys_discovered": summarize_journeys(pages),
        "measurement_opportunity_hints": measurement_opportunity_hints(pages),
        "journey_coverage_ledger": journey_coverage_ledger(
            pages,
            list(candidate_universe.values()),
            material_unvisited,
            blocked_candidates,
            root_url,
            automatic_interaction_runs,
        ),
        "automatic_interaction_runs": automatic_interaction_runs,
        "notes": [
            "This helper stratifies sitemap branches, preserves rendered link signals, and automatically continues targeted rounds while material candidate families remain.",
            "It accepts a visible privacy statement and safely progresses representative non-transactional forms with clearly synthetic data by default.",
            "It stops at CAPTCHA, payment, order, appointment confirmation, contract, deletion, and other consequential boundaries instead of claiming completion.",
            "Use build_analysis_context_seed.py so every hint becomes an explicit measure, exclude, or unresolved analyst decision.",
            "Technical measurement evidence is internal input. Sensitive-looking dataLayer values are redacted while field structure is retained.",
            "Never claim site-specific gated capabilities from this rendered-DOM inventory. If interactive access fails, record the coverage gap; applicable official or recurrent sector outcomes may remain visibly recommended with to-confirm website data and precise success conditions.",
        ],
    }
    report_errors = validate_discovery_report(output)
    if report_errors:
        raise SystemExit("Generated discovery report failed its contract:\n- " + "\n- ".join(report_errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return discovery_exit_code(outcome)


if __name__ == "__main__":
    raise SystemExit(main())
