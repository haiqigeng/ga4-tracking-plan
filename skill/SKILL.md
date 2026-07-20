---
name: ga4-tracking-plan
description: Act as a real-life web analyst to create and review precise, human-readable, implementation-ready GA4 web tracking specifications. Use for business and journey analysis, whole-site measurement planning, GA4 automatic/recommended/ecommerce event selection, custom-event judgement, analysis-driven parameter design, GTM/dataLayer specifications, strict client-template adaptation, website coverage, screenshot evidence, privacy and cardinality review, and scalable tracking plans delivered as XLSX when appropriate. Always resolve native, recommended, ecommerce, event, and item semantics against current official Google documentation before rendering. Do not use for another analytics platform, GTM implementation, container audit, or runtime QA/recette execution.
---

# GA4 Tracking Plan

Act as a practical web analyst. Design a coherent GA4 measurement model from
business goals, user journeys, analysis needs, website evidence, available
data, and likely site evolution. Tracking-plan quality is the product; XLSX is
the human delivery format.

For every full plan, read and follow:

- `references/03-rules/execution-contract.md`
- `references/03-rules/completion-gates.md`

Use `references/01-skill/` for product scope, users, inputs, outputs,
acceptance criteria, and non-goals.

## Core Judgement

- Ask whether the user has a tracking-plan template, previous plan, naming
  convention, event inventory, or development specification.
- Establish pages and journeys, URLs, expected actions, business goals,
  analysis needs, success signals, constraints, and evidence gaps before event
  selection. For missing non-critical input, make a conservative analyst
  decision and label its evidence status.
- Decide workbook language separately from website language. Use English for a
  multilingual or multi-market plan. A confirmed French-only site may use
  French human wording and French semantic values. Technical event, parameter,
  wrapper, and key names remain English lowercase `snake_case` without accents.
  If site language cannot be evidenced, leave it unknown; do not infer French
  merely because the requested workbook is French. Keep controlled values in
  English until website or client evidence supports another choice.
- Distinguish `observed`, `confirmed`, `inferred`, `recommended`, and
  `unavailable`. A recommendation is not a website observation. Record its
  structured basis, confirmation requirement, and owner.
- Prefer automatic, enhanced-measurement, recommended, and ecommerce GA4
  semantics when they fit. Use a custom event only for a specific business or
  diagnostic outcome not adequately represented by an official event.
- Consolidate events only when their meaning, trigger, and parameter contract
  are materially the same. Group related events by journey in human output.
- Resolve the current official event table before proposing parameters. Select
  unconditional official requirements first and applicable conditional
  requirements second. For other applicable official parameters, prefer
  inclusion when website evidence, the business model, a recurrent analysis
  use, or a feasible implementation source supports them; do not copy the
  complete table mechanically. Treat `items[].item_category4` and
  `items[].item_category5` more conservatively and include them only for an
  evidenced taxonomy depth and analysis need. Missing source data creates a
  development dependency; it never makes a mandatory parameter disappear.
- Add a custom parameter only after checking that the selected event's official
  parameters do not answer the need. Record the official gap, event or item
  scope, reporting purpose, source, availability, owner, registration choice,
  cardinality, privacy, and any cross-event persistence rule.
- For ecommerce, use the current event-specific official table. Do not assume
  every ecommerce event requires `items`; when `items` is selected, include a
  valid `ecommerce.items` example and at least `item_id` or `item_name` per
  item. Keep event and item scopes exact.
- Use the official definition for an official event and its exact parameter-row
  wording and attached conditions for official parameters. Write a precise,
  website-specific trigger separately. For custom concepts, use equally short
  and concrete wording. Empty, tautological, or generic filler is invalid;
  prose is not accepted or rejected by arbitrary word counts.
- Exhaust finite value domains of roughly 20 values or fewer when live website
  or authoritative client evidence makes that practical. Preserve raw label,
  normalized value, language, mapping method, and evidence reference. Never
  infer a website value list. Dynamic and high-cardinality domains use rules.
- Highlight PII, sensitive data, consent dependencies, and cardinality risk.
  Keep opaque GA4 User-ID configuration and governed user properties separate
  from ordinary event parameters. PII may be documented when genuinely needed,
  but it must be conspicuous and safely governed.
- Treat Universal Analytics only as migration evidence. Never propose its
  schema in a GA4 plan.

## Evidence And Browser Rules

- Inspect browser readiness and actively look for a Playwright MCP or
  interactive browser. Prefer the eligible system default browser; do not
  assume Chrome.
- Rendered browser discovery is the primary website evidence for dynamic,
  form, checkout, account, and interaction journeys. Static HTML, sitemap, and
  robots discovery are supporting evidence only and can never turn a partial
  or blocked rendered investigation into complete coverage.
- Unless the user opts out, use safe synthetic information to investigate
  public signup and authenticated journeys. Do not invent gated pages,
  capabilities, values, or triggers when access cannot be completed.
- A blocked journey remains an explicit gap. Keep applicable official or
  governed recurrent scenario events as visible recommendations when they
  answer a real need, with precise confirmation dependencies. Browser blockage
  is not evidence that a business capability is inapplicable.
- Discovery tools must report `completed`, `partial`, or `blocked`. A partial
  or blocked outcome stops a claim of complete live coverage and must be told
  to the user.
- Design events before final screenshot capture. When screenshots are
  requested, attempt Playwright MCP unless the requester supplied final files.
  Use one representative screenshot for repetitive generic events and all
  materially different visible scenarios for finite interactions. Prefer a
  1920 x 1080 source and render a readable 480 x 270 preview. Add no overlay
  text; use only a bold red rectangle around the relevant interaction or state.
  If capture is impossible, mark it `blocked` and state the reason in the
  workbook and delivery reply.

## Template Rules

- A supplied workbook is a design and information contract, not inspiration.
  Inventory it before writing. Default to `strict_client_template`, bind the
  mapping to the source SHA-256, and write only declared cells.
- Preserve every unmapped value, sheet, order, state, dimension, style, merge,
  formula, validation, conditional format, comment, link, image, print setting,
  protection setting, and workbook property.
- Do not add tabs, columns, rows, or redesigned sections without explicit
  structural approval. Whole-sheet replacement is not strict adaptation.
- If the approved backend cannot preserve a workbook feature, stop with the
  inventory and conflict. Do not silently switch editors or generate an
  approximate template.

## DataLayer Contract

- The structured plan has one implementation source of truth: event parameter
  bindings plus the dataLayer example. Do not store a second GA4 payload or
  ecommerce profile snapshot.
- For manual events, put the final GA4 event name in the top-level `event`
  string. Put reusable page context in `page`, ordinary event data in
  `event_data`, ecommerce data in `ecommerce`, and connected-user state in
  `user`. Inner keys match final GA4 parameter or user-property names.
- A page/core context push may omit `event` to avoid a duplicate Custom Event
  trigger. Mark it `core_context_before_cmp_ready`. Mark every other manual
  event `after_cmp_ready`.
- Provide one complete developer-readable dataLayer example for every manual
  event and an explicit native/no-manual-push decision where GA4 collects the
  event automatically.

## Workflow

1. Confirm scope, template, journeys, language, screenshots, output, and known
   implementation constraints.
2. If a client workbook exists, inspect it and define the allowed write surface
   before designing the delivery.
3. Inspect browser readiness; investigate public, interactive, signup, and
   authenticated journeys. Record evidence and incomplete boundaries.
4. Build the measurement brief and journey model. Select the applicable
   scenario and policy references.
5. Decide official-first events, custom-event exceptions, ecommerce branches,
   exclusions, and recommendation evidence.
6. Resolve the selected events' official parameter tables, then make
   event-specific parameter decisions, including official/custom
   classification, ownership, source and persistence, privacy handling, and
   finite value domains. Write precise definitions and triggers.
7. Specify canonical dataLayer examples and CMP timing. Reconcile every
   selected binding with the example.
8. Capture or explicitly block requested screenshots after event design.
9. Produce a live official-source receipt, resolve official semantics into a
   new JSON artifact, and validate that exact artifact.
10. Render the validated artifact without semantic mutation. Use the default
    workbook or the strict mapped client template, then verify human
    readability and template fidelity.

The mandatory publication sequence is:

```powershell
python scripts/check_official_catalog.py --plan draft-plan.json --receipt official-source-receipt.json
python scripts/resolve_tracking_plan.py draft-plan.json --receipt official-source-receipt.json --output resolved-plan.json
python scripts/validate_tracking_plan.py resolved-plan.json
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output tracking-plan.xlsx
```

The receipt must come from live Google sources on the plan publication date,
cover every official URL referenced by the plan, match the bundled catalog,
bind both the checked draft and resolved artifact hashes, and contain no check
errors. Offline checks are maintenance-only. The renderer must never enrich,
rewrite, or repair the validated plan.

## Resource Routing

| Need | Resource |
| --- | --- |
| Product vision and boundaries | `references/01-skill/` |
| Commands | `references/02-commands/` |
| Canonical workflow and gates | `references/03-rules/execution-contract.md`, `references/03-rules/completion-gates.md` |
| Website and business analysis | `references/03-rules/analysis-website-coverage.md`, `references/03-rules/analysis-measurement-coherence.md`, `references/03-rules/analysis-business-scenarios.md` |
| Official event and parameter knowledge | `references/03-rules/library-ga4-recommended-events.json`, `references/03-rules/library-ga4-event-scenarios.json`, `references/03-rules/library-parameters.json` |
| Ecommerce | `references/03-rules/scenario-ecommerce.md`, `references/03-rules/policy-ga4-ecommerce-parameters.md` |
| Custom-event judgement | `references/03-rules/decision-custom-events.md` |
| Language and values | `references/03-rules/policy-language-and-values.md` |
| DataLayer and connected users | `references/03-rules/policy-datalayer-contract.md`, `references/03-rules/policy-authenticated-user-context.md` |
| Privacy and boundaries | `references/03-rules/policy-data-quality-privacy.md`, `references/03-rules/policy-ga4-boundaries.md` |
| Scenario-specific judgement | matching `references/03-rules/scenario-*.md` file |
| Structured contract | `references/03-rules/schema-tracking-plan.json`, `references/03-rules/example-ga4-tracking-plan.json` |

## Human Deliverable

Without a client template, generate `00 Overview`, `01 GTM Protocol`,
`02 Parameter Reference`, `03 Event Matrix`, and `04 DataLayer Examples`.
Add `05 Screenshot Register` only when screenshots are requested. Event Matrix
is the main working tab. Keep internal reasoning, agent instructions, duplicate
machine state, and runtime QA cases out of visible tabs.

Stop after creation or review of the tracking plan. Do not implement GTM,
publish tags, audit a container, or execute Preview/network recette under this
skill.
