from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
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
        self.title_parts: list[str] = []
        self.headings: list[str] = []
        self.main_parts: list[str] = []
        self._active_link: str | None = None
        self._active_text: list[str] = []
        self._title_depth = 0
        self._heading_depth = 0
        self._main_depth = 0
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._title_depth += 1
        if tag in {"h1", "h2"}:
            self._heading_depth += 1
        if tag in {"main", "article"}:
            self._main_depth += 1
        if tag in {"header", "footer", "nav", "aside"}:
            self._ignored_depth += 1
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
        if self._title_depth:
            self.title_parts.append(data)
        if self._heading_depth and not self._ignored_depth:
            value = clean_text(data)
            if value:
                self.headings.append(value)
        if self._main_depth and not self._ignored_depth:
            self.main_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active_link:
            self.links.append(LinkSignal(self._active_link, clean_text(" ".join(self._active_text)), self.base_url))
            self._active_link = None
            self._active_text = []
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag in {"h1", "h2"} and self._heading_depth:
            self._heading_depth -= 1
        if tag in {"main", "article"} and self._main_depth:
            self._main_depth -= 1
        if tag in {"header", "footer", "nav", "aside"} and self._ignored_depth:
            self._ignored_depth -= 1


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:160]


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=20) as response:
        data = response.read(MAX_BYTES)
    return data.decode("utf-8", "ignore")


def same_host(url: str, root: str) -> bool:
    def normalized_host(value: str) -> str:
        host = (urlparse(value).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host

    return normalized_host(url) == normalized_host(root)


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


def discover_robots(
    root_url: str,
    errors: list[SourceError],
) -> tuple[str, list[str], RobotFileParser | None]:
    robots_url = urljoin(root_url, "/robots.txt")
    try:
        text = fetch_text(robots_url)
    except Exception as error:
        errors.append(SourceError("robots_txt", robots_url, str(error)))
        return robots_url, [], None
    rules = RobotFileParser()
    rules.set_url(robots_url)
    rules.parse(text.splitlines())
    sitemaps = []
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())
    return robots_url, sitemaps, rules


def parse_sitemap(
    url: str,
    limit: int,
    errors: list[SourceError],
    seen: set[str] | None = None,
    delay_seconds: float = 0.0,
) -> list[str]:
    seen = seen or set()
    url = canonical_url(url)
    if url in seen or len(seen) >= 100 or limit <= 0:
        return []
    seen.add(url)
    try:
        text = fetch_text(url)
    except Exception as error:
        errors.append(SourceError("sitemap", url, str(error)))
        return []
    if delay_seconds:
        time.sleep(delay_seconds)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as error:
        errors.append(SourceError("sitemap", url, f"XML parse error: {error}"))
        return []
    locations = [canonical_url(loc.text.strip()) for loc in root.findall(".//{*}loc") if loc.text]
    if root.tag.rsplit("}", 1)[-1].lower() == "sitemapindex":
        urls: list[str] = []
        children = locations[:100]
        for index, child in enumerate(children):
            remaining_children = len(children) - index
            remaining_limit = limit - len(urls)
            if remaining_limit <= 0:
                break
            # Allocate a fair share to every sitemap branch so a large product
            # sitemap cannot hide categories, services, account, or support.
            child_limit = max(1, math.ceil(remaining_limit / remaining_children))
            urls.extend(
                parse_sitemap(
                    child,
                    child_limit,
                    errors,
                    seen,
                    delay_seconds,
                )
            )
            if len(urls) >= limit:
                break
        return urls[:limit]
    return locations[:limit]


def normalize_signal_text(value: Any) -> str:
    """Normalize multilingual page evidence without enabling substring matches."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def signal_contains_phrase(value: Any, phrase: str) -> bool:
    corpus = normalize_signal_text(value)
    normalized_phrase = normalize_signal_text(phrase)
    if not corpus or not normalized_phrase:
        return False
    expression = r"(?<![a-z0-9])" + re.escape(normalized_phrase).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return re.search(expression, corpus) is not None


ARCHETYPE_PHRASES: dict[str, tuple[str, ...]] = {
    "checkout": ("checkout", "paiement", "payment", "finaliser commande", "passer commande"),
    "cart": ("cart", "panier", "basket"),
    "post_purchase": (
        "order history",
        "mes commandes",
        "historique commande",
        "retour commande",
        "return order",
        "annuler commande",
        "cancel order",
        "remboursement",
        "refund",
    ),
    "account": ("account", "mon compte", "espace client", "login", "connexion", "sign up", "inscription"),
    "lead_form": ("demande de devis", "devis", "quote", "estimate", "estimation", "mon projet", "simulation"),
    "appointment": ("rendez vous", "appointment", "booking", "reservation"),
    "catalogue": ("catalogue", "catalog", "brochure"),
    "newsletter": ("newsletter", "infolettre", "lettre d information"),
    "wishlist": ("wishlist", "favori", "favorite", "liste d envies"),
    "promotion": ("promotion", "promo", "offre speciale", "soldes", "discount", "bon plan"),
    "store_locator": (
        "store locator",
        "localisateur",
        "trouver un magasin",
        "trouver une station",
        "point de vente",
        "points de vente",
        "station service",
        "magasin",
        "agence",
        "showroom",
    ),
    "configurator": ("configurateur", "configurator", "personnaliser", "customize"),
    "support_or_contact": ("contact", "nous contacter", "help", "aide", "faq", "service client"),
    "search_results": ("search results", "resultats de recherche", "recherche", "search"),
    "product_detail": ("fiche produit", "product detail", "produit", "product"),
    "listing": ("category", "categorie", "collection", "boutique", "filter", "filtre", "sort", "trier"),
}


ARCHETYPE_ROUTE_PATTERNS: dict[str, tuple[str, ...]] = {
    "product_detail": (r"/(?:p|products?|produits?)/[^/]+/?$",),
    "listing": (
        r"/(?:products?|produits?)/?$",
        r"/(?:category|categorie|collection|boutique)(?:/|$)",
    ),
    "store_locator": (r"/(?:store-locator|localisateur|magasins?|agences?|showrooms?|points?-de-vente|stations?-service)(?:/|$)",),
    "support_or_contact": (r"/(?:contact|aide|help|faq|service-client)(?:/|$)",),
    "post_purchase": (r"/(?:order-history|mes-commandes|retours?|returns?|remboursements?|refunds?)(?:/|$)",),
    "lead_form": (r"/(?:devis|quote|estimate|estimation|mon-projet|simulation)(?:/|$)",),
    "appointment": (r"/(?:rendez-vous|appointment|booking|reservation)(?:/|$)",),
    "catalogue": (r"/(?:catalogue|catalog|brochure)(?:/|$)",),
    "account": (r"/(?:account|compte|login|connexion|inscription|sign-up)(?:/|$)",),
    "checkout": (r"/(?:checkout|paiement|payment|commande)(?:/|$)",),
    "cart": (r"/(?:cart|panier|basket)(?:/|$)",),
    "search_results": (r"/(?:search|recherche)(?:/|$)",),
    "promotion": (r"/(?:promotions?|promo|soldes|offres-speciales?)(?:/|$)",),
    "configurator": (r"/(?:configurateur|configurator)(?:/|$)",),
}

ARCHETYPE_WEAK_ROUTE_PATTERNS: dict[str, tuple[str, ...]] = {
    # Short commerce aliases are useful supporting evidence but are too
    # ambiguous to classify a page without a second local signal.
    "listing": (r"/c/[^/]+/?$",),
}


def classify_page_archetype(
    url: str,
    surfaces: dict[str, Any] | None = None,
    *,
    text: str = "",
) -> dict[str, Any]:
    """Classify the page purpose from weighted local surfaces.

    Global header/footer copy is deliberately ignored. The result retains
    competing candidates so uncertain pages become an exploration target
    instead of being silently forced into a wrong journey.
    """
    path = urlparse(url).path or "/"
    if path in {"", "/"}:
        return {
            "primary": "homepage",
            "confidence": "high",
            "candidates": [{"template": "homepage", "score": 100, "reasons": ["root route"]}],
        }

    provided = surfaces or {}
    weighted_surfaces: tuple[tuple[str, Any, int], ...] = (
        ("title", provided.get("title", ""), 6),
        ("headings", provided.get("headings", ""), 6),
        ("main", provided.get("main", provided.get("main_text", "")), 2),
        ("components", provided.get("components", ""), 3),
        # Backward-compatible text is intentionally weak because historical
        # callers passed every visible control, including global navigation.
        ("legacy_text", text, 1),
    )
    scores = {template: 0 for template in ARCHETYPE_PHRASES}
    reasons: dict[str, list[str]] = {template: [] for template in ARCHETYPE_PHRASES}
    decomposed_path = unicodedata.normalize("NFKD", path)
    decomposed_path = "".join(character for character in decomposed_path if not unicodedata.combining(character))
    normalized_path = re.sub(r"[^a-z0-9/]+", "-", decomposed_path.casefold())
    for template, patterns in ARCHETYPE_ROUTE_PATTERNS.items():
        if any(re.search(pattern, normalized_path) for pattern in patterns):
            scores[template] += 12
            reasons[template].append("route pattern")
    for template, patterns in ARCHETYPE_WEAK_ROUTE_PATTERNS.items():
        if any(re.search(pattern, normalized_path) for pattern in patterns):
            scores[template] += 4
            reasons[template].append("weak route pattern")
    for surface_name, value, weight in weighted_surfaces:
        if not value:
            continue
        if isinstance(value, (list, tuple, set)):
            value = " ".join(str(item) for item in value)
        for template, phrases in ARCHETYPE_PHRASES.items():
            matches = [phrase for phrase in phrases if signal_contains_phrase(value, phrase)]
            if not matches:
                continue
            scores[template] += weight + min(2, len(matches) - 1)
            reasons[template].append(f"{surface_name}: {', '.join(matches[:3])}")

    ranked = sorted(
        (
            {"template": template, "score": score, "reasons": reasons[template]}
            for template, score in scores.items()
            if score > 0
        ),
        key=lambda item: (-int(item["score"]), str(item["template"])),
    )
    top_score = int(ranked[0]["score"]) if ranked else 0
    second_score = int(ranked[1]["score"]) if len(ranked) > 1 else 0
    ambiguous = second_score >= 5 and top_score - second_score < 2
    primary = str(ranked[0]["template"]) if top_score >= 5 and not ambiguous else "unknown"
    confidence = "high" if primary != "unknown" and top_score >= 12 and top_score - second_score >= 4 else ("medium" if primary != "unknown" else "low")
    return {
        "primary": primary,
        "confidence": confidence,
        "candidates": ranked[:5],
    }


def infer_template(url: str, text: str = "") -> str:
    """Compatibility wrapper for URL and concise link-label candidates."""
    surfaces = {"headings": text} if text else None
    return str(classify_page_archetype(url, surfaces)["primary"])


def infer_journey(template: str) -> str:
    mapping = {
        "homepage": "homepage_discovery",
        "listing": "product_listing",
        "search_results": "site_search",
        "product_detail": "product_detail",
        "cart": "cart",
        "checkout": "checkout",
        "account": "account",
        "lead_form": "lead_generation",
        "appointment": "appointment_booking",
        "catalogue": "catalogue_request",
        "newsletter": "newsletter_signup",
        "wishlist": "wishlist",
        "promotion": "promotion_engagement",
        "store_locator": "store_discovery",
        "configurator": "configuration",
        "support_or_contact": "support_contact",
        "post_purchase": "post_purchase_service",
        "unknown": "unknown",
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
    surfaces = {
        "title": clean_text(" ".join(parser.title_parts)),
        "headings": parser.headings[:30],
        "main": re.sub(r"\s+", " ", " ".join(parser.main_parts)).strip()[:5000],
        "components": " ".join(
            [
                *[f"form {form.get('id', '')} {form.get('name', '')}" for form in parser.forms],
                *parser.buttons,
            ]
        ),
    }
    classification = classify_page_archetype(url, surfaces)
    return {
        "url": url,
        "template": classification["primary"],
        "classification_diagnostic": classification,
        "page_surfaces": surfaces,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
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
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=250,
        help="Politeness delay between requests in milliseconds.",
    )
    return parser.parse_args()


def discovery_outcome(pages: list[dict], errors: list[SourceError]) -> tuple[str, int, str]:
    usable = sum(not page.get("fetch_error") for page in pages)
    root_failed = bool(pages and pages[0].get("fetch_error"))
    if usable == 0:
        return "blocked", usable, "Static discovery produced no usable page evidence."
    if errors or root_failed:
        return "partial", usable, "Static discovery is partial; inspect source_errors before using any evidence."
    return "completed", usable, "Static discovery completed as supporting evidence only."


def main() -> int:
    args = parse_args()
    root_url = canonical_url(args.url if "://" in args.url else f"https://{args.url}")
    errors: list[SourceError] = []
    robots_url, robots_sitemaps, robots_rules = discover_robots(
        root_url,
        errors,
    )
    delay_seconds = max(0, args.delay_ms) / 1000
    sitemap_candidates = robots_sitemaps or [urljoin(root_url, "/sitemap.xml")]
    sitemap_urls: list[str] = []
    for sitemap in sitemap_candidates:
        sitemap_urls.extend(
            parse_sitemap(
                sitemap,
                args.limit,
                errors,
                delay_seconds=delay_seconds,
            )
        )
        if sitemap_urls:
            break
    seed_urls = [root_url, *[url for url in sitemap_urls if same_host(url, root_url)]]
    seen: set[str] = set()
    pages = []
    for url in seed_urls:
        if url in seen:
            continue
        seen.add(url)
        if robots_rules is not None and not robots_rules.can_fetch(USER_AGENT, url):
            errors.append(
                SourceError(
                    "robots_disallow",
                    url,
                    "Skipped because robots.txt disallows this crawler.",
                )
            )
            continue
        page = parse_page(url)
        pages.append(page)
        if delay_seconds:
            time.sleep(delay_seconds)
        if page.get("fetch_error"):
            errors.append(SourceError("page", url, str(page["fetch_error"])))
        if len(pages) >= args.limit:
            break
    outcome, usable_page_count, delivery_notice = discovery_outcome(pages, errors)
    output = {
        "root_url": root_url,
        "generated_by": "discover_site_journeys.py",
        "crawl_mode": "static_html",
        "outcome": outcome,
        "attempted_page_count": len(pages),
        "usable_page_count": usable_page_count,
        "delivery_notice": delivery_notice,
        "sources_checked": [
            {"source_type": "robots_txt", "source_ref": robots_url, "used_for": "sitemap discovery"},
            *[{"source_type": "sitemap", "source_ref": sitemap, "used_for": "URL discovery"} for sitemap in sitemap_candidates],
            {"source_type": "static_html", "source_ref": root_url, "used_for": "static HTML link and form discovery"},
        ],
        "source_errors": [asdict(error) for error in errors],
        "pages_sampled": pages,
        "journeys_discovered": summarize_journeys(pages),
        "notes": [
            "Static discovery is supporting evidence and never satisfies the live-rendered exploration gate.",
            "Use browser or Playwright exploration for dynamic menus, checkout, account, forms, filters, and SPA routes.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    return 0 if outcome == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
