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
- the actual Playwright MCP attempt, selected eligible browser, journey-
  discovery outcome, value-discovery outcome, and evidence references.

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
python scripts/inspect_browser_environment.py
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --browser auto --output site_discovery_rendered.json
```

The rendered helper samples links, forms, and buttons after page load. It does
not submit forms, log in, place orders, or mutate live state. Use an interactive
Playwright MCP or browser session for those journeys. Static helper output is
not evidence of a gated journey and must never be used to label a gated
capability or event as observed, or to invent its site-specific pages, values,
or trigger details.

The preflight detects the system default browser and eligible Playwright
channels. Prefer the eligible default, including Microsoft Edge through
`msedge`. If an interactive browser MCP already exists, inspect its configured
channel first; the local preflight cannot inspect agent tools.

## Authenticated Journey Default

Unless the user explicitly opts out, treat synthetic account creation and
customer-space exploration as consented when public self-registration is
available. Use an interactive browser or Playwright MCP to complete signup and
login with synthetic information, then investigate the actual account, order,
return, wishlist, preference, loyalty, and reorder paths. Record the actions and
rendered gated evidence as synthetic account exploration. A static crawler or
the presence of account links is not enough.

When the real authenticated flow cannot be completed, document the concrete
evidence gap and required follow-up. Do not invent site-specific pages,
interactions, values, capabilities, or trigger details beyond the boundary.
This does not make a whole-site measurement specification complete: retain
applicable official GA4 events and recurrent, governed sector or journey events
as `recommended` rows when they answer a named business question. Mark their
site data `to_confirm`, keep confidence low or medium, and write the canonical
success or backend-confirmed trigger precisely. Client-confirmed capabilities
remain `confirmed`; recommendations must never be presented as observations.

Keep discovery evidence and specification coverage separate:

- `authenticated_journey.discovery_status = attempted_blocked` records the
  failed live access attempt;
- the matching journey coverage can remain `assumed` and `included` when the
  plan contains governed recommendation rows;
- a coverage gap records which site-specific details still need confirmation;
- `blocked`, CAPTCHA, missing credentials, or an unreachable confirmation page
  is never by itself a valid reason to omit an applicable checkout, purchase,
  refund, return, cancellation, login, signup, or customer-service branch.

For an unconfirmed gated journey, execute this sequence before event design:

1. Run the browser preflight and prefer the eligible system default or the
   configured browser MCP channel.
2. Open public registration or login and use synthetic information.
3. Complete authentication and confirm that a gated page actually renders.
4. Explore the visible customer navigation and each safely reachable service.
5. Record attempted actions, representative gated URLs or states, and
   screenshot evidence without personal information.
6. Mark only observed outcomes as `observed`. If any step blocks access, stop
   the browser at the boundary and document the gap. Then complete the
   specification from current official GA4 semantics and governed scenario
   rules, using `recommended` only for applicable unobserved outcomes and never
   fabricating website values or capabilities.

## Playwright Decision

When screenshots are required, start by actively discovering an available
Playwright MCP. Do not conclude that browser automation is unavailable merely
because a generic browser tool has no session. A local browser preflight is
useful context, but it is not a substitute for the MCP attempt.

Use Playwright or equivalent browser exploration when:

- menus, filters, checkout, forms, account, or SPA routes are dynamic;
- important journeys require interaction to discover;
- manual browser exploration is unavailable or needs repeatable rendered-DOM
  support;
- the plan will be used as a real delivery and missing journeys would create
  implementation risk.

For a whole-site plan, live rendered exploration is required even when the
requester excludes screenshots. A sitemap or static crawl can support URL
coverage but cannot prove dynamic journeys, interactions, or finite values.
Record the actual outcome in `website_coverage_map.browser_exploration`.

During the same exploration, inspect finite parameter domains. Exercise filters,
sorts, menus, language selectors, shipping and payment choices, and other safely
reachable option sets. Store only values actually observed, and link each
exhaustive list to its browser evidence through the parameter `value_domain`
and each observed entry's `source_ref`.

The screenshot-capture attempt is optional only when screenshots were
explicitly excluded or final screenshots were supplied by the requester. That
does not waive live journey discovery. A dynamic journey or unconfirmed gated
journey still requires a Playwright MCP attempt before an interactive-browser
fallback, and a whole-site plan still records its browser-exploration outcome.
State capture attempts in `screenshot_capture`; do not present a preflight as a
completed attempt.

## Screenshot Capture Gate

Before generating the workbook, record one of these outcomes:

- `captured`: all required Screenshot Register rows have final embedded files.
- `partially_captured`: both captured and blocked rows exist, with a visible
  explanation of the missing scenarios.
- `blocked`: every required row is blocked or not needed, and the concrete
  reason is visible at the top of Screenshot Register and in the delivery reply.
- `not_requested`: the requester explicitly excluded screenshots; every event
  uses `not_needed` coverage.

Never leave `capture_required` or `skip_allowed` in a final delivery. A missing
file for a `captured` row is a delivery error, not a note for later.

## Coverage Gate

Do not finalize a whole-site plan until every measurement-brief journey has a
matching coverage entry. For any important journey not covered by evidence,
either add a coverage gap or mark the journey as assumed, blocked, or out of
scope.

For a journey that is applicable but inaccessible, use `assumed` for the
included specification and keep the blocked state in browser or authenticated-
journey evidence. Use `blocked` plus `needs_discovery` only when no defensible
measurement recommendation can yet be made. This prevents an access failure
from being mistaken for business non-applicability.

For whole-site plans, `journeys_discovered` must list discovered journeys and a
decision for each one. If a discovered journey is marked `include_in_plan`, it
must appear in `measurement_brief` and `journeys_covered`. If it is marked
`needs_discovery`, add a matching coverage gap with the impact and next step.
