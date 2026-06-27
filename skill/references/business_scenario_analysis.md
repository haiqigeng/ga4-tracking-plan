# Business Scenario Analysis

Use this reference when the user gives a website, page, user journey, or limited brief and expects practical web analyst judgment, not just event generation.

## Contents

- [Analyst Reasoning Loop](#analyst-reasoning-loop)
- [Page And Journey Signals](#page-and-journey-signals)
- [Scenario Playbook](#scenario-playbook)
- [Custom Event Design Checklist](#custom-event-design-checklist)
- [Parameter Strategy](#parameter-strategy)
- [Event Consolidation](#event-consolidation)
- [Approval Readiness](#approval-readiness)

## Analyst Reasoning Loop

1. Identify the business model and page role from visible context.
2. Translate visible actions into business questions before choosing events.
3. Separate macro conversions, micro conversions, and diagnostic signals.
4. Prefer platform-native events where semantics fit.
5. Use `custom_event_decision_matrix.md` before accepting custom events.
6. Use `parameter_proposition_library.json` to choose reusable parameters and value rules, then verify official parameters in current platform docs.
7. Consolidate repeated interactions into one reusable event with controlled values.
8. Design event families, parameter names, and QA identifiers so the plan can scale to future pages, markets, components, and journey variants.
9. Reject or deprioritize low-signal tracking that creates maintenance cost without analysis value.

When information is missing, continue with assumptions instead of stalling. Flag assumptions in the plan.

## Page And Journey Signals

| Signal | Likely analysis need | Measurement implication |
|---|---|---|
| Homepage with hero, navigation, offers, search | Discovery, merchandising exposure, entry paths | Track page view, promotion exposure/clicks when truly promotional, search, consolidated content/navigation selection. |
| Product listing or search results | Product discovery, filter/search behavior, list performance | Use official ecommerce list events for product lists; custom filter/sort events only when they answer merchandising or UX questions. |
| Product detail page | Product interest, variant choice, add-to-cart intent | Use official product detail and add-to-cart ecommerce events; use custom events for size guide, stock alert, configurator, or financing when analytically useful. |
| Cart and checkout | Funnel progression, friction, revenue quality | Use official ecommerce cart, checkout, shipping, payment, purchase events with required parameters; add diagnostic error events only for actionable checkout issues. |
| Form or quote journey | Lead funnel completion and drop-off | Use form_start/form_submit when sufficient; use generate_lead for valid success; use custom step/error events for multi-step forms and validation friction. |
| Account/login area | Authentication success and account intent | Use login for successful login; custom account_access_intent only for pre-login entry clicks when needed. Never send account identifiers. |
| Content/support page | Content usefulness and support deflection | Use page_view, scroll/download/video when native collection fits; use select_content or custom helpful/contact/chat events when tied to support outcomes. |
| Media player | Consumption and player friction | Use GA4 enhanced measurement for supported YouTube embeds or Piano AV Insights when Piano is in scope; custom media only when native support does not fit. |

## Scenario Playbook

| Business scenario | Macro events | Micro events | Diagnostic events | Usually avoid |
|---|---|---|---|---|
| Retail ecommerce | purchase; refund | view_item_list, select_item, view_item, add_to_cart, view_cart, begin_checkout, add_shipping_info, add_payment_info | filter_apply, sort_apply, checkout_error, stock_alert_signup | One event per banner/link; incomplete ecommerce events missing items. |
| Lead generation | generate_lead; sign_up when account creation is the outcome | form_start, form_submit, begin_quote, form_step_submit, calculator_complete | form_step_view, form_error, contact_intent, chat_start | Sending raw form values, error text, phone/email, or every field focus. |
| Booking/reservation | purchase for paid booking; generate_lead for request/appointment | search, select_item, begin_checkout, appointment_start, appointment_booked | booking_step_view, booking_error, availability_filter_apply | Custom purchase-like events when official ecommerce purchase fits. |
| SaaS/product-led | sign_up, login, purchase/subscribe when paid | pricing_plan_select, tutorial_begin, tutorial_complete, feature_use | upgrade_intent, invite_sent, workspace_created | Tracking every dashboard click with no product KPI. |
| Publisher/content | subscribe/sign_up, share, newsletter success | page_view, scroll, select_content, video events, file_download | newsletter_signup_intent, content_feedback, paywall_view | Duplicate scroll/video tracking when enhanced measurement is enough. |
| Support/service | generate_lead or contact success when applicable | search, select_content, file_download, login, contact_intent, chat_start | support_article_helpful, claim_intent, account_access_intent | Sending claim descriptions, policy numbers, chat text, or free-text queries without scrubbing. |
| Marketplace/classifieds | generate_lead, purchase, contact seller success | search, view_item_list, select_item, view_item, filter_apply, seller_contact_intent | listing_map_interaction, save_listing, alert_signup | Tracking raw addresses or seller/buyer personal identifiers. |
| Finance/insurance | generate_lead, begin_checkout/purchase if online sale is real | begin_quote, calculator_start, calculator_complete, form_step_submit | quote_error, eligibility_error, document_download | Sensitive personal, financial, health, or claim data in analytics. |

## Custom Event Design Checklist

Create a custom event only when all answers are clear:

- What business question does it answer?
- Which decision, report, audience, or optimization action will use it?
- Why does no platform-native event fit?
- Which official automatic, enhanced-measurement, recommended, ecommerce, or platform-standard event was considered and rejected?
- What page, component, or journey step triggers it?
- Which controlled values are needed, and are they finite enough for reporting?
- Which values must stay raw because they are official IDs, numeric amounts, ISO codes, or platform-required fields?
- Does it need registration as a GA4 custom dimension/metric or Piano Data Model property?
- Is cardinality acceptable?
- Is PII impossible or explicitly scrubbed?
- Can QA reproduce the event and verify it in the dataLayer/SDK call and network request?

In machine-readable plans, write this decision into `official_match`. A weak rationale such as "track click" is not enough; use wording like "custom GA4 event: pre-login account-entry intent; official `login` only applies after successful authentication."

## Parameter Strategy

Prefer reusable parameters:

- `page_type`, `page_template`, `journey_name`, `journey_step`
- `component_type`, `component_id`, `component_name`, `cta_location`
- `content_type`, `content_id`, `content_name`
- `form_name`, `form_step`, `validation_status`, `error_type`, `error_code`
- `filter_category`, `filter_value`, `sort_type`, `result_count`
- `login_status`, `customer_type`, `audience_type` when privacy-safe and low-cardinality

Reusable parameters should feel like a durable reporting taxonomy, not one-off labels copied from the current page design. Keep names stable even when the UI wording changes.

Avoid or heavily restrict:

- raw text fields, comments, messages, addresses, claim details, order notes
- email, phone, hashed contact data, customer/account IDs, loyalty numbers
- full URLs with sensitive query parameters
- overly granular labels that change every release

## Event Consolidation

Use one event with controlled values when trigger, meaning, and parameter structure are the same:

- one `select_content` for navigation, cards, and modules with `content_type`, `content_id`, and `cta_location`
- one `filter_apply` for filter categories with `filter_category` and `filter_value`
- one `form_error` for validation/system errors with `error_type`, `error_code`, and `form_step`
- one `contact_intent` for phone/email/store/contact CTA clicks with `contact_method`

Split events when:

- platform-native event names differ
- ecommerce required parameters differ
- success and intent must be separated
- one interaction is a macro conversion and the other is diagnostic
- QA reproduction or data availability is materially different

## Approval Readiness

A tracking plan is ready for human review when:

- the measurement brief is visible
- official events are cited and custom events are justified
- ecommerce blocks use official parameter names and required fields
- every controlled value uses a clear rule
- parameter names and controlled values can support future similar pages or journey variants
- custom definitions or Data Model properties are listed
- risky fields are flagged
- each testable event has a QA case and screenshot placeholder
