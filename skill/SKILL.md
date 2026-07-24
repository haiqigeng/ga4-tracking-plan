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
- Treat every evidence source according to what it can prove. Distinguish live
  behavior, intended future design, business requirements, current tracking,
  technical data capability, and historical contracts.
- Include only manually implemented measurement in the tracking plan. Do not
  include automatic or enhanced-measurement events, native/no-push rows, or
  related implementation guidance.
- Read the complete current official table for every selected official event.
  Include required parameters, applicable conditional parameters, and optional
  official parameters supported by a real analysis, business, attribution, or
  implementation need. Do not copy the table mechanically.
- Add custom events and parameters only after the concise official-gap test in
  `references/official-first.md`.
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
  dataLayer example. Derive the Event Matrix and Parameter Reference from it.
- Follow an evidenced client dataLayer convention. Use the integrated default
  convention only when no client convention exists. Always quote object keys
  in delivered examples.
- Inventory relevant user information collected or exposed by the website.
  Distinguish dataLayer presence from its destination; do not silently omit a
  field merely because it is not appropriate as an ordinary GA4 parameter.
- Keep evidence, confidence, source conflict, ownership, registration,
  privacy, cardinality, and agent reasoning out of the default visible
  workbook. Surface a concise exception only when it changes implementation.

## Adaptive Workflow

1. Resolve the requested scope, target state, workbook language, supplied
   template, previous plan, dataLayer convention, and available evidence.
2. Ingest all relevant user, business, design, technical, GTM, and historical
   artifacts. Record their evidence roles internally.
3. Explore real public and safely accessible gated journeys in the rendered
   website. Record incomplete boundaries without inventing behavior.
4. Build the journey and business-question model before choosing events.
5. Resolve selected official events and their parameter tables from current
   official Google documentation. Apply custom-gap judgement only afterward.
6. Specify exact triggers, event-specific parameters, finite values, source
   logic, and quoted dataLayer pushes.
7. Validate official fit, scope, requiredness, custom gaps, dataLayer parity,
   and human wording.
8. Render through the supplied template or
   `assets/default-tracking-plan.xlsx`. Validate human readability and template
   fidelity.
9. When a previous plan exists, also import and compare it, then deliver a
   complete updated plan plus a concise change log. Never deliver an addendum
   as the only current source of truth.

## Commands

Validate and render:

```powershell
python scripts/check_official_sources.py plan.json --output official-check.json
python scripts/validate_tracking_plan.py plan.json
python scripts/generate_tracking_plan_workbook.py plan.json --output tracking-plan.xlsx
```

Inspect or adapt a supplied workbook:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-map.json
python scripts/adapt_tracking_plan_workbook.py plan.json client-template.xlsx --mapping template-map.json --output tracking-plan.xlsx
```

Maintain an existing plan:

```powershell
python scripts/import_tracking_plan_workbook.py previous-plan.xlsx --output previous-plan.json
python scripts/diff_tracking_plans.py previous-plan.json updated-plan.json --output changes.json
python scripts/generate_tracking_plan_workbook.py updated-plan.json --changes changes.json --output updated-tracking-plan.xlsx
```

## Boundaries

Stop after creating, reviewing, adapting, or maintaining the tracking plan.
Do not implement or publish GTM, audit or clean a container, execute Preview or
network recette, make legal decisions, or design another analytics platform.
