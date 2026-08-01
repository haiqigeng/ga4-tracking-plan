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
- `references/official-first.md`
- `references/workbook-contract.md`

Read only the relevant scenario reference:

- ecommerce: `references/scenario-ecommerce.md`
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
- Build the rendered candidate universe from supplied entry points, sitemaps,
  and discovered links; prioritize materially distinct journeys and templates.
  A page cap, sitemap cap, blocked state, or unvisited material candidate makes
  coverage partial, never complete.
- Treat every evidence source according to what it can prove. Distinguish live
  behavior, intended future design, business requirements, current tracking,
  technical data capability, and historical contracts.
- Build an evidence-backed view of how the business creates value before
  designing measurement. Cover material entry points, alternate journey
  shapes, success, failure, empty, and post-conversion states without turning
  the exercise into a page or click inventory.
- Maintain a validated internal `analysis-context.json` as the resumable
  evidence, conflict, journey-coverage, and finite-value checkpoint. Delivery
  is blocked when a material journey or value domain is neither covered nor
  explicitly bounded.
- Include only manually implemented measurement in the tracking plan. Do not
  include automatic or enhanced-measurement events, native/no-push rows, or
  related implementation guidance.
- Read the complete current official table for every selected official event.
  Include required parameters, applicable conditional parameters, and optional
  official parameters supported by a real analysis, business, attribution, or
  implementation need. Do not copy the table mechanically.
- Add custom events and parameters only after the concise official-gap test in
  `references/official-first.md`.
- Record one concrete internal `business_question` for every non-context
  event. It must explain the decision or analysis the event supports; it is
  reasoning traceability, not a visible workbook column.
- Keep each event's parameter list exact. Never inject inherited page, user, or
  journey variables into an event unless they are genuinely sent with it.
- Exhaust stable, observable finite value domains of up to 50 values. Use a
  precise rule for dynamic or larger domains.
- Use exact official definitions and attached conditions for official
  semantics. Use equally precise official-like wording for custom semantics.
  Generic filler is invalid.
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

## Adaptive Workflow

1. Resolve the requested scope, target state, workbook language, supplied
   template, previous plan, dataLayer convention, and available evidence.
2. Ingest all relevant user, business, design, technical, GTM, and historical
   artifacts into the validated analysis context, including evidence roles,
   conflicts, hashes where available, and safe-test boundaries.
3. Explore real public and safely accessible gated journeys in the rendered
   website. Use prioritized sitemap and rendered-link candidates plus
   controlled synthetic interaction recipes. Record incomplete boundaries
   without inventing behavior or treating a sample cap as completeness.
4. Build the business-value, journey-variant, and business-question model
   before choosing events.
5. Resolve selected official events and their parameter tables from current
   official Google documentation. Apply custom-gap judgement only afterward.
6. Specify exact triggers, event-specific parameters, finite values, source
   logic, one combined page-and-user core context, and quoted dataLayer
   pushes.
7. Validate evidence coverage, official fit, scope, requiredness, custom gaps, dataLayer parity,
   GA4 limits, User-ID handling, purchase customer type, event-purpose and
   trigger overlap, plan-wide coherence, and human wording. Review and resolve
   every warning before delivery.
8. Build the atomic delivery through the supplied template or
   `assets/default-tracking-plan.xlsx`. Validate the rendered workbook,
   supplied-template fidelity, per-event schemas, machine contracts, hashes,
   and approval state.
9. When a previous plan exists, also import and compare it, then deliver a
   complete updated plan plus a concise change log. Never deliver an addendum
   as the only current source of truth.

## Commands

Discover public journeys and execute a deliberately specified safe gated flow:

```powershell
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --output discovery.json
python scripts/capture_interactive_journey.py interactive-journey.json --output journey-evidence.json
```

Validate the internal checkpoint, then build the complete default delivery:

```powershell
python scripts/validate_analysis_context.py analysis-context.json --plan plan.json --delivery
python scripts/build_tracking_plan_delivery.py plan.json analysis-context.json --output-dir delivery
```

For a supplied workbook, inspect it once and reuse the hash-bound mapping:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-map.json
python scripts/build_tracking_plan_delivery.py plan.json analysis-context.json --template client-template.xlsx --mapping template-map.json --output-dir delivery
```

Maintain, detect drift, or target a business change:

```powershell
python scripts/import_tracking_plan_workbook.py previous-plan.xlsx --output previous-plan.json
python scripts/import_tracking_plan_workbook.py edited-plan.xlsx --reconcile-visible-edits --output reconciled-plan.json
python scripts/diff_tracking_plans.py previous-plan.json updated-plan.json --output changes.json
python scripts/detect_tracking_plan_drift.py previous-analysis-context.json analysis-context.json updated-plan.json --output drift-report.json
python scripts/analyze_tracking_plan_change_impact.py updated-plan.json change-request.json --analysis-context analysis-context.json --output impact-report.json
```

## Boundaries

Stop after creating, reviewing, adapting, or maintaining the tracking plan.
Do not implement or publish GTM, audit or clean a container, execute Preview or
network recette, make legal decisions, or design another analytics platform.
