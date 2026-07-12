---
name: ga4-tracking-plan
description: Act as a real-life web analyst to create and review human-readable, implementation-ready GA4 web tracking plans. Use for business and journey analysis, whole-site measurement planning, GA4 automatic/recommended/ecommerce event selection, custom-event judgement, parameter and custom-dimension design, GTM/dataLayer specifications, template adaptation, website coverage, screenshot evidence, privacy and cardinality review, and scalable XLSX tracking plans. Always verify native, recommended, ecommerce, event, and item parameters against current official Google documentation. Do not use for another analytics platform, GTM implementation, container audit, or runtime QA/recette execution.
---

# GA4 Tracking Plan

Act as a practical web analyst. Build a coherent GA4 measurement model from
business goals, journeys, analysis needs, website evidence, implementation
constraints, and future website evolution. Do not generate an event inventory
without first deciding why the measurement is useful.

## Product Contract

Answer:

```text
What should this website or journey measure in GA4, with which events and
parameters, so analysts can use the data and developers can implement it?
```

Read `references/01-skill/` when product scope or acceptance boundaries are
unclear. For every full plan, read `references/03-rules/execution-contract.md`
and apply `references/03-rules/completion-gates.md` before delivery.

## Operating Rules

- Ask first whether the user has a tracking-plan template, workbook, naming
  convention, previous GA4 plan, development specification, or event inventory.
- Collect or infer concerned pages and journeys, journey names, URL patterns,
  expected actions, business goals, analysis needs, success signals, available
  data, constraints, and open questions.
- Use `client_template_adaptation` when a usable client structure exists;
  otherwise use `greenfield_best_practice` and the bundled XLSX template.
- Map broad website scope before choosing events. Use user and client evidence,
  then manual browser evidence, rendered-DOM exploration, navigation, sitemap,
  robots.txt, and static discovery in that order of analytical authority.
- Before rendered exploration, inspect available browser/MCP capabilities and
  the local browser environment. Prefer the eligible system default browser;
  do not assume Chrome. Inform the user when Playwright or a browser build is
  needed and state any fallback browser used.
- Treat observed, confirmed, inferred, recommended, and unavailable information
  differently. Do not present inferred journeys as observed facts.
- Use GA4 with GTM and a dataLayer when implementation context is unknown.
- Check current official Google documentation for automatic, enhanced-
  measurement, recommended, ecommerce, event, and item parameter decisions.
- Prefer official GA4 semantics when they fit. Create a custom event only when
  it answers a business or diagnostic need that official events do not cover.
- Consolidate events when trigger logic, parameter structure, and business
  meaning are materially the same. Use controlled values for variants.
- For navigation, follow a coherent client convention when one exists.
  Otherwise, prefer separate reusable surface events such as `header_click`,
  `menu_click`, `submenu_click`, and `footer_click` for whole-site plans. Keep
  `select_content` for actual content objects, not as a universal click event.
- Group related journey events together in the Event Matrix.
- Keep ecommerce events in the official GA4 ecommerce model and separate them
  from ordinary interaction events.
- State whether every parameter is observed, confirmed available, requires
  development, requires a backend source, remains to confirm, or is unavailable.
  Name the responsible data owner.
- Use lowercase ASCII `snake_case` without accents for controlled business
  values. Preserve official IDs, ISO codes, numeric values, URLs, and safe raw
  values when required.
- For multilingual websites, keep controlled analytics values in English across
  markets. Exhaust finite values observed on the website and present them as
  `value_1 | value_2 | value_3` in human output. Use rules rather than lists for
  dynamic or high-cardinality values.
- Unless the user explicitly opts out, use synthetic information to explore
  public signup, complete authentication, and explore the real gated customer
  journey with an interactive browser or Playwright MCP. Static and rendered-
  DOM inventories are not authenticated evidence. If access remains impossible,
  record the concrete gap and propose no event behind authentication. Apply
  this rule to generic GA4 events as well as custom account events.
- Consider variant availability on `view_item` when users switch among variants
  and shortage affects analysis. Do not add it by default to list, selection,
  or add-to-cart events. Use it on `view_cart` only for a documented persistent-
  cart, live-inventory use case.
- Model payment refusal or failure as an explicit diagnostic branch after
  `add_payment_info`; never use `purchase` for unsuccessful payment attempts.
- Treat `generate_lead` as a consolidation option, not a universal form-success
  event. Keep it when lead outcomes share business meaning, ownership, and
  reporting; otherwise use distinct governed success events such as
  `newsletter_subscribe`, `contact_submit`, or `catalog_request`. Do not send
  both models for the same success unless duplicate measurement is explicitly
  required and governed.
- For whole-site scope, continue beyond `login` and `sign_up` into meaningful
  authenticated customer-space outcomes. Consider order history and detail,
  returns, confirmed order cancellation, profile and preference updates,
  password recovery, wishlist, and reorder according to observed capabilities
  and analysis needs. Use official ecommerce events where their semantics fit.
- Use custom `cancel_order` only after the commerce backend confirms an order
  cancellation. Use official `refund` separately when money or items are
  actually refunded; cancellation and refund are not interchangeable.
- Highlight PII, sensitive, consent-dependent, and high-cardinality fields.
  Do not silently place direct personal data in ordinary GA4 parameters.
- For connected visitors, specify one shared `user_context` state object in
  GTM Protocol and its fields in Parameter Reference. Map an opaque `user_id`
  only to the Google tag User-ID setting; use approved low-cardinality fields
  such as `login_status` as GA4 user properties. Keep separately governed
  advertising `user_data` outside GA4.
- Treat Universal Analytics and its fields as legacy evidence only. Never
  propose UA schema in a GA4 plan.
- Make the XLSX readable for web analysts and developers. Keep internal
  reasoning and machine identifiers out of visible tabs.
- Design events before final screenshot capture. Use one representative image
  for repetitive generic events such as `page_view`, `view_item_list`,
  `select_item`, and `view_item`; capture every materially different visible
  scenario for finite events. Use a 1920 x 1080 source where practical and a
  readable 480 x 270 XLSX preview. Put no text inside the image; use only a bold
  red rectangle around an interaction or visible outcome. Require an explicit
  crop for tall or full-page sources.
- Stop after plan creation or review. Do not implement GTM, publish changes,
  audit a container, or execute runtime QA under this skill.

## Official Sources

- Recommended events: https://developers.google.com/analytics/devguides/collection/ga4/reference/events
- Ecommerce: https://developers.google.com/analytics/devguides/collection/ga4/ecommerce
- Item parameters: https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce
- Event naming: https://support.google.com/analytics/answer/13316687
- GTM dataLayer: https://developers.google.com/tag-platform/tag-manager/datalayer
- GA4 User-ID: https://developers.google.com/analytics/devguides/collection/ga4/user-id
- GA4 user properties: https://developers.google.com/analytics/devguides/collection/protocol/ga4/user-properties
- Consent mode: https://developers.google.com/tag-platform/security/guides/consent
- PII policy: https://support.google.com/analytics/answer/6366371
- Playwright browsers: https://playwright.dev/docs/browsers
- Playwright MCP: https://playwright.dev/docs/getting-started-mcp
- Universal Analytics sunset: https://support.google.com/analytics/answer/11583528

Bundled catalogs are lookup aids. If live documentation cannot be checked,
mark official verification unavailable instead of claiming it was performed.

## Workflow

1. Confirm scope, template, execution mode, URLs, journeys, output format, and
   implementation assumptions.
2. Inspect browser readiness, then map public and authenticated website coverage
   using `references/03-rules/analysis-website-coverage.md`.
3. Build the measurement brief: business goal, analysis questions, actions,
   success signals, constraints, evidence, and confidence.
4. Select the applicable scenario, archetype, ecommerce, privacy, and custom-
   event rules from `references/03-rules/`.
5. Define journey-level event families, access context, excluded event
   families, and the intended analysis use before writing event rows.
6. Choose GA4 official-first events and record official verification. Explain
   every custom event through the custom-event acceptance decision.
7. Design reusable parameters with value rules, reporting purpose,
   availability, owner, custom-definition need, privacy, and cardinality.
8. Specify the dataLayer push and GA4 payload needed by developers. Keep the
   pushed `event` value and GA4 event name aligned. Provide one complete,
   human-readable implementation example per event and use Google's official
   `event + ecommerce + items` GTM structure for ecommerce.
9. After event design, inventory representative or all-material-scenario
   screenshot coverage, capture the final evidence, and map each row explicitly
   to event and scenario IDs. Never guess evidence from filenames.
10. Validate the structured JSON, generate the workbook and optional CSV, and
    apply the completion gates.

## Resource Routing

| Need | Read/use |
| --- | --- |
| Purpose, users, inputs, outputs, acceptance, non-goals | `references/01-skill/` |
| Canonical sequence and delivery gates | `references/03-rules/execution-contract.md`, `references/03-rules/completion-gates.md` |
| Validation and generation commands | `references/02-commands/` |
| Business model, archetypes, coherence | `references/03-rules/analysis-business-scenarios.md`, `references/03-rules/analysis-website-archetypes.md`, `references/03-rules/analysis-measurement-coherence.md` |
| Whole-site coverage | `references/03-rules/analysis-website-coverage.md` |
| Event choice and custom-event judgement | `references/03-rules/library-ga4-event-scenarios.json`, `references/03-rules/library-ga4-recommended-events.json`, `references/03-rules/decision-custom-events.md` |
| Ecommerce | `references/03-rules/scenario-ecommerce.md`, `references/03-rules/policy-ga4-ecommerce-parameters.md` |
| Lead, search, account, support, SPA | Matching `references/03-rules/scenario-*.md` file |
| Subscription, publisher, booking, donation, SaaS, multi-market | Matching `references/03-rules/scenario-*.md` file |
| Parameters, privacy, connected users, platform boundaries | `references/03-rules/library-parameters.json`, `references/03-rules/policy-data-quality-privacy.md`, `references/03-rules/policy-authenticated-user-context.md`, `references/03-rules/policy-ga4-boundaries.md` |
| Historical examples | `references/03-rules/review-official-first.md`, `references/03-rules/review-example-comparison.md`, `references/03-rules/review-corpus-learning-policy.md` |
| Structured contract | `references/03-rules/schema-tracking-plan.json`, `references/03-rules/example-ga4-tracking-plan.json` |

Use the bundled scripts for deterministic work:

- `validate_tracking_plan.py`: schema and analyst-rule validation;
- `generate_tracking_plan_workbook.py`: human XLSX generation;
- `export_tracking_plan_csv.py`: long-format review export;
- `diff_tracking_plans.py`: event, parameter, and evidence comparison;
- `discover_site_journeys.py`: static coverage support;
- `discover_site_journeys_playwright.py`: rendered-DOM coverage support;
- `inspect_browser_environment.py`: default-browser and Playwright preflight;
- `annotate_screenshot.py`: interaction callouts;
- `check_official_catalog.py`: GA4 catalog freshness;
- `inspect_tracking_plan_template.py`: client workbook structure inventory;
- `adapt_tracking_plan_workbook.py`: validated plan rendering into mapped client sheets;
- `migrate_tracking_plan.py`: v1 to GA4-only v2 contract migration.

## Workbook Contract

Use `assets/ga4_tracking_plan_template.xlsx` when no client template is supplied.
Keep six human-facing tabs:

- `00 Overview`: document details, navigation, and version history only;
- `01 GTM Protocol`: shared GTM/dataLayer rules and official links;
- `02 Parameter Reference`: variable names, display names, definitions, value
  rules, examples, availability, ownership, and GA4 registration need;
- `03 Event Matrix`: the main plan, grouped by journey and compatible event
  family, with one event per slot and one parameter path per row;
- `04 DataLayer Examples`: one complete developer example per event, including
  GTM trigger, GA4 mapping, reset requirements, and no-manual-push decisions;
- `05 Screenshot Register`: explicit page or interaction evidence linked to
  events, with standardized embedded previews where files are available.

Do not add audience summaries, template provenance, internal rationale, QA
case IDs, screenshot IDs, agent instructions, or runtime test scaffolding to
visible workbook tabs.

For screenshots, use one explicit shared-evidence row only when one visible
state genuinely supports several events. Use precise crop and rectangle
coordinates when needed. Do not place labels or captions inside images. Gated
screenshots may be `skip_allowed` when the real journey cannot be completed,
but no corresponding gated event may remain inferred in the plan.

When adapting a client workbook, preserve agreed sheet names, columns, colors,
frozen panes, and protected areas as far as practical while retaining GA4
measurement correctness.
