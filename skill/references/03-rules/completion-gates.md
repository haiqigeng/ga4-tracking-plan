# Completion Gates

Do not deliver until every applicable gate passes.

## Evidence Gate

- Scope, journeys, language decisions, and template mode are explicit.
- Live browser discovery reports `completed`; a `partial` or `blocked` outcome
  is presented as an evidence gap, not complete website coverage.
- Dynamic and gated journeys were attempted with an interactive browser unless
  explicitly excluded.
- Observed, confirmed, inferred, recommended, and unavailable claims are not
  conflated.
- Recommendations carry a structured basis, confirmation requirement, and
  confirmation owner; they do not claim high confidence.
- Finite values presented as exhaustive have value-level browser or client
  evidence. Dynamic values use rules.

## Measurement Gate

- Events form a journey-based measurement model, not a click inventory.
- Official events are preferred when their semantics fit; custom events have a
  business reason and official alternatives.
- Every applicable whole-site branch is included, recommended, or explicitly
  confirmed not applicable. Browser blockage is not an exclusion reason.
- Payment success and failure, order cancellation, return initiation, and
  refund are kept semantically distinct when those journeys apply.
- Manual events do not silently duplicate automatic or enhanced measurement.
- Universal Analytics fields are absent from the proposed schema.

## Official Truth Gate

- Every official definition, trigger basis, parameter row, type, scope,
  requiredness, example, and attached condition resolves to current Google
  documentation.
- A live source receipt covers every official source used, matches the bundled
  catalog signature, has no errors, and is dated on the publication date.
- The resolved JSON, not the draft, is the artifact validated and rendered.
- Official wording is catalog-derived or a faithful localized rendering.
- Website-specific triggers are separate, precise, and actionable.
- Generic filler, tautologies, and placeholders are absent. No prose field is
  accepted merely because it meets a word-count threshold.

## Data Gate

- Unconditional and applicable conditional official parameters are present.
- Optional parameters have a concrete analysis or implementation need.
- Event bindings state requirement, applicable condition, availability, and a
  real source owner when unresolved.
- Ecommerce requiredness follows the current event-specific table. When
  `items` is sent, the example contains item identity and valid item scope.
- Event and item scope are not duplicated where item-level values override the
  event-level value.
- Bindings and the dataLayer example agree exactly. No duplicate stored GA4
  payload or parameter profile exists.
- Manual pushes use top-level `event` plus only `page`, `event_data`,
  `ecommerce`, and `user`; inner keys match final GA4 names.
- Page/core context uses `core_context_before_cmp_ready`; other manual events
  use `after_cmp_ready`.
- PII, consent, privacy, and cardinality concerns are visible and governed.

## Human Output Gate

- Event Matrix is the main working tab and groups related journey events.
- Supporting tabs contain only information useful to analysts and developers.
- Event summaries, triggers, parameter definitions, value rules, availability,
  and owners are concise and implementation-ready.
- Every manual event has one complete developer example; native collection has
  an explicit no-manual-push decision.
- Screenshot Register exists only when screenshots are requested. Captured rows
  resolve to real files; blocked capture has a visible notice.
- Screenshot previews are readable, representative, free of overlay text, and
  use a red rectangle only where an interaction or state needs emphasis.
- Filters, panes, widths, wrapping, and row grouping are usable at normal zoom.

## Template Gate

- The mapping is bound to the inventoried source SHA-256.
- Strict adaptation changes only mapped cell values.
- Unmapped content, sheets, styles, formulas, validations, comments, links,
  images, print setup, protection, and workbook properties remain unchanged.
- Any unsupported workbook feature blocks strict adaptation.
- Structural additions have explicit approval and a passing extension-fidelity
  report.

## Technical Gate

- JSON Schema validation passes.
- Semantic validation returns no errors.
- The renderer consumes the validated JSON without modifying it.
- Workbook generation or strict adaptation succeeds.
- Package, tests, privacy scans, and official-catalog maintenance checks pass.
