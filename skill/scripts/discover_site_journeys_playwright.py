from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from browser_environment import inspect_browser_environment, resolve_browser_channel
from discover_site_journeys import (
    SourceError,
    canonical_url,
    clean_text,
    infer_template,
    same_host,
    summarize_journeys,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a rendered-DOM URL and journey discovery JSON for dynamic websites with Playwright."
    )
    parser.add_argument("url", help="Website root URL, for example https://www.example.com/")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=25, help="Maximum rendered pages to inspect.")
    parser.add_argument("--timeout-ms", type=int, default=20000, help="Navigation timeout in milliseconds.")
    parser.add_argument("--headful", action="store_true", help="Run the selected browser with a visible window.")
    parser.add_argument(
        "--browser",
        choices=["auto", "chromium", "chrome", "msedge", "firefox", "webkit"],
        default="auto",
        help="Browser channel. Auto prefers the eligible system default browser.",
    )
    return parser.parse_args()


def discovery_outcome(pages: list[dict], errors: list[SourceError]) -> tuple[str, int, str]:
    usable = sum(not page.get("fetch_error") for page in pages)
    root_failed = bool(pages and pages[0].get("fetch_error"))
    if usable == 0:
        return "blocked", usable, "Rendered discovery produced no usable page evidence."
    if errors or root_failed:
        return "partial", usable, "Rendered discovery is partial; inspect source_errors before claiming website coverage."
    return "completed", usable, "Rendered discovery completed for the sampled public pages."


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Playwright is required for rendered-DOM discovery. Install it with "
            "`python -m pip install playwright`. Then run "
            "`python scripts/inspect_browser_environment.py` to reuse an eligible installed browser or identify the browser build still needed."
        ) from error
    return sync_playwright


def launch_browser(playwright: Any, channel: str, headless: bool):
    if channel in {"chrome", "msedge"}:
        return playwright.chromium.launch(channel=channel, headless=headless)
    if channel == "firefox":
        return playwright.firefox.launch(headless=headless)
    if channel == "webkit":
        return playwright.webkit.launch(headless=headless)
    return playwright.chromium.launch(headless=headless)


def collect_rendered_page(page: Any, url: str, root_url: str, timeout_ms: int) -> dict[str, Any]:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 8000))
        except Exception:
            pass
    except Exception as error:
        return {"url": url, "template": infer_template(url), "fetch_error": str(error), "links": [], "forms": [], "buttons": []}

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
            name: element.getAttribute("name") || ""
        }))""",
    )
    buttons = page.eval_on_selector_all(
        "button, [role='button'], input[type='submit'], input[type='button']",
        """elements => elements.map(element =>
            (element.innerText || element.value || element.getAttribute("aria-label") || element.getAttribute("title") || element.id || "").trim()
        ).filter(Boolean)""",
    )
    clean_links = [
        {"url": canonical_url(item["url"]), "text": clean_text(item.get("text", "")), "source": url}
        for item in links
        if isinstance(item, dict) and item.get("url") and same_host(str(item["url"]), root_url)
    ]
    return {
        "url": url,
        "template": infer_template(url),
        "links": clean_links[:100],
        "forms": forms[:25] if isinstance(forms, list) else [],
        "buttons": [clean_text(str(button)) for button in buttons[:50]] if isinstance(buttons, list) else [],
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
    queue = [root_url]

    with sync_playwright() as playwright:
        browser = launch_browser(playwright, browser_channel, headless=not args.headful)
        context = browser.new_context()
        page = context.new_page()
        while queue and len(pages) < args.limit:
            current_url = canonical_url(queue.pop(0))
            if current_url in seen or not same_host(current_url, root_url):
                continue
            seen.add(current_url)
            rendered = collect_rendered_page(page, current_url, root_url, args.timeout_ms)
            pages.append(rendered)
            if rendered.get("fetch_error"):
                errors.append(SourceError("playwright_crawl", current_url, str(rendered["fetch_error"])))
                continue
            for link in rendered.get("links", []):
                href = canonical_url(str(link.get("url", "")))
                if href and href not in seen and same_host(href, root_url):
                    queue.append(href)
        context.close()
        browser.close()

    outcome, usable_page_count, delivery_notice = discovery_outcome(pages, errors)
    output = {
        "root_url": root_url,
        "generated_by": "discover_site_journeys_playwright.py",
        "crawl_mode": "playwright_rendered_dom",
        "outcome": outcome,
        "attempted_page_count": len(pages),
        "usable_page_count": usable_page_count,
        "delivery_notice": delivery_notice,
        "browser": {
            "requested": args.browser,
            "selected_channel": browser_channel,
            "default_browser": browser_environment.get("default_browser"),
            "default_browser_eligible": browser_environment.get("default_browser_eligible"),
        },
        "sources_checked": [
            {
                "source_type": "playwright_crawl",
                "source_ref": root_url,
                "used_for": "rendered DOM link, form, button, and route discovery",
            }
        ],
        "source_errors": [asdict(error) for error in errors],
        "pages_sampled": pages,
        "journeys_discovered": summarize_journeys(pages),
        "notes": [
            "This helper samples rendered DOM pages. It does not submit forms, log in, place orders, or mutate live state.",
            "This crawler is not authenticated exploration. Use an interactive browser or Playwright MCP with synthetic information for gated journeys.",
            "Never claim site-specific gated capabilities from this rendered-DOM inventory. If interactive access fails, record the coverage gap; applicable official or recurrent sector outcomes may remain visibly recommended with to-confirm website data and precise success conditions.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0 if outcome == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
