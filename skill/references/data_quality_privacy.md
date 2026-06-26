# Data Quality And Privacy Reference

Use this reference during every tracking-plan review, regardless of scenario.

## Naming And Values

- Event and parameter names use lowercase `snake_case`, start with a letter, and avoid reserved GA4 names and prefixes.
- Controlled analytics values use lowercase ASCII `snake_case`.
- Remove accents and diacritics for controlled values, especially French labels.
- Preserve raw IDs, ISO codes, numeric values, URLs, and safe user-entered values only when analytically required.
- List finite options with ` | ` in human workbooks.

## Data Minimization

- Do not send direct PII: email, phone number, address, full name, customer ID, order notes, account number, policy number, free-text message, or precise personal identifiers.
- Scrub search terms, form errors, URLs, and link destinations for sensitive query parameters.
- Avoid registering high-cardinality values as GA4 custom dimensions unless there is a clear reporting need.
- Prefer stable business metadata over scraped DOM text when values must be controlled.

## Human Plan Review

- Every event must answer a business or diagnostic question.
- Macro conversions must be separated from micro conversions and diagnostic events.
- Ecommerce events must not be mixed with interaction-only parameters unless those custom item/event parameters are intentionally documented.
- Optional parameters should be included only when they improve analysis or QA.
- Events intentionally not tracked should be listed with a reason.

## AI Agent Usage

- Keep generated outputs human-readable first and machine-readable second.
- Use the canonical JSON contract for repeatable generation, QA automation, and future conversion to other formats.
- Never commit client-specific plans, screenshots, test outputs, URLs, or credentials into the generic skill repository.
- Keep examples generic with `example.com`, placeholder IDs, and non-sensitive sample values.

