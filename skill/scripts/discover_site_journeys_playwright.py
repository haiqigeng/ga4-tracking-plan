from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from browser_environment import inspect_browser_environment, load_playwright_sync_api, resolve_browser_channel
from discover_site_journeys import (
    USER_AGENT,
    SourceError,
    canonical_url,
    clean_text,
    discover_robots,
    infer_journey,
    infer_template,
    parse_sitemap,
    same_host,
    summarize_journeys,
)

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a rendered-DOM URL and journey discovery JSON for dynamic websites with Playwright."
    )
    parser.add_argument("url", help="Website root URL, for example https://www.example.com/")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=75, help="Maximum rendered pages to inspect.")
    parser.add_argument(
        "--sitemap-limit",
        type=int,
        default=2000,
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
    "store": 575,
    "magasin": 575,
}


def candidate_priority(
    candidate: dict[str, str],
    root_url: str,
    observed_templates: set[str] | None = None,
) -> int:
    url = str(candidate.get("url", ""))
    if canonical_url(url) == canonical_url(root_url):
        return 10_000
    corpus = f'{url} {candidate.get("text", "")}'.casefold()
    score = max((weight for token, weight in JOURNEY_TOKENS.items() if token in corpus), default=100)
    template = infer_template(url)
    if observed_templates is not None and template not in observed_templates:
        score += 500
    path = urlparse(url).path.strip("/")
    score -= min(150, path.count("/") * 20)
    if urlparse(url).query:
        score -= 50
    if candidate.get("source") == "explicit_seed":
        score += 2_000
    return score


def material_unvisited_candidates(
    candidates: list[dict[str, str]],
    root_url: str,
    observed_templates: set[str],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    material: list[dict[str, Any]] = []
    for candidate in candidates:
        template = infer_template(str(candidate.get("url", "")))
        priority = candidate_priority(candidate, root_url, observed_templates)
        if template not in observed_templates or priority >= 550:
            material.append({**candidate, "template": template, "priority": priority})
    return sorted(material, key=lambda item: (-int(item["priority"]), str(item["url"])))[:limit]


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
        return "partial", usable, (
            "Rendered discovery is partial; inspect source_errors and coverage_gaps "
            "before claiming website coverage."
        )
    return "completed", usable, "Rendered discovery covered the material public candidates in the sampled universe."


def _route_variant(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return "/" + "/".join(parts[:2]) if parts else "/"


def journey_coverage_ledger(
    pages: list[dict[str, Any]],
    candidates: list[dict[str, str]],
    material_unvisited: list[dict[str, Any]],
    root_url: str,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    def group(journey_id: str) -> dict[str, Any]:
        return groups.setdefault(
            journey_id,
            {
                "journey_id": journey_id,
                "material": journey_id != "content_navigation",
                "status": "blocked",
                "entry_points": set(),
                "states_covered": set(),
                "variants": set(),
                "evidence_refs": set(),
                "unvisited_material_candidates": set(),
            },
        )

    for candidate in candidates:
        url = str(candidate.get("url", ""))
        journey_id = infer_journey(infer_template(url))
        item = group(journey_id)
        item["entry_points"].add(url)
        item["variants"].add(_route_variant(url))
        if candidate_priority(candidate, root_url) >= 550:
            item["material"] = True
    for page in pages:
        url = str(page.get("url", ""))
        template = str(page.get("template", infer_template(url)))
        item = group(infer_journey(template))
        item["entry_points"].add(url)
        item["variants"].add(_route_variant(url))
        item["evidence_refs"].add(url)
        if not page.get("fetch_error"):
            item["states_covered"].add(template)
            item["status"] = "observed"
            if page.get("forms"):
                item["states_covered"].add("form_present")
    for candidate in material_unvisited:
        url = str(candidate.get("url", ""))
        item = group(infer_journey(str(candidate.get("template", infer_template(url)))))
        item["unvisited_material_candidates"].add(url)
        if item["status"] == "observed":
            item["status"] = "partial"
        elif item["status"] == "blocked":
            item["status"] = "partial"
    result: list[dict[str, Any]] = []
    for item in groups.values():
        result.append(
            {
                **item,
                "entry_points": sorted(item["entry_points"])[:25],
                "states_covered": sorted(item["states_covered"]),
                "variants": sorted(item["variants"])[:25],
                "evidence_refs": sorted(item["evidence_refs"])[:25],
                "unvisited_material_candidates": sorted(
                    item["unvisited_material_candidates"]
                )[:25],
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

    links = page.eval_on_selector_all(
        "a[href]",
        """elements => elements.map(element => ({
            url: new URL(element.getAttribute("href"), document.baseURI).href,
            text: (element.innerText || element.getAttribute("aria-label") || element.getAttribute("title") || "").trim()
        }))""",
    )
    forms = page.eval_on_selector_all(
        "form",
        """elements => elements.map(element => ({
            action: new URL(element.getAttribute("action") || document.location.href, document.baseURI).href,
            method: (element.getAttribute("method") || "get").toLowerCase(),
            id: element.id || "",
            name: element.getAttribute("name") || "",
            fields: [...element.querySelectorAll("input, select, textarea")].slice(0, 50).map(field => ({
                name: field.getAttribute("name") || "",
                id: field.id || "",
                type: (field.getAttribute("type") || field.tagName).toLowerCase(),
                required: !!field.required,
                autocomplete: field.getAttribute("autocomplete") || "",
                option_values: field.tagName === "SELECT"
                    ? [...field.options].slice(0, 50).map(option => option.value || option.textContent.trim())
                    : []
            }))
        }))""",
    )
    buttons = page.eval_on_selector_all(
        "button, [role='button'], input[type='submit'], input[type='button']",
        """elements => elements.map(element =>
            (element.innerText || element.value || element.getAttribute("aria-label") || element.getAttribute("title") || element.id || "").trim()
        ).filter(Boolean)""",
    )
    try:
        measurement_evidence = page.evaluate(
            """() => {
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
            const dataLayer = Array.isArray(window.dataLayer) ? window.dataLayer : [];
            const pushes = dataLayer.slice(-100).map(value => sanitize(value));
            const resources = performance.getEntriesByType("resource").map(entry => entry.name || "");
            const corpus = [document.documentElement.innerHTML, ...resources].join("\\n");
            const unique = values => [...new Set(values)];
            return {
                data_layer_present: Array.isArray(window.dataLayer),
                data_layer_push_count: dataLayer.length,
                data_layer_pushes: pushes,
                gtm_container_ids: unique(corpus.match(/GTM-[A-Z0-9]+/gi) || []).sort(),
                google_tag_ids: unique(corpus.match(/GT-[A-Z0-9]+/gi) || []).sort(),
                ga4_measurement_ids: unique(corpus.match(/G-[A-Z0-9]{6,}/gi) || []).sort()
            };
            }"""
        )
    except Exception as error:
        measurement_evidence = {
            "capture_error": f"{type(error).__name__}: {error}"
        }
    clean_links = [
        {"url": canonical_url(item["url"]), "text": clean_text(item.get("text", "")), "source": url}
        for item in links
        if isinstance(item, dict) and item.get("url") and same_host(str(item["url"]), root_url)
    ]
    record = {
        "url": url,
        "template": infer_template(url),
        "links": clean_links[:100],
        "forms": forms[:25] if isinstance(forms, list) else [],
        "buttons": [clean_text(str(button)) for button in buttons[:50]] if isinstance(buttons, list) else [],
        "privacy_statement_accepted": privacy_acceptance,
        "measurement_evidence": (
            measurement_evidence
            if isinstance(measurement_evidence, dict)
            else {}
        ),
    }
    structure = {
        "url": record["url"],
        "template": record["template"],
        "links": record["links"],
        "forms": record["forms"],
        "buttons": record["buttons"],
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
        record["rendered_dom_sha256"] = hashlib.sha256(
            page.content().encode("utf-8")
        ).hexdigest()
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


def main() -> int:
    args = parse_args()
    root_url = canonical_url(args.url if "://" in args.url else f"https://{args.url}")
    sync_playwright = require_playwright()
    browser_environment = inspect_browser_environment()
    try:
        browser_channel = resolve_browser_channel(args.browser, browser_environment)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    pages: list[dict[str, Any]] = []
    errors: list[SourceError] = []
    seen: set[str] = set()
    queued: set[str] = set()
    queue: list[dict[str, str]] = []
    robots_url, robots_sitemaps, robots_rules = discover_robots(
        root_url,
        errors,
    )
    delay_seconds = max(0, args.delay_ms) / 1000
    sitemap_candidates = robots_sitemaps or [
        root_url.rstrip("/") + "/sitemap.xml"
    ]
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
    sitemap_universe_truncated = (
        args.sitemap_limit > 0 and len(sitemap_urls) >= args.sitemap_limit
    )

    def enqueue(url: str, text: str, source: str) -> None:
        candidate_url = canonical_url(url)
        if (
            not candidate_url
            or candidate_url in queued
            or candidate_url in seen
            or not same_host(candidate_url, root_url)
        ):
            return
        queued.add(candidate_url)
        queue.append({"url": candidate_url, "text": clean_text(text), "source": source})

    enqueue(root_url, "homepage", "root")
    for seed in args.seed_url:
        enqueue(seed, "explicit journey entry point", "explicit_seed")
    for sitemap_url in sitemap_urls:
        enqueue(sitemap_url, "", "sitemap")
    candidate_universe: dict[str, dict[str, str]] = {
        item["url"]: dict(item) for item in queue
    }

    with sync_playwright() as playwright:
        browser = launch_browser(playwright, browser_channel, headless=not args.headful)
        context = browser.new_context()
        page = context.new_page()
        while queue and len(pages) < args.limit:
            observed_templates = {
                str(item.get("template"))
                for item in pages
                if not item.get("fetch_error")
            }
            queue.sort(
                key=lambda item: candidate_priority(
                    item,
                    root_url,
                    observed_templates,
                ),
                reverse=True,
            )
            selected = queue.pop(0)
            current_url = canonical_url(selected["url"])
            queued.discard(current_url)
            seen.add(current_url)
            if (
                robots_rules is not None
                and not robots_rules.can_fetch(USER_AGENT, current_url)
            ):
                errors.append(
                    SourceError(
                        "robots_disallow",
                        current_url,
                        "Skipped because robots.txt disallows this crawler.",
                    )
                )
                continue
            rendered = collect_rendered_page(page, current_url, root_url, args.timeout_ms)
            pages.append(rendered)
            if delay_seconds:
                time.sleep(delay_seconds)
            if rendered.get("fetch_error"):
                errors.append(SourceError("playwright_crawl", current_url, str(rendered["fetch_error"])))
                continue
            for link in rendered.get("links", []):
                href = canonical_url(str(link.get("url", "")))
                enqueue(href, str(link.get("text", "")), "rendered_link")
                if href and same_host(href, root_url):
                    candidate_universe.setdefault(
                        href,
                        {
                            "url": href,
                            "text": clean_text(str(link.get("text", ""))),
                            "source": "rendered_link",
                        },
                    )
        context.close()
        browser.close()

    observed_templates = {
        str(item.get("template"))
        for item in pages
        if not item.get("fetch_error")
    }
    remaining_candidates = [
        candidate
        for url, candidate in candidate_universe.items()
        if url not in seen
    ]
    material_unvisited = material_unvisited_candidates(
        remaining_candidates,
        root_url,
        observed_templates,
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
                "description": (
                    f"{len(material_unvisited)} prioritized candidate URLs remain unvisited "
                    "within the reported sample."
                ),
                "candidate_urls": [item["url"] for item in material_unvisited],
            }
        )
    if sitemap_universe_truncated:
        coverage_gaps.append(
            {
                "gap_id": "sitemap_candidate_cap_reached",
                "material": True,
                "description": (
                    f"The sitemap candidate universe reached the configured cap of "
                    f"{args.sitemap_limit} URLs."
                ),
            }
        )
    output = {
        "root_url": root_url,
        "generated_by": "discover_site_journeys_playwright.py",
        "crawl_mode": "playwright_rendered_dom",
        "outcome": outcome,
        "attempted_page_count": len(pages),
        "usable_page_count": usable_page_count,
        "candidate_url_count": len(candidate_universe),
        "sitemap_url_count": len(sitemap_urls),
        "page_limit_reached": len(pages) >= args.limit and bool(queue),
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
                "used_for": (
                    "rendered DOM journey discovery and internal dataLayer, GTM, "
                    "Google tag, and GA4 identifier evidence"
                ),
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
        "pages_sampled": pages,
        "measurement_evidence_summary": summarize_measurement_evidence(pages),
        "journeys_discovered": summarize_journeys(pages),
        "journey_coverage_ledger": journey_coverage_ledger(
            pages,
            list(candidate_universe.values()),
            material_unvisited,
            root_url,
        ),
        "notes": [
            "This helper uses sitemap and rendered-link candidates, prioritizes materially distinct journeys and templates, and reports unvisited material candidates instead of treating a page cap as completeness.",
            "It accepts a visible privacy statement by default, but does not submit forms, log in, place orders, or mutate live state.",
            "Use capture_interactive_journey.py or an interactive browser with synthetic information for gated journeys.",
            "Technical measurement evidence is internal input. Sensitive-looking dataLayer values are redacted while field structure is retained.",
            "Never claim site-specific gated capabilities from this rendered-DOM inventory. If interactive access fails, record the coverage gap; applicable official or recurrent sector outcomes may remain visibly recommended with to-confirm website data and precise success conditions.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0 if outcome == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
