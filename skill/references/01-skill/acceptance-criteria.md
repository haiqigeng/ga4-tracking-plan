# Acceptance Criteria

A complete GA4 tracking plan must satisfy all applicable criteria.

## Measurement Quality

- Concerned pages, journeys, expected actions, goals, analysis needs, and
  success signals are clear.
- Events and parameters work together around those goals; events from the same
  journey are easy to identify and review.
- Official GA4 events are preferred when their semantics fit. Every custom
  event has a concrete business reason and documented official alternatives.
- Whole-site branches are observed, confirmed, recommended, or explicitly
  confirmed not applicable. Blocked discovery is not an exclusion reason.
- Automatic or enhanced measurement is not duplicated by an ungoverned manual
  event. Universal Analytics schema is absent.

## Evidence Quality

- Website, workbook, and controlled-value languages are decided separately.
  Multilingual plans use English; unknown site language remains unknown.
- Observed, confirmed, inferred, recommended, and unavailable information is
  not conflated.
- Whole-site and dynamic coverage relies on an actual interactive-browser or
  Playwright attempt. Static discovery is supporting evidence only.
- Gated journeys are explored with safe synthetic information unless excluded.
  Unobserved gated behavior is not invented.
- Recommendations record their basis, confirmation requirement, and owner.
- Practical finite values are exhausted only from browser or authoritative
  client evidence; dynamic domains use rules.

## Official Truth

- Official event definitions, trigger bases, parameter rows, requiredness,
  types, scopes, examples, and attached conditions resolve to current Google
  documentation with exact source sections and locators.
- A live publication-date source receipt covers every official plan URL,
  matches the bundled catalog, and contains no errors.
- Official summaries use resolved official wording or a faithful localized
  rendering. Website triggers remain separate and precise.
- Custom wording is equally concrete. Empty, tautological, placeholder, or
  generic tracking prose is absent; arbitrary word counts are not used as a
  proxy for quality.

## Parameter And Data Quality

- Every unconditional official requirement and applicable conditional
  dependency is present. Missing availability is a development dependency, not
  a reason to remove a mandatory parameter.
- Optional parameters have a named analysis or implementation use.
- Event bindings state event-specific requirement, condition, availability,
  and a real data owner when unresolved.
- Ecommerce requiredness and event/item scope follow the event-specific
  official table. When `items` is sent, each item has `item_id` or `item_name`.
- Parameter bindings and the dataLayer example agree. No duplicate GA4 payload
  or ecommerce profile snapshot is stored.
- Manual pushes use top-level `event` and the governed `page`, `event_data`,
  `ecommerce`, and `user` wrappers. Inner keys match final GA4 names.
- Page/core context uses `core_context_before_cmp_ready`; all other manual
  events use `after_cmp_ready`.
- PII, sensitive data, consent, and cardinality risks are highlighted. Opaque
  User-ID and separately governed advertising data are not ordinary event
  parameters.

## Human Delivery

- Event Matrix is the primary working tab and groups related journeys.
- Supporting tabs contain only useful analyst and developer information.
- Every manual event has a complete dataLayer example; native collection has an
  explicit no-manual-push decision.
- Screenshot Register appears only when screenshots are requested. Captured
  evidence resolves to real files; blocked evidence has a visible reason.
- A client template is inspected first and changed only through its SHA-bound
  mapped cells. Unsupported workbook features block strict adaptation.
- The resolved JSON is validated before rendering, and rendering does not
  mutate semantics.

The plan is incomplete if any applicable criterion above fails.
