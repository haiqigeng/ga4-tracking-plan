# Example Comparison Contract

Use this reference when the user provides a tracking plan, spreadsheet, or implementation template as an example to learn from.

## What To Borrow

- Useful workbook navigation, table of contents, and sheet-purpose summaries.
- Compact event inventories that let analysts scan event name, classification, conversion/key-event status, trigger, and QA status without opening every detail block.
- Separate global references for core dataLayer context, custom definitions, and parameter dictionaries.
- Event detail patterns that clarify trigger, page or component scope, variables, allowed values, implementation notes, and recette status.
- Explicit implementation and QA columns when they help a later recette skill identify what has been built and what has been tested.
- Plain language explanations that help non-technical stakeholders understand why an event exists.

## What To Avoid

- Copying client names, live URLs, emails, sheet links, screenshots, bug reports, or container IDs into the generic skill.
- Treating legacy wrapper names such as `gtm.custom_event`, `action`, or `label` as GA4 event authority.
- Reusing Universal Analytics schema such as `eventCategory`, `eventAction`, `eventLabel`, `nonInteraction`, `dimension1`, `metric1`, UA Enhanced Ecommerce, or UA property IDs. UA is sunset; use these examples only to infer business intent.
- Creating one workbook tab per event by default; it can become hard to navigate on full ecommerce plans. Prefer a compact event inventory plus grouped matrix and QA sheets.
- Mixing website bug reporting, design QA, or consent implementation issues into the tracking-plan template unless the user explicitly asks for that scope.
- Using example status labels, colors, or mandatory flags when they conflict with official GA4 requirements or the skill's QA contract.
- Keeping long code snippets in analyst-facing sheets when a concise dataLayer example or QA expectation is enough.

## Comparison Pass

Evaluate examples against:

| Dimension | Keep if good | Improve if weak |
|---|---|---|
| Navigation | Clear cover, sheet links, sheet purpose | Add a concise overview and avoid excess empty styled canvas |
| Event inventory | Event name, classification, trigger, key event, QA status | Add official GA4 classification and avoid wrapper-first naming |
| Parameter detail | Type, requirement, allowed values, source, explanation | Add scope, official/custom classification, custom definition need, PII/cardinality risk |
| Legacy migration value | Business journeys, macro/micro strategy, QA evidence habits | Remove UA field names, numbered dimensions, legacy ecommerce payloads, and old property IDs |
| Implementation clarity | dataLayer example, source object, trigger timing | Keep code generic and avoid client/container-specific snippets |
| Recette readiness | QA status, comments, expected event payload | Add stable event IDs, QA IDs, expected dataLayer and GA4/network checks |
| Analyst UX | Scannable tables, restrained color, hidden gridlines, wrapped text | Reduce visual density and move evidence/comments to QA sheets |

## Template Evolution Rule

Keep the default six-sheet workbook structure stable unless the user asks for a different deliverable. Improve the template by adding reusable sections inside existing sheets before adding new tabs. The default structure is:

- `00 Overview`
- `01 GTM Protocol`
- `02 Parameter Reference`
- `03 Event Matrix`
- `04 Screenshot Register`
- `05 QA Cases`
