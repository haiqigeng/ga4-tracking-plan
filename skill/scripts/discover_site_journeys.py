from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

USER_AGENT = "ga4-tracking-plan-site-discovery/1.0"
MAX_BYTES = 2_000_000


@dataclass
class LinkSignal:
    url: str
    text: str
    source: str


@dataclass
class SourceError:
    source_type: str
    source_ref: str
    message: str


class SignalParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[LinkSignal] = []
        self.forms: list[dict[str, str]] = []
        self.buttons: list[str] = []
        self._active_link: str | None = None
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "a" and attr.get("href"):
            self._active_link = urljoin(self.base_url, attr["href"])
            self._active_text = []
        elif tag == "form":
            self.forms.append(
                {
                    "action": urljoin(self.base_url, attr.get("action", "")),
                    "method": attr.get("method", "get").lower(),
                    "id": attr.get("id", ""),
                    "name": attr.get("name", ""),
                }
            )
        elif tag == "button":
            label = attr.get("aria-label") or attr.get("title") or attr.get("name") or attr.get("id")
            if label:
                self.buttons.append(clean_text(label))

    def handle_data(self, data: str) -> None:
        if self._active_link:
            self._active_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_link:
            self.links.append(LinkSignal(self._active_link, clean_text(" ".join(self._active_text)), self.base_url))
            self._active_link = None
            self._active_text = []


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:160]


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        data = response.read(MAX_BYTES)
    return data.decode("utf-8", "ignore")


def same_host(url: str, root: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(root).netloc.lower()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid", "msclkid"}
        ]
    )
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.params, query, ""))


def discover_robots(root_url: str, errors: list[SourceError]) -> tuple[str, list[str]]:
    robots_url = urljoin(root_url, "/robots.txt")
    try:
        text = fetch_text(robots_url)
    except Exception as error:
        errors.append(SourceError("robots_txt", robots_url, str(error)))
        return robots_url, []
    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())
    return robots_url, sitemaps


def parse_sitemap(url: str, limit: int, errors: list[SourceError], seen: set[str] | None = None) -> list[str]:
    seen = seen or set()
    url = canonical_url(url)
    if url in seen or len(seen) >= limit:
        return []
    seen.add(url)
    try:
        text = fetch_text(url)
    except Exception as error:
        errors.append(SourceError("sitemap", url, str(error)))
        return []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        errors.append(SourceError("sitemap", url, f"XML parse error: {error}"))
        return []
    locations = [canonical_url(loc.text.strip()) for loc in root.findall(".//{*}loc") if loc.text]
    if root.tag.rsplit("}", 1)[-1].lower() == "sitemapindex":
        urls: list[str] = []
        for child in locations:
            urls.extend(parse_sitemap(child, limit - len(urls), errors, seen))
            if len(urls) >= limit:
                break
        return urls[:limit]
    return locations[:limit]


def infer_template(url: str) -> str:
    path = urlparse(url).path.lower()
    if path in {"", "/"}:
        return "homepage"
    if any(token in path for token in ["checkout", "commande", "payment", "paiement"]):
        return "checkout"
    if any(token in path for token in ["cart", "panier", "basket"]):
        return "cart"
    if any(token in path for token in ["account", "compte", "login", "connexion"]):
        return "account"
    if any(token in path for token in ["contact", "help", "aide", "faq", "service-client"]):
        return "support_or_contact"
    if any(token in path for token in ["search", "recherche"]):
        return "search_results"
    if re.search(r"/p/|/product|/produit", path):
        return "product_detail"
    if any(token in path for token in ["category", "categorie", "collection", "boutique"]):
        return "listing"
    return "content_or_other"


def infer_journey(template: str) -> str:
    mapping = {
        "homepage": "homepage_discovery",
        "listing": "product_listing",
        "search_results": "site_search",
        "product_detail": "product_detail",
        "cart": "cart",
        "checkout": "checkout",
        "account": "account",
        "support_or_contact": "support_contact",
    }
    return mapping.get(template, "content_navigation")


def parse_page(url: str) -> dict[str, Any]:
    try:
        text = fetch_text(url)
    except Exception as error:
        return {"url": url, "fetch_error": str(error), "links": [], "forms": [], "buttons": []}
    parser = SignalParser(url)
    parser.feed(text)
    links = [asdict(link) for link in parser.links if same_host(link.url, url)]
    return {
        "url": url,
        "template": infer_template(url),
        "links": links[:100],
        "forms": parser.forms[:25],
        "buttons": parser.buttons[:50],
    }


def summarize_journeys(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_journey: dict[str, dict[str, Any]] = {}
    for page in pages:
        template = page.get("template", "content_or_other")
        journey_id = infer_journey(str(template))
        item = by_journey.setdefault(
            journey_id,
            {
                "journey_id": journey_id,
                "journey_name": journey_id.replace("_", " ").title(),
                "representative_urls": [],
                "page_templates": [],
                "key_interactions": set(),
                "source_refs": ["site discovery helper"],
            },
        )
        item["representative_urls"].append(page["url"])
        if template not in item["page_templates"]:
            item["page_templates"].append(template)
        if page.get("forms"):
            item["key_interactions"].add("form submission")
        link_text = " ".join(link.get("text", "") for link in page.get("links", []))
        if re.search(r"search|recherche", link_text, re.I):
            item["key_interactions"].add("site search")
        if re.search(r"cart|panier|basket", link_text, re.I):
            item["key_interactions"].add("cart access")
        if re.search(r"account|compte|login|connexion", link_text, re.I):
            item["key_interactions"].add("account access")
    result = []
    for item in by_journey.values():
        item["representative_urls"] = item["representative_urls"][:10]
        item["key_interactions"] = sorted(item["key_interactions"]) or ["page view"]
        result.append(item)
    return sorted(result, key=lambda item: item["journey_id"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a privacy-safe URL and journey discovery JSON for a website.")
    parser.add_argument("url", help="Website root URL, for example https://www.example.com/")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum sitemap/page URLs to inspect.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_url = canonical_url(args.url if "://" in args.url else f"https://{args.url}")
    errors: list[SourceError] = []
    robots_url, robots_sitemaps = discover_robots(root_url, errors)
    sitemap_candidates = robots_sitemaps or [urljoin(root_url, "/sitemap.xml")]
    sitemap_urls: list[str] = []
    for sitemap in sitemap_candidates:
        sitemap_urls.extend(parse_sitemap(sitemap, args.limit, errors))
        if sitemap_urls:
            break
    seed_urls = [root_url, *[url for url in sitemap_urls if same_host(url, root_url)]]
    seen: set[str] = set()
    pages = []
    for url in seed_urls:
        if url in seen:
            continue
        seen.add(url)
        page = parse_page(url)
        pages.append(page)
        if page.get("fetch_error"):
            errors.append(SourceError("page", url, str(page["fetch_error"])))
        if len(pages) >= args.limit:
            break
    output = {
        "root_url": root_url,
        "generated_by": "discover_site_journeys.py",
        "crawl_mode": "static_html",
        "sources_checked": [
            {"source_type": "robots_txt", "source_ref": robots_url, "used_for": "sitemap discovery"},
            *[
                {"source_type": "sitemap", "source_ref": sitemap, "used_for": "URL discovery"}
                for sitemap in sitemap_candidates
            ],
            {"source_type": "static_html", "source_ref": root_url, "used_for": "static HTML link and form discovery"},
        ],
        "source_errors": [asdict(error) for error in errors],
        "pages_sampled": pages,
        "journeys_discovered": summarize_journeys(pages),
        "notes": [
            "This helper is a first-pass discovery aid, not a full Playwright crawl.",
            "Use browser or Playwright exploration for dynamic menus, checkout, account, forms, filters, and SPA routes.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
