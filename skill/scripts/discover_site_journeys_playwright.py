from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
    parser.add_argument("--headful", action="store_true", help="Run Chromium with a visible browser window.")
    return parser.parse_args()


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Playwright is required for rendered-DOM discovery. Install it with "
            "`python -m pip install playwright` and then run "
            "`python -m playwright install chromium`."
        ) from error
    return sync_playwright


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
    pages: list[dict[str, Any]] = []
    errors: list[SourceError] = []
    seen: set[str] = set()
    queue = [root_url]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headful)
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

    output = {
        "root_url": root_url,
        "generated_by": "discover_site_journeys_playwright.py",
        "crawl_mode": "playwright_rendered_dom",
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
            "Credential-gated, payment, account, and checkout journeys still need user-approved access or a skip note.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
