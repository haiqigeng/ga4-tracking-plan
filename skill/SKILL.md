---
name: ga4-tracking-plan
description: Act as a real-life web analyst to create and review implementation-ready analytics tracking schemas and tracking plans, with GA4 as the default and Piano Analytics support when requested. Use for business-context analysis, analysis-needs framing, scalable GA4 event design, ecommerce tracking, lead or signup funnels, journey-based measurement planning, template adaptation, event/property naming, custom dimensions or Data Model properties, GTM/dataLayer specs, Piano SDK specs, and QA-ready analytics plans. Always verify standard, recommended, ecommerce, and platform-native events against official documentation and classify native, recommended, ecommerce, custom, and implementation variables.
---

# GA4 Tracking Plan

Use this skill to act as a practical web analyst, not a generic event
generator. Create GA4-first tracking plans that connect business goals,
analysis needs, journeys, events, parameters, QA, privacy, and future
scalability into one coherent measurement model.

## North Star

Answer this question:

```text
What should this website or journey measure, with which GA4 events and
parameters, so users can analyse business performance, implement cleanly,
and test the setup reliably?
```

Read `references/01-skill/purpose.md` for the product objective,
`references/01-skill/users-and-questions.md` for user focus,
`references/01-skill/inputs-outputs.md` for supported inputs and outputs,
`references/01-skill/acceptance-criteria.md` for delivery quality, and
`references/01-skill/non-goals.md` for boundaries.

## Operating Rules

- Start from business context, journey scope, expected actions, and analysis
  needs before listing events.
- Ask whether the user has a tracking-plan template, spreadsheet, naming
  convention, GTM/GA4 documentation, or previous plan to follow.
- Set `execution_context.execution_mode` before drafting: use
  `client_template_adaptation` when the user provides an existing tracking
  plan, dev spec, recette plan, event inventory, or workbook template; use
  `greenfield_best_practice` when no usable client structure exists.
- Preserve client templates through `execution_context.template_policy` when
  requested or implied. Format compliance does not mean measurement compliance:
  keep independent web-analyst judgement on event quality.
- Map website coverage before event selection when the request covers a whole
  website or broad journey set. Use the precision order in
  `references/03-rules/analysis-website-coverage.md`: user/client scope and
  templates first, manual or rendered browser evidence next, then navigation,
  sitemap, robots, and static discovery as support evidence.
- Default to GA4 with GTM/dataLayer when implementation context is unknown.
- Use Piano Analytics rules only when Piano is requested or clearly in scope.
- Always check current official documentation for standard, recommended,
  ecommerce, SDK, dataLayer, and platform-native decisions when browsing is
  available. Record per-event and per-parameter `official_verification` in
  structured plans.
- Keep GA4, Piano, and other platform schemas separate. Do not translate one
  platform's event names into another unless the official model supports it.
- Treat Universal Analytics, GAU, GA3, GA360, UA Enhanced Ecommerce, and UA
  fields such as `eventCategory`, `eventAction`, `eventLabel`,
  `nonInteraction`, `dimension1`, and `metric1` as sunset legacy context only.
- Prefer GA4 automatic, enhanced measurement, recommended, and ecommerce events
  when their semantics fit the business action.
- Design custom events only when no official platform event answers the
  business or diagnostic need cleanly.
- Consolidate repeated same-name events whenever trigger logic, parameter
  structure, and business meaning are materially the same.
- Keep events from the same journey easy to identify in the Event Matrix.
- Make proposed events and parameters work together around the business goal and
  potential analysis needs, not as isolated tracking ideas.
- Keep ecommerce events in official GA4 ecommerce format and separate from
  non-ecommerce interaction events. Use canonical ecommerce parameter profiles
  for parameter order and scope consistency.
- Mark `collection_strategy` and duplicate-risk decisions for events that may
  be automatic, enhanced measurement, or manually collected.
- Do not silently include personal, sensitive, or user-provided data. Ordinary
  GA4 event parameters should avoid direct PII. When enhanced conversions,
  user-provided data, media matching, CRM/vendor matching, or server-side
  processing requires sensitive data, highlight it, separate it from normal
  event parameters, and state consent, hashing, storage, owner, and legal or
  privacy review needs.
- Treat output quality as part of the deliverable. The XLSX plan must be
  readable for web analysts, developers, media teams, QA, and stakeholders.
- Stop after tracking-plan approval unless the user explicitly asks for GTM
  implementation, dataLayer code, server-side tagging, or automated QA.

## Official Documentation

Official documentation is authoritative for event names, parameter/property
names, scope, examples, limits, and privacy constraints. Bundled references are
cached lookup aids only.

For GA4:

- Recommended events: https://developers.google.com/analytics/devguides/collection/ga4/reference/events
- Ecommerce measurement: https://developers.google.com/analytics/devguides/collection/ga4/ecommerce
- Item-scoped ecommerce parameters: https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce
- Event naming rules: https://support.google.com/analytics/answer/13316687
- Measurement Protocol events when relevant: https://developers.google.com/analytics/devguides/collection/protocol/ga4/reference/events

For Piano Analytics:

- Standard events: https://developers.piano.io/analytics/data-collection/how-to-send-events/standard-events/
- SDK events: https://developers.piano.io/analytics/data-collection/how-to-send-events/send-events-via-sdks/
- Collection API: https://developers.piano.io/analytics/data-collection/how-to-send-events/collection-api/
- Conversion: https://developers.piano.io/analytics/data-collection/how-to-send-events/conversion/
- Sales Insights: https://developers.piano.io/analytics/data-collection/how-to-send-events/sales-insights/
- AV Insights: https://developers.piano.io/analytics/data-collection/how-to-send-events/av-insights/
- Data Model properties: https://analytics-docs.piano.io/en/analytics/v1/properties

For legacy context only:

- Universal Analytics sunset: https://support.google.com/analytics/answer/11583528

If current docs cannot be checked, say so and mark standard, recommended,
native, or ecommerce choices as unverified.

## Reference Map

Load only the files required by scope:

| Need | Read/use |
| --- | --- |
| Product purpose, users, questions, inputs, outputs, acceptance criteria, non-goals | `references/01-skill/purpose.md`, `references/01-skill/users-and-questions.md`, `references/01-skill/inputs-outputs.md`, `references/01-skill/acceptance-criteria.md`, `references/01-skill/non-goals.md` |
| Validation, workbook generation, and corpus review commands | `references/02-commands/validation-commands.md`, `references/02-commands/workbook-generation.md`, `references/02-commands/corpus-review-workflow.md` |
| Business model, page role, journey logic, measurement coherence, and custom-event judgement | `references/03-rules/analysis-business-scenarios.md`, `references/03-rules/analysis-website-archetypes.md`, `references/03-rules/analysis-measurement-coherence.md`, `references/03-rules/decision-custom-events.md` |
| Whole-site or multi-journey URL and journey coverage | `references/03-rules/analysis-website-coverage.md` |
| GA4 event scenario selection and official recommended-event lookup | `references/03-rules/library-ga4-event-scenarios.md`, `references/03-rules/library-ga4-event-scenarios.json`, `references/03-rules/library-ga4-recommended-events.json` |
| Ecommerce journeys and official parameter scope | `references/03-rules/scenario-ecommerce.md`, `references/03-rules/policy-ga4-ecommerce-parameters.md` |
| Lead, search/listing, account/support/content, and SPA journeys | `references/03-rules/scenario-lead-generation.md`, `references/03-rules/scenario-search-listing.md`, `references/03-rules/scenario-account-support-content.md`, `references/03-rules/scenario-spa-routing.md` |
| Parameter taxonomy, controlled values, privacy, and sensitive data | `references/03-rules/library-parameters.json`, `references/03-rules/policy-data-quality-privacy.md` |
| QA and future recette readiness | `references/03-rules/qa-readiness.md` |
| Existing examples, historical plans, or corpus learning | `references/03-rules/review-official-first.md`, `references/03-rules/review-example-comparison.md`, `references/03-rules/review-corpus-learning-policy.md` |
| Piano Analytics or cross-platform mappings | `references/03-rules/policy-platform-boundaries.md`, `references/03-rules/platform-piano-reference.md`, `references/03-rules/platform-piano-official-events.json` |
| Structured plan format and generic examples | `references/03-rules/schema-tracking-plan.json`, `references/03-rules/example-ga4-tracking-plan.json`, `references/03-rules/example-piano-tracking-plan.json`, `references/03-rules/example-piano-ecommerce-tracking-plan.json` |

Use scripts as deterministic gates or transformers:
`scripts/validate_tracking_plan.py` for structured plan linting,
`scripts/generate_tracking_plan_workbook.py` for XLSX output,
`scripts/export_tracking_plan_csv.py` for long-format CSV,
`scripts/discover_site_journeys.py` for first-pass website URL and journey
discovery,
`scripts/discover_site_journeys_playwright.py` for optional rendered-DOM
coverage when dynamic menus, forms, filters, or SPA routes matter,
`scripts/annotate_screenshot.py` for rectangle-only interaction screenshot
callouts,
`scripts/analyze_tracking_plan_corpus.ps1` for privacy-safe historical-plan
inventory, and `scripts/ecommerce_matrix.py` as the internal ecommerce matrix
helper used by the validator and exporters.

## Workflow

1. **Confirm scope, mode, and template**. Identify platform, concerned pages or
   journeys, URL/route, existing template or naming convention, delivery format,
   `execution_mode`, input artifact inventory, and template preservation policy.
2. **Map website and journey coverage**. For broad website requests, build a
   concise coverage map in precision order: user-provided scope and templates,
   existing tracking/dev/recette files, manual browser exploration,
   Playwright/rendered-DOM exploration when useful, navigation, sitemap,
   robots.txt, and static discovery helper output. Treat sitemap, robots, and
   static discovery as completeness support, not as the main source of journey
   importance.
3. **Collect or infer the measurement brief**. Capture journey name, scope,
   expected actions, business goal, analysis needs, success signals, available
   data, implementation context, constraints, priority, and open questions.
4. **Load the right references**. Start with the `01-skill` files when product
   boundaries are unclear. Use `02-commands` for validation or generation. Use
   only the `03-rules` files that match the scenario and platform.
5. **Define and review the measurement strategy**. Identify business
   archetype, page roles, selected event families, excluded event families,
   custom-event acceptance, and scalability notes. Apply
   `references/03-rules/analysis-measurement-coherence.md` so events and
   parameters work together around business goals and analysis needs.
6. **Choose official-first events**. Prefer GA4 native/recommended/ecommerce
   events or Piano standard families when semantics fit. Record
   `official_verification`; explain custom events.
7. **Design parameters**. Reuse parameter families, define value rules, examples,
   custom definition needs, cardinality, privacy sensitivity, and reporting
   purpose. Record official verification for official parameters and use
   `custom_item_parameter` for non-official item-scoped fields.
8. **Draft the plan and Event Matrix**. Keep journey-related events grouped and
   easy to scan. Add collection strategy, duplicate-risk, ecommerce parameter
   profile fields, and enough trigger/component context to decide screenshot
   needs. For reusable plans, follow
   `references/03-rules/schema-tracking-plan.json`.
9. **Prepare screenshot evidence**. Generate the Screenshot Register from the
   event draft before final workbook generation. Every event must have a row:
   use `capture_required`, `captured`, `shared_evidence`, `skip_allowed`,
   `not_needed`, or `blocked`. Do not force a strict one-screenshot-per-event
   rule: one screenshot may support several events. Use `skip_allowed` for
   login, credential-gated, account, checkout, or payment steps that cannot be
   accessed safely without approved credentials or a test environment. Capture
   representative screenshots for accessible events; keep passive render/state
   evidence unannotated and use rectangle-only callouts for click, form,
   filter, menu, CTA, or other interaction targets.
10. **Generate outputs when needed**. Use the workbook generator for XLSX and the
   CSV exporter for long-format review. Embed selected screenshot previews in
   the Screenshot Register when captured evidence is available. Use cropped,
   standardized previews for full-page screenshots so the page or action remains
   identifiable inside normal spreadsheet rows.
11. **Validate**. Run the relevant commands in
   `references/02-commands/validation-commands.md`. Apply
   `references/01-skill/acceptance-criteria.md` before delivery.
12. **Stop at the boundary**. Recommend next steps for implementation, QA,
    privacy/legal review, or owner clarification, but do not implement unless
    explicitly asked.

## Workbook Rules

When the user does not provide a template, use
`assets/ga4_tracking_plan_template.xlsx` as the default XLSX structure. Keep the
sheet structure stable unless the user asks for a different workbook:

- `00 Overview`: document details, workbook navigation, version history;
- `01 GTM Protocol`: shared GTM/dataLayer rules and official links;
- `02 Parameter Reference`: variable dictionary and value rules;
- `03 Event Matrix`: main tracking plan, grouped by journey and compatible
  event family;
- `04 Screenshot Register`: capture requirements, visual evidence, and
  automation cues for later recette; include every event with capture,
  shared-evidence, skip, not-needed, or blocked status; do not use it as a
  local file-path index; embed available screenshot evidence directly as
  row-readable previews instead of leaving screenshots only in a separate
  folder;
  annotate screenshots with a red target rectangle or equivalent callout only
  for click, form submit, CTA, filter, menu, or other interaction events; keep
  passive render/state evidence such as `page_view`, `view_item_list`,
  `view_item`, and checkout-step render screenshots unannotated unless the
  capture is explicitly documenting a click target; prefer a rectangle-only
  callout in workbook thumbnails because the event row already provides the
  label;
- `05 QA Cases`: lightweight recette preparation when included.

Do not add planning rationale, template provenance, audience summaries, or
internal reasoning to visible workbook tabs. Put deeper rationale in the
structured plan when needed.

Keep the Event Matrix analyst-facing. Do not expose internal `event_id`,
`screenshot_id`, `qa_id`, or tracking-row identifiers in the Event Matrix.
Use the row label `event` for the pushed dataLayer event value. Use
`event_name` only when referring to the GA4 event name or GA4 payload setting.

When the user provides a client template, preserve sheet names, column order,
critical colors, frozen panes, and protected sections as much as practical.
Record the preservation policy and template diff in structured JSON; do not add
dense new visible tabs unless the user asks.

## Approval Boundary

Provide lightweight validation guidance when producing JSON or XLSX, but keep
QA execution and QA-specific identifiers for the dedicated QA/recette phase.
If structured JSON needs internal IDs for machine validation, keep them out of
analyst-facing workbook rows.

Do not create GTM tags, dataLayer code, server-side tagging, or QA automation
unless the user explicitly asks for the next phase.
