# Inputs And Outputs

## Inputs

Use available combinations of:

- website URLs, page lists, journeys, screenshots, navigation, or sitemap;
- business goals, expected actions, analysis needs, and success signals;
- existing tracking plans, workbook templates, naming conventions, or
  development specifications;
- page, product, cart, transaction, form, account, content, and consent data;
- GTM, dataLayer, gtag.js, SPA, CMS, ecommerce, or server-side context;
- technical, privacy, legal, regional, and data-availability constraints.

Ask whether a template exists. When information is missing, preserve unknowns
or make a clearly labelled recommendation with a confirmation owner. Do not
invent site language, finite value lists, authenticated capabilities, or
completed browser coverage.

## Outputs

The primary output is a human-readable XLSX tracking plan with:

- a concise Overview;
- shared GTM Protocol rules;
- a Parameter Reference including availability and ownership;
- a journey-grouped Event Matrix;
- complete per-event dataLayer examples and GTM-to-GA4 mappings;
- a Screenshot Register with embedded previews when screenshots are requested,
  or a clear analyst-facing notice when requested capture is blocked.

Structured JSON is the source used to validate and render the human workbook.
The publication artifact includes a live official-source receipt and stores
event-specific parameter bindings, one canonical dataLayer example, and
evidence-bearing finite-value entries. It does not store a duplicate GA4
payload or ecommerce profile. Those machine fields remain subordinate to the
human deliverable.
A long-format CSV can support review and comparison. Internal IDs and reasoning
must not appear in the visible Event Matrix.
