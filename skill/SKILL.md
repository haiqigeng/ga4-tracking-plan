---
name: ga4-tracking-plan
description: Create, review, adapt, and maintain complete, human-readable, implementation-ready GA4 web tracking plans from live website journeys, user input, designs, previous plans, GTM containers, dataLayer evidence, and technical documentation. Use for whole-site or journey-level measurement design, official-first event and parameter selection, justified custom semantics, finite website value discovery, developer-ready dataLayer specifications, supplied-template adaptation, default XLSX generation, and semantic plan updates. Resolve selected GA4 semantics against current official Google documentation before delivery. Do not use for GTM mutation, container cleanup, runtime recette, another analytics platform, or legal approval.
---

# GA4 Tracking Plan

## North Star

Turn live website exploration and all available business, design, and technical
evidence into a complete, adapted, and implementation-ready GA4 tracking plan
for the real user journeys. Use current official GA4 events, parameters,
semantics, and wording first; introduce precise custom elements only where
official constructs cannot represent a meaningful business need. Deliver the
result, in the supplied template or the skill's default template, as a clear
and just-enough human contract that web analysts can review and maintain and
developers can implement directly through the dataLayer.

Keep the work operationally deep and the human output deliberately lean.
Tracking-plan quality is the product; machinery and research records are
internal support.

For a complete plan, read:

- `references/product.md`
- `references/workflow.md`
- `references/discovery-and-coverage.md`
- `references/official-first.md`
- `references/official-semantic-rules.md`
- `references/workbook-contract.md`

Read only the relevant scenario reference:

- supplied measurement framework:
  `references/measurement-framework-intake.md`
- ecommerce: `references/scenario-ecommerce.md`
- search, listing, filtering, sorting, or merchandising discovery:
  `references/scenario-search-and-listing.md`
- lead, form, quote, or booking funnels:
  `references/scenario-lead-generation.md`
- account, support, navigation, or content:
  `references/scenario-authenticated-and-content.md`

## Non-Negotiable Decisions

- Use one adaptive workflow and one quality standard. Never introduce
  small/standard/enterprise tiers, event-count modes, time-box modes, or
  reduced-quality plans.
- Activate only relevant modules such as ecommerce, authentication, supplied
  templates, screenshots, or maintenance.
- Investigate the live website with an interactive browser. Accept the CMP
  choice needed for investigation and use safe synthetic information for
  accessible forms, signup, login, and gated journeys unless the user opts out.
- Build the rendered candidate universe from supplied entry points, stratified
  sitemap evidence, and discovered links. Explore by distinct journey,
  template, route family, and interaction rather than link order or repeated
  product pages. Treat a page cap as a sampling budget, never as a stopping
  condition: run targeted discovery rounds for uncovered material candidates.
- Treat every evidence source according to what it can prove. Distinguish live
  behavior, intended future design, business requirements, current tracking,
  technical data capability, and historical contracts.
- When a measurement framework is supplied, use it as optional, non-governing
  upstream business evidence. Let it seed discovery priorities, candidate
  material journeys, business questions, and semantic facts to investigate.
  It creates a duty to investigate and decide, not a duty to implement. Never
  let it replace or narrow rendered, design, or technical discovery; never
  derive GA4 events, parameters, triggers, or dataLayer structures from it
  mechanically.
- For a new or fresh run, use a new run ID and source inventory containing only
  explicitly supplied artifacts and current-run evidence. Never reuse another
  client's plans, values, or prior discovery merely because they remain in the
  session or filesystem. Bind every report to that run ID, hash, and timestamp.
- Build an evidence-backed view of how the business creates value before
  designing measurement. Cover material entry points, alternate journey
  shapes, success, failure, empty, and post-conversion states without turning
  the exercise into a page or click inventory.
- Maintain a validated internal `analysis-context.json` as the resumable
  evidence, conflict, journey-coverage, and finite-value checkpoint. Delivery
  is blocked when a material journey or value domain is neither covered nor
  explicitly bounded.
- Bind every rendered discovery report to the analysis context by SHA-256.
  Every discovery hint must map to an explicit measured, covered-elsewhere,
  excluded, or unresolved opportunity; every discovered journey and material funnel
  variant must map to the coverage ledger. Never let one successful variant
  close a different route family, funnel shape, or component implementation.
  Treat structural hints as candidates until analyst reasoning establishes
  materiality. Every bounded interaction-family hint still needs an explicit
  measure, covered-elsewhere, or exclude decision; do not turn every detected control into a
  mandatory event.
- Classify rendered pages from weighted route, title, heading, main-content,
  and component evidence. Exclude global header/footer controls from page
  purpose, use whole-word multilingual matching, and retain `unknown` plus
  competing candidates when evidence is ambiguous. Keep a material `unknown`
  as an exploration target until it is resolved or explicitly bounded; never
  relabel it as generic content merely to close coverage.
- Keep factual discovery state separate from analyst resolution. `not_tested`
  is not an external blocker; use `externally_blocked` only for an evidenced
  access or execution barrier and never relabel sampling limits as blocked.
- Include only manually implemented measurement in the tracking plan. Do not
  include automatic or enhanced-measurement events, native/no-push rows, or
  related implementation guidance.
- Read the complete current official table for every selected official event.
  Include required parameters, applicable conditional parameters, and optional
  official parameters supported by a real analysis, business, attribution, or
  implementation need. Do not copy the table mechanically.
- Evaluate official semantics first for every material measurement
  opportunity. This is a sequence rule, not a bias against custom measurement:
  add precise custom events and parameters whenever the official model leaves
  a meaningful business or diagnostic gap.
- Record one concrete internal `business_question` for every non-context
  event. It must explain the decision or analysis the event supports; it is
  reasoning traceability, not a visible workbook column.
- Keep each event's parameter list exact. Never inject inherited page, user, or
  journey variables into an event unless they are genuinely sent with it.
- Classify the value domain of every parameter. Exhaust stable, observable
  finite domains of up to 50 values; record a precise, evidenced reason and
  generation rule for free text, identifiers, URLs, changing inventories,
  structured values, inaccessible values, or domains above 50. A captured
  sample is exhaustive only when the source control exposes its full count and
  every relevant instance agrees; otherwise keep the domain incomplete.
- Localize controlled semantic values to the workbook language and normalize
  them to lowercase ASCII `snake_case`. Keep official enums, codes, technical
  identifiers, authoritative labels, free text, numbers, and booleans in their
  required source format.
- For every finite controlled domain, retain one localized human label per
  technical value and prove that the technical value is the ASCII
  `snake_case` normalization of that label. For a dynamic controlled domain,
  retain the localized label-generation rule.
- Resolve official definitions, conditions, types, examples, and cross-page
  implementation rules from current Google documentation before authoring.
  Preserve the exact official source text internally even when the visible
  wording is faithfully localized. Use equally precise official-like wording
  for custom semantics. Generic filler is invalid.
- Keep `requirement` limited to `required`, `conditional`, or `optional`.
  Store a condition separately.
- Make one event specification the implementation source of truth: event
  meaning, trigger, locations, event-specific parameters, and a quoted
  dataLayer example. Derive the lean Event Matrix, Parameter Reference, and
  event tabs from it. Keep conditions and source paths in the canonical model,
  not as default visible columns.
- Follow an evidenced client dataLayer convention. Use the integrated default
  convention only when no client convention exists. Always quote object keys
  in delivered examples.
- Put reusable page and user state in one core context push. Do not create
  separate page-context and user-context pushes for the same lifecycle moment.
- Inventory relevant user information collected or exposed by the website.
  Distinguish dataLayer presence from its destination; do not silently omit a
  field merely because it is not appropriate as an ordinary GA4 parameter.
- When authenticated journeys exist, specify `user_id` in core user context
  and map it only to the official GA4 User-ID configuration setting. Do not
  model it as an event parameter, user property, or custom dimension.
- Include official `customer_type` on `purchase` as a conditional parameter:
  send `new` or `returning` only when the confirmed order can classify it
  reliably, and omit it when uncertain.
- Include the defining official choice on its own checkout step:
  `payment_type` on `add_payment_info` and `shipping_tier` on
  `add_shipping_info`. When the same concept is deliberately carried into an
  event that does not prescribe it, classify that use as custom and retain the
  explicit custom decision.
- Keep evidence, confidence, source conflict, ownership, registration,
  privacy, cardinality, and agent reasoning out of the default visible
  workbook. Surface a concise exception only when it changes implementation.
- Review the plan as one measurement system before delivery. Reconcile
  overlapping event purposes and triggers, and keep parameter meaning, scope,
  type, destination, commerce continuity, and outcome logic coherent across
  events. Use deterministic validation only where the rule is objective.
- Keep the human workbook lean while delivering versioned machine contracts
  beside it: canonical plan JSON, expected events, one JSON Schema per
  dataLayer push, official verification, approval and hashes, and internal
  evidence context. Do not generate copy-paste JavaScript by default.
- Never ignore visible workbook edits in maintenance. Reconcile supported
  event-tab edits into canonical JSON; require canonical edits for structural
  changes. Detect evidence drift and business-change impact for analyst review
  without mutating or approving the plan automatically.
- For a supplied template, assign an explicit semantic role to its parameter
  registry. Default to all parameters actually used; use a custom-only view
  only when the template owner confirms that meaning. Validate every mapped
  semantic region against the canonical model after saving.

## Adaptive Workflow

1. Resolve the requested scope, target state, workbook language, supplied
   template, previous plan, dataLayer convention, and available evidence.
2. Ingest all relevant user, business, design, technical, GTM, and historical
   artifacts into the validated analysis context, including evidence roles,
   conflicts, hashes where available, and safe-test boundaries.
   When a measurement framework is present, follow
   `references/measurement-framework-intake.md` inside this same intake step;
   do not activate another workflow or reduce independent discovery.
3. Explore real public and safely accessible gated journeys in the rendered
   website. Use stratified sitemap and rendered-link candidates, then run
   targeted rounds for uncovered journey families, page archetypes, and
   bounded interaction families,
   success, failure, empty, and post-conversion states. Use controlled
   synthetic interaction recipes for every material safe funnel variant and
   every distinct locally relevant form purpose within that variant, including
   forms initially hidden behind a local tab or modal.
   Record `not_tested`, `partial`, and `externally_blocked` boundaries without
   inventing behavior or treating a sample cap or another variant's success
   as completeness. A valid partial
   discovery report remains usable input and must continue into analyst
   resolution rather than aborting the workflow. Require an explicit measure,
   covered-elsewhere, or exclude decision for every generated interaction-
   family hint.
4. Build the business-value and journey-variant model, then create an internal
   measurement-opportunity ledger covering every material outcome,
   progression signal, and actionable diagnostic. Give every opportunity an
   explicit measured, covered-elsewhere, excluded, or unresolved disposition before
   choosing events. Every applicable material framework journey or web-
   measurement requirement needs an explicit opportunity disposition, while
   independently discovered needs remain equally eligible for inclusion.
5. For every measured opportunity, evaluate current official GA4 semantics
   first, including the complete event parameter table and applicable
   implementation guidance. Select the official event when it fits; otherwise
   design the justified custom event. Do not let the official-first sequence
   suppress uncovered custom needs.
6. Specify exact triggers, event-specific parameters, finite values, source
   logic, one combined page-and-user core context, and quoted dataLayer
   pushes.
7. Validate journey and measurement-opportunity coverage, official fit, scope,
   requiredness, custom gaps, dataLayer parity,
   GA4 limits, User-ID handling, purchase customer type, event-purpose and
   trigger overlap, plan-wide coherence, framework-intake disposition closure
   when applicable, and human wording. Review and resolve every warning before
   delivery.
8. Build the atomic delivery through the supplied template or
   `assets/default-tracking-plan.xlsx`. Validate the rendered workbook,
   non-overlapping merged-cell structure, supplied-template fidelity,
   per-event schemas, machine contracts, hashes, and approval state.
9. When a previous plan exists, also import and compare it, then deliver a
   complete updated plan plus a concise change log. Never deliver an addendum
   as the only current source of truth.

## Commands

Discover public and safely accessible gated journeys. The rendered helper
automatically continues targeted rounds and executes representative safe
synthetic form progression; use a manual recipe only for a known exception:

```powershell
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --output discovery.json
python scripts/build_analysis_context_seed.py discovery.json --output analysis-context.json --target-state as_is
# Multiple same-site reports from one run merge deterministically:
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --run-id run_11111111111111111111111111111111 --output discovery-round-1.json
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --seed-url https://www.example.com/secondary-entry --run-id run_11111111111111111111111111111111 --output discovery-round-2.json
python scripts/build_analysis_context_seed.py discovery-round-1.json discovery-round-2.json --output analysis-context.json --target-state as_is
# When explicit context overrides website language:
python scripts/build_analysis_context_seed.py discovery.json --output analysis-context.json --language fr --language-basis user
python scripts/capture_interactive_journey.py interactive-journey.json --output journey-evidence.json
```

Validate the internal checkpoint, then build the complete default delivery:

```powershell
python scripts/validate_analysis_context.py analysis-context.json --plan plan.json --discovery-report discovery.json --delivery
python scripts/build_tracking_plan_delivery.py plan.json analysis-context.json --discovery-report discovery.json --output-dir delivery
```

For a supplied workbook, inspect it once and reuse the hash-bound mapping:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-map.json
python scripts/build_tracking_plan_delivery.py plan.json analysis-context.json --discovery-report discovery.json --template client-template.xlsx --mapping template-map.json --output-dir delivery
```

Maintain, detect drift, or target a business change:

```powershell
python scripts/import_tracking_plan_workbook.py previous-plan.xlsx --output previous-plan.json
python scripts/import_tracking_plan_workbook.py edited-plan.xlsx --reconcile-visible-edits --output reconciled-plan.json
python scripts/diff_tracking_plans.py previous-plan.json updated-plan.json --output changes.json
python scripts/detect_tracking_plan_drift.py previous-analysis-context.json analysis-context.json updated-plan.json --before-discovery-report previous-discovery.json --after-discovery-report discovery.json --output drift-report.json
python scripts/analyze_tracking_plan_change_impact.py updated-plan.json change-request.json --analysis-context analysis-context.json --output impact-report.json
```

## Boundaries

Stop after creating, reviewing, adapting, or maintaining the tracking plan.
Do not implement or publish GTM, audit or clean a container, execute Preview or
network recette, make legal decisions, or design another analytics platform.
