# Completion Gates

Do not deliver a plan until every applicable gate passes.

## Product Gate

- Scope and journeys are clear or explicitly inferred.
- Events form a coherent measurement model rather than a click inventory.
- Every event answers a business, reporting, optimization, or diagnostic need.
- Excluded interactions and unresolved assumptions are visible.

## GA4 Gate

- Official event and parameter decisions were checked against current Google
  documentation.
- Custom events have documented official alternatives and a concrete reason.
- Ecommerce events use official event-level and item-level structures.
- Payment journeys distinguish confirmed purchase from refused or failed payment.
- `generate_lead` consolidation versus dedicated form-success events is an
  explicit business decision.
- Authenticated customer-space coverage continues beyond login and signup into
  useful self-service outcomes when they were observed or client-confirmed.
- Blocked authenticated areas remain explicit coverage gaps rather than
  speculative implementation events.
- Every event declares public, authentication-flow, or authenticated-area
  access, and no authenticated-area event relies on inferred evidence.
- Confirmed order cancellation and actual refund completion use separate
  semantics.
- Manual events do not silently duplicate automatic or enhanced measurement.
- Universal Analytics fields are absent from the proposed schema.

## Data Gate

- Every parameter has value rules, an example, availability, and an owner.
- Finite controlled values are exhausted when practical, use English across
  multilingual sites, and render with ` | ` separators.
- Required data dependencies are concrete and do not rely on generic labels.
- PII, sensitive data, cardinality, and consent concerns are highlighted.
- Connected-user state is documented once in GTM Protocol; User-ID is mapped
  only through Google tag configuration, and approved user properties reuse
  Parameter Reference definitions.

## Human Output Gate

- The Event Matrix is the main working tab and groups related journey events.
- Supporting tabs contain only information useful to analysts and developers.
- Every event has a complete developer example or an explicit no-manual-push
  decision, with GTM paths mapped to final GA4 parameters.
- Screenshot rows map explicitly to events and shared evidence is intentional.
- Required screenshot capture records an actual Playwright MCP attempt unless
  final images were supplied by the requester.
- A blocked or partial capture has a concrete, analyst-facing notice in both
  Screenshot Register and the delivery reply; no final row remains pending or
  silently skipped.
- Every `captured` or `shared_evidence` row resolves to an actual image file;
  missing files stop workbook generation.
- Repetitive generic events have one representative screenshot; finite events
  cover every inventoried material scenario.
- Screenshot previews are readable at normal zoom, contain no overlay text,
  and never rely on an automatic top crop of a full-page source.
- Workbook filters, frozen panes, widths, wrapping, and previews remain usable.

## Technical Gate

- The JSON matches the current schema.
- The validator returns no errors.
- Workbook and CSV generation succeed.
- Package, privacy, test, and official-catalog metadata checks pass.
