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
- Manual events do not silently duplicate automatic or enhanced measurement.
- Universal Analytics fields are absent from the proposed schema.

## Data Gate

- Every parameter has value rules, an example, availability, and an owner.
- Required data dependencies are concrete and do not rely on generic labels.
- PII, sensitive data, cardinality, and consent concerns are highlighted.

## Human Output Gate

- The Event Matrix is the main working tab and groups related journey events.
- Supporting tabs contain only information useful to analysts and developers.
- Screenshot rows map explicitly to events and shared evidence is intentional.
- Workbook filters, frozen panes, widths, wrapping, and previews remain usable.

## Technical Gate

- The JSON matches the current schema.
- The validator returns no errors.
- Workbook and CSV generation succeed.
- Package, privacy, test, and official-catalog metadata checks pass.
