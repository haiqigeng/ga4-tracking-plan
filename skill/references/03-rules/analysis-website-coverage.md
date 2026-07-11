# Website Coverage Mapping

Use this reference when the user asks for a whole website, large journey set,
or greenfield tracking plan. The goal is to avoid missing important journeys
before event design starts.

## Contents

- [Coverage Source Order](#coverage-source-order)
- [Coverage Map Requirements](#coverage-map-requirements)
- [Playwright Decision](#playwright-decision)
- [Coverage Gate](#coverage-gate)

## Coverage Source Order

Prefer sources in this precision order when available:

1. User-provided scope, business brief, concerned journeys, URLs, and analysis
   needs. This is the clearest signal for what the plan must answer.
2. Existing client tracking plans, templates, naming conventions, dev specs,
   implementation-review files, event inventories, or approved business documentation. Use
   these for expected structure and client-specific logic, but challenge legacy
   or weak measurement choices.
3. Manual browser exploration. Use it to understand
   real user journeys, visible components, interactions, modals, filters,
   checkout/account gates, and screenshot needs.
4. Playwright or rendered-DOM exploration. Use it when dynamic navigation,
   filters, forms, SPA routes, or interaction-revealed elements matter and the
   environment can run it safely.
5. Header navigation, footer navigation, account menu, breadcrumbs, mobile
   menu, internal search, listing structures, filters, and representative page
   templates such as homepage, PLP, PDP, cart, checkout, account, contact,
   support, content, store locator, and confirmation pages.
6. `sitemap.xml`, sitemap indexes, URL inventories, analytics exports,
   search-console exports, or backend exports when provided. Use these for
   canonical URL coverage and completeness checks.
7. `robots.txt` for sitemap discovery and intentionally blocked areas.
8. Static HTML discovery helper output from `scripts/discover_site_journeys.py`.
   Use it as a support inventory, not as final journey truth.

Existing tracking files can reveal historical expectations, but they are not
the source of truth for GA4 design quality. Sitemap, robots, static HTML, and
exports can reveal missing URL families, but they should not override business
scope, client priorities, or observed user journeys.

## Coverage Map Requirements

Before proposing events for broad scope, capture:

- site scope: whole site, selected journeys, selected pages, or single journey;
- sources checked and what each source was used for;
- covered journeys with representative URLs, page templates, key interactions,
  and coverage status;
- discovered journeys with include, exclude, out-of-scope, or needs-discovery
  decisions;
- coverage gaps, blocked areas, assumptions, and journeys intentionally out of
  scope;
- whether Playwright or deeper browser exploration was required, optional, not
  needed, or blocked.

Use `website_coverage_map` in the structured plan. Keep this information
concise. Do not add a dense visible workbook tab unless the user asks for it;
summarize assumptions and evidence through Overview, Screenshot Register, and
implementation review.

Use `scripts/discover_site_journeys.py` as a support helper when a URL is
provided and no complete URL inventory exists:

```powershell
python scripts/discover_site_journeys.py https://www.example.com/ --output site_discovery.json
```

The helper reads robots, sitemap candidates, static links, forms, and obvious
URL patterns. Treat its output as completeness evidence, not final journey
truth. Use manual browser exploration or Playwright for dynamic navigation,
filters, checkout, account, forms, modals, or SPA routes.

Use `scripts/discover_site_journeys_playwright.py` when rendered DOM discovery
is needed and the environment can run Playwright:

```powershell
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --output site_discovery_rendered.json
```

The rendered helper samples links, forms, and buttons after page load. It does
not submit forms, log in, place orders, or mutate live state. Treat
credential-gated or payment-like journeys as `needs_discovery`, `blocked`, or
`skip_allowed` unless approved test access exists.

## Authenticated Journey Default

Unless the user explicitly opts out, treat synthetic account creation and
customer-space exploration as consented when public self-registration is
available. Use synthetic information and investigate signup, login, account,
order, return, wishlist, preference, loyalty, and reorder paths. Record this as
synthetic account exploration. Do not omit these journeys merely because no
credentials were supplied. When the environment cannot complete the flow,
document the concrete coverage gap and required follow-up. Do not create
implementation events for inaccessible capabilities unless they are observed
or client-confirmed.

## Playwright Decision

Use Playwright or equivalent browser exploration when:

- menus, filters, checkout, forms, account, or SPA routes are dynamic;
- important journeys require interaction to discover;
- manual browser exploration is unavailable or needs repeatable rendered-DOM
  support;
- the plan will be used as a real delivery and missing journeys would create
  implementation risk.

Playwright is optional when the user/client scope, existing client files,
manual browser exploration, navigation, and page templates already provide
enough coverage for the requested scope. State this choice in the coverage map.

## Coverage Gate

Do not finalize a whole-site plan until every measurement-brief journey has a
matching coverage entry. For any important journey not covered by evidence,
either add a coverage gap or mark the journey as assumed, blocked, or out of
scope.

For whole-site plans, `journeys_discovered` must list discovered journeys and a
decision for each one. If a discovered journey is marked `include_in_plan`, it
must appear in `measurement_brief` and `journeys_covered`. If it is marked
`needs_discovery`, add a matching coverage gap with the impact and next step.
