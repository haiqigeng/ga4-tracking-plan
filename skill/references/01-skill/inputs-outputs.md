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

Ask whether a template exists. When information is missing, make conservative
assumptions, label them as inferred, and state what remains to confirm.

## Outputs

The primary output is a human-readable XLSX tracking plan with:

- a concise Overview;
- shared GTM Protocol rules;
- a Parameter Reference including availability and ownership;
- a journey-grouped Event Matrix;
- complete per-event dataLayer examples and GTM-to-GA4 mappings;
- an explicit Screenshot Register with embedded previews when captured, or a
  clear analyst-facing notice when capture is blocked or excluded.

Structured JSON is the source used to validate and render the human workbook.
A long-format CSV can support review and comparison. Internal IDs and reasoning
must not appear in the visible Event Matrix.
