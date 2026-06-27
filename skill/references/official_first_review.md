# Official-First Review

Use this reference when reviewing an existing tracking plan example, translating a legacy implementation plan into GA4, or preparing a plan for future QA/recette usage.

## Contents

- [Review Order](#review-order)
- [Lint Pass](#lint-pass)
- [Comparison Rubric](#comparison-rubric)
- [Template Policy](#template-policy)
- [Human And Recette Split](#human-and-recette-split)
- [Real-Example Lessons](#real-example-lessons)

## Review Order

1. Treat official Google Analytics and Google Tag Manager documentation as the source of truth.
2. Prefer automatic, enhanced measurement, recommended, and recommended ecommerce events before custom events.
3. Treat `gtm.custom_event`, `event_name`, `action`, `label`, UA Enhanced Ecommerce, `eventCategory`, `eventAction`, `eventLabel`, `nonInteraction`, `dimension1`, `metric1`, and vendor wrapper patterns as migration context, not GA4 authority.
4. Keep the skill workbook template stable unless the user explicitly asks to change it.
5. Borrow useful implementation and QA ideas from examples, but do not preserve legacy naming, PII fields, or dense layouts when they weaken the GA4 plan.

## Lint Pass

Run this pass after every independent draft and again after comparing the user-provided example.

| Check | Pass condition | Common correction |
|---|---|---|
| Event name | Official GA4 event is used when semantics match | Replace wrappers with `login`, `sign_up`, `search`, `view_item`, `purchase`, etc. |
| Ecommerce scope | Event-level and item-level parameters are not mixed | Move `currency`, `value`, `transaction_id`, `shipping`, `tax`, and event coupon to event level where applicable |
| Ecommerce scope fallback | Event-level and item-level fallback rules are explicit | Prefer event-level list/promotion values for homogeneous events; use item-level values only when they intentionally override event-level values |
| Item parameters | Item fields use official names and casing | Fix `Item_name` to `item_name`, `Item_category` to `item_category` |
| Custom item parameters | Non-official `items[]` fields are explicitly custom | Classify as `custom_item_parameter`, justify the analysis need, and list item-scoped custom dimension registration when needed |
| Optional ecommerce parameters | Useful optional official parameters are visible rather than silently omitted | Mark rows as `send`, `send_default_quantity`, `event_level_used`, `not_available`, or `not_applicable` |
| Required ecommerce fields | Required or conditionally required fields are present | Require `items`, one of `items[].item_id` or `items[].item_name`, and `transaction_id` for `purchase` or `refund` |
| DataLayer hygiene | Reused ecommerce data cannot leak between events | Add `dataLayer.push({ ecommerce: null })` before ecommerce pushes in GTM/dataLayer examples |
| Legacy UA boundary | UA fields do not appear in the proposed GA4 schema | Extract business intent only, then redesign events and parameters through current GA4 official docs |
| PII | GA4 plan excludes direct and contact-derived PII | Remove email, phone, hashed email, hashed phone, customer IDs, addresses, order notes, and free-text messages |
| Custom events | Each custom event has a business reason no official event covers | Map weak custom click events to official events or list as not tracked |
| Mandatory flags | Required status reflects GA4 rules and business-critical needs | Demote useful-but-optional fields from mandatory to optional |
| QA readiness | Every testable event has stable QA fields | Add `event_id`, `qa_id`, expected dataLayer, expected network payload, DebugView expectation, status |

## Comparison Rubric

Score each example against these dimensions:

| Dimension | What good looks like |
|---|---|
| Official compliance | Event names, parameter names, item scope, and dataLayer examples follow official GA4/GTM setup |
| Analyst usefulness | Events answer business or diagnostic questions without tracking every click |
| Implementation clarity | Developers can identify trigger timing, data source, dataLayer push, and GA4 mapping |
| Privacy safety | No PII or sensitive free text is sent to GA4; data minimization choices are explicit |
| QA and recette readiness | Testers can reproduce, inspect dataLayer, inspect GA4/network payload, and record evidence |
| Information density | Workbook is scannable for analysts; detailed code and evidence stay in protocol or QA sheets |
| Matrix grouping | Ecommerce events are grouped by compatible parameter families, not only by journey |

## Template Policy

Keep the default workbook structure stable:

- `00 Overview`
- `01 GTM Protocol`
- `02 Parameter Reference`
- `03 Event Matrix`
- `04 Screenshot Register`
- `05 QA Cases`

Do not copy example layouts wholesale when they preserve legacy implementation patterns or increase visual density. Adapt only the useful content pattern.

## Human And Recette Split

Keep analyst-facing sheets concise:

- journey
- business question
- event name
- classification
- trigger
- key parameters
- priority
- key event recommendation
- open questions

Keep future recette fields explicit:

- `event_id`
- `qa_id`
- reproduction steps
- expected dataLayer keys and examples
- expected GA4/network event and parameters
- DebugView expectation
- status
- evidence placeholder

## Real-Example Lessons

From ecommerce examples, keep implementation realism such as core dataLayer inventories, event-specific trigger notes, developer code snippets, and test-result comments.

From implementation-template examples, keep cover navigation, compact event inventories, global dataLayer and custom-definition registers, event-level trigger/variable detail, and recette status columns. Fold these into the stable six-sheet workbook instead of creating one tab per event by default.

From brand, healthcare, regulated-product, and professional-resource examples, separate product discovery from transactions. Use `view_item_list`, `select_item`, and `view_item` for product catalog discovery when item data exists, but do not add cart, checkout, purchase, or refund events unless the website actually supports those journeys.

From UA or mixed GAU/GA4 migration examples, keep only business journeys, macro/micro structure, implementation questions, QA habits, and data-availability notes. Discard UA field names, numbered custom dimensions, UA Enhanced Ecommerce commands, and UA property IDs.

Improve recurring issues:

- Translate wrapper events into direct GA4 events when possible.
- Remove hashed email and phone from GA4 planning.
- Reduce mandatory flags to actual GA4 or business requirements.
- Move dense test-result matrices into `05 QA Cases`.
- Add an overview event inventory when the matrix is too detailed for first-pass analyst review.
- Add a custom-definition registration block before the full parameter dictionary.
- Add missing ecommerce events such as `select_item`, `view_promotion`, `select_promotion`, and `refund` where relevant.
- Fix official GA4 casing and typos such as `transaction_id`.
- Move `currency` out of item scope.
- Use `items[].item_variant` before adding custom item fields for color, size, or product options; never label non-official item fields as official GA4 item parameters.
- Clear ecommerce object before pushes.
- Replace generic menu, CTA, and wrapper click events with `select_content`, `contact_intent`, `search`, `generate_lead`, `login`, `sign_up`, or a justified custom event.
- Keep live-search, locator, and autocomplete QA focused on trigger timing so events do not fire for every typed character.
- Prefer enhanced-measurement `video_start`, `video_progress`, `video_complete`, `file_download`, and outbound `click` when they are sufficient, and avoid duplicate custom events.
