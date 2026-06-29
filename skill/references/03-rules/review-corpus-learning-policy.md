# Tracking Plan Corpus Learning Policy

Use this reference when learning from existing tracking plans, client examples, migration files, recette workbooks, or a folder of historical plans. The goal is to improve analyst judgment, not to copy historical schemas.

## Non-Negotiables

- Do not copy client names, URLs, screenshots, IDs, email addresses, phone numbers, bug notes, GTM IDs, GA measurement IDs, Piano site IDs, or raw workbook rows into the generic skill.
- Treat examples as evidence of analyst patterns, not as authoritative documentation.
- Verify current GA4 and Piano official documentation before adopting any event name, parameter, property, SDK payload, or ecommerce structure.
- Promote only reusable, privacy-safe patterns that improve business usefulness, implementation clarity, QA readiness, or workbook readability.

## Platform Boundary

Classify each source before learning from it:

| Source signal | How to use it |
|---|---|
| GA4 events, GA4 ecommerce, GTM/dataLayer for GA4 | Learn event grouping, business scenarios, QA structure, parameter value rules, and official-first implementation patterns. Still verify names and parameters against current GA4 docs. |
| Piano events or properties | Learn Piano-specific event families and property design only for Piano plans. Keep Piano names separate from GA4. |
| Universal Analytics, GAU, GA3, GA360, `eventCategory`, `eventAction`, `eventLabel`, `nonInteraction`, `dimension1`, `metric1`, UA Enhanced Ecommerce | Legacy context only. Extract business journey intent, macro/micro thinking, and QA habits; do not reuse the schema, event names, parameters, dataLayer format, or custom-dimension numbering. |
| Unknown or mixed platform | Separate business actions from implementation fields first. Do not infer GA4 validity from a mixed or legacy workbook. |

Universal Analytics is sunset. In GA4 work, legacy UA fields are forbidden as proposed event schema. If a user provides a UA plan, translate only the business action through current GA4 official events or a justified GA4 custom event.

## What To Learn

Borrow these patterns when they remain generic and official-compatible:

- concise workbook navigation and version history
- GTM/dataLayer protocol rules with official reference links
- event inventories that let analysts scan event names, classifications, triggers, key-event status, and QA status
- parameter dictionaries with display names, value rules, examples, and registration needs
- macro, micro, diagnostic, and context roles before detailed event rows
- event grouping by journey and compatible parameter family
- screenshot and QA evidence registers for future recette
- controlled value normalization, especially lowercase ASCII `snake_case` without accents
- explicit not-tracked decisions for noisy, duplicate, sensitive, or low-value interactions

## What To Reject

Do not promote these patterns into the skill:

- one custom event for every CTA, menu link, card, or banner when one official or consolidated event can cover the need
- GA4 ecommerce events missing `items`, item identity, `transaction_id` for purchase/refund, or `currency` when `value` is sent
- ecommerce parameters placed at the wrong scope, such as `currency` inside `items[]`
- GA4 custom parameters named like UA fields: `eventCategory`, `eventAction`, `eventLabel`, `nonInteraction`, `dimension1`, `metric1`
- hashed emails, phones, customer IDs, loyalty IDs, addresses, account IDs, free text, or sensitive user-entered data
- Piano events copied into GA4 as custom events when GA4 has a native or recommended equivalent
- client-specific screenshots, links, container IDs, design QA comments, or test evidence in a reusable skill package
- dense historical layouts that make the Event Matrix harder for humans to read

## Corpus Review Process

1. Inventory files without copying raw workbook rows into the skill.
2. Classify each file by platform: GA4, Piano, UA legacy, mixed, or unknown.
3. Extract business archetypes, journey types, event families, parameter families, QA patterns, and anti-patterns.
4. Gate every candidate improvement:
   - Is it current-platform official or clearly custom?
   - Does it answer a business or diagnostic need?
   - Can it be made generic without client details?
   - Does it improve readability, implementation, QA, privacy, or scalability?
5. Add reusable patterns to references or scripts.
6. Validate fixtures and scan the skill package for confidential or example-specific residue.

## Scenario Signals Worth Capturing

Common real-world plans often mix these scenarios:

- ecommerce merchandising, product discovery, cart, checkout, purchase, refund, and promotions
- lead generation, quote forms, appointment requests, callbacks, and contact journeys
- search, filtering, sorting, listing refresh, autocomplete, and result selection
- account creation, login, member area entry, and pre-login intent
- support, FAQ, downloads, contact methods, chat, and service locators
- donations, subscriptions, petitions, volunteer or membership journeys
- calculators, simulators, eligibility tools, configurators, and multi-step tools
- content, video, newsletter, share, and publisher engagement

Use these as business-scenario prompts, then map to official GA4 or Piano events according to the requested platform.

## Promotion Criteria

Promote a corpus lesson into the skill only when it is:

- platform-safe: does not mix GA4, Piano, and UA schemas
- official-first: current official docs support the native or recommended event, or the custom reason is explicit
- human-useful: helps analysts, developers, QA, media, or stakeholders understand and use the plan
- scalable: can support future pages, journeys, and recette automation
- privacy-safe: avoids personal, sensitive, and high-cardinality data by design
- maintainable: can be documented once and reused across scenarios
