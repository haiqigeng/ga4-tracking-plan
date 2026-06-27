# Contributing

Thanks for improving this GA4-first web analyst skill package.

## Scope

Good contributions keep the skill focused on GA4-first tracking-plan creation and review, with Piano Analytics support when explicitly requested. The skill should act like a real web analyst: start from business context and analysis needs, then design a scalable and testable plan.

- measurement brief intake
- GA4 event and parameter design
- official GA4 recommended/ecommerce event checks
- Piano standard, Sales Insights, AV Insights, and Data Model mapping checks when Piano is in scope
- native, recommended, standard, ecommerce, and custom classification
- tracking-plan XLSX examples
- QA notes for analytics implementation
- reusable parameter taxonomies, controlled values, and future QA/recette readiness

Implementation work for GTM, dataLayer, server-side tagging, or browser automation should be proposed separately unless the skill scope changes.

## Pull Requests

- Keep changes small and explain the analytics reason for the change.
- Update `skill/SKILL.md` when the skill behavior changes.
- Move detailed event libraries, scenario guidance, and maintenance rules into `skill/references/` when they would bloat `SKILL.md`.
- Keep examples and fixtures generic, reusable, and non-sensitive.
- Do not commit client secrets, API keys, PII, private tracking plans, or proprietary analytics data.

## Validation

Before opening a pull request, confirm:

- `skill/SKILL.md` exists.
- The skill frontmatter includes `name` and `description`.
- The skill name remains lowercase hyphen-case.
- XLSX examples contain no personal data or confidential client data.
- `python scripts/validate_package.py` passes.
- Official GA4 or Piano claims are backed by official documentation.
