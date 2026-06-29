# Website Coverage Mapping

Use this reference when the user asks for a whole website, large journey set,
or greenfield tracking plan. The goal is to avoid missing important journeys
before event design starts.

## Coverage Source Order

Prefer sources in this order when available:

1. `sitemap.xml` and sitemap indexes for canonical URL families.
2. Header navigation, footer navigation, account menu, breadcrumbs, and mobile
   menu for business-prioritized journeys.
3. `robots.txt` for sitemap discovery and intentionally blocked areas.
4. Internal search, category/listing structures, filters, and result pages.
5. Representative page templates such as homepage, PLP, PDP, cart, checkout,
   account, contact, support, content, store locator, and confirmation pages.
6. Browser or Playwright exploration for dynamic menus, checkout, forms,
   modals, SPA routes, or journeys hidden behind interaction.
7. Existing client tracking plans, dev specs, recette plans, and event
   inventories as hints for client-specific criteria.
8. Analytics, search-console, or backend exports when the user provides them.

Existing tracking files can reveal historical expectations, but they are not
the source of truth for website coverage unless the user explicitly says so.

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
QA Cases.

Use `scripts/discover_site_journeys.py` as a first-pass helper when a URL is
provided and no complete URL inventory exists:

```powershell
python scripts/discover_site_journeys.py https://www.example.com/ --output site_discovery.json
```

The helper reads robots, sitemap candidates, static links, forms, and obvious
URL patterns. Treat its output as input evidence, not final truth. Use
Playwright or manual browser exploration for dynamic navigation, filters,
checkout, account, forms, modals, or SPA routes.

## Playwright Decision

Use Playwright or equivalent browser exploration when:

- no reliable sitemap or URL list exists for a whole-site request;
- menus, filters, checkout, forms, account, or SPA routes are dynamic;
- important journeys require interaction to discover;
- the plan will be used as a real delivery and missing journeys would create
  implementation or recette risk.

Playwright is optional when sitemap, navigation, client files, and page
templates already provide enough coverage for the requested scope. State this
choice in the coverage map.

## Coverage Gate

Do not finalize a whole-site plan until every measurement-brief journey has a
matching coverage entry. For any important journey not covered by evidence,
either add a coverage gap or mark the journey as assumed, blocked, or out of
scope.

For whole-site plans, `journeys_discovered` must list discovered journeys and a
decision for each one. If a discovered journey is marked `include_in_plan`, it
must appear in `measurement_brief` and `journeys_covered`. If it is marked
`needs_discovery`, add a matching coverage gap with the impact and next step.
