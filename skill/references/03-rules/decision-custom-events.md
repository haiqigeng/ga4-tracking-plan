# Custom Event Decision Matrix

Use this reference before proposing custom events. A custom event is acceptable only when official GA4 automatic, enhanced-measurement, recommended, ecommerce, or Piano standard events do not answer the analysis need cleanly.

## Decision Rules

1. Name the business action first, not the clicked element.
2. Check the platform's official event model.
3. Use the official event when its meaning matches the action.
4. Consolidate repeated same-name interactions with controlled parameters.
5. Create a custom event only when the action has a distinct business or diagnostic meaning.
6. Define required parameters, value rules, reporting registration needs, privacy risk, and QA steps.

## GA4 Official-First Replacements

| User action | Prefer this GA4 event | Custom event only when |
|---|---|---|
| Internal search submitted | `search` with `search_term` | Search is a domain-specific locator or tool with additional workflow steps that `search` alone cannot explain. |
| Product list displayed | `view_item_list` | No item data is available and the event is only a generic page/module view. |
| Product selected from a list | `select_item` | The selected element is not a product/item and should use `select_content` or a justified custom event. |
| Product detail displayed | `view_item` | The page is not a real item/product detail and has no item identity. |
| Product added/removed/cart viewed | `add_to_cart`, `remove_from_cart`, `view_cart` | The action is only intent without product/cart data; use a non-ecommerce intent event instead of incomplete ecommerce. |
| Checkout step begins or progresses | `begin_checkout`, `add_shipping_info`, `add_payment_info` | The site has a non-transactional lead/quote funnel; use lead/form/tool events instead. |
| Purchase/refund | `purchase`, `refund` | There is no completed transaction with transaction identifier and item/revenue data. |
| Onsite promotion displayed or selected | `view_promotion`, `select_promotion` | The element is normal navigation/content and not a merchandising/promotion placement. |
| Form starts/submits | `form_start`, `form_submit` when semantics fit | Multi-step lead quality, validation, or funnel diagnostics require custom step/error events. |
| Valid lead submitted | `generate_lead` | The action is only a pre-lead intent or incomplete form step. |
| Login or signup success | `login`, `sign_up` | The event is pre-login entry intent, account-area CTA click, or account failure diagnostic. |
| File download or outbound click | Enhanced measurement `file_download` or outbound `click` | Enhanced measurement is unavailable, insufficiently scoped, or duplicate-safe custom QA is required. |
| Video engagement | Enhanced measurement video events for supported embeds | The player is unsupported, non-YouTube, or needs domain-specific media diagnostics. |
| Content item selected | `select_content` | The action is a richer business intent with its own funnel role. |

## Common Custom Events

Use these as patterns, not standards. Always justify them in `custom_event_acceptance`.

| Custom event | Use when | Key parameters | Avoid when |
|---|---|---|---|
| `filter_apply` | A user applies a filter that changes discovery results and the filter choice is analytically important. | `filter_category`, `filter_value`, `result_count`, `list_id` or `item_list_id` when available | The filter does not affect a meaningful list or cannot be acted on. |
| `sort_apply` | Sort order affects merchandising or UX analysis. | `sort_type`, `result_count`, `list_id` or `item_list_id` | Sort choice is not needed beyond a refreshed `view_item_list`. |
| `form_step_view` | A multi-step form needs drop-off visibility at step display. | `form_name`, `form_step`, `journey_name` | A single-step form is already covered by `form_start` and `form_submit`. |
| `form_step_submit` | A user validates a step before final submission. | `form_name`, `form_step`, `validation_status` | The step is not a meaningful user commitment. |
| `form_error` | Validation or system errors explain funnel friction. | `form_name`, `form_step`, `error_type`, `error_code` | Error text contains user input or sensitive details. |
| `contact_intent` | A phone, email, store, representative, chat, or appointment CTA signals contact intent before a lead exists. | `contact_method`, `cta_location`, `journey_name` | The action is final valid lead submission; use `generate_lead`. |
| `chat_start` | Chat engagement is a support or sales KPI. | `chat_type`, `cta_location`, `support_topic` | Chat transcript or user message would be sent. |
| `stock_alert_signup` | A user asks to be notified about stock availability. | `item_id`, `item_name`, `item_variant`, `stock_status` | The action is a normal `add_to_wishlist` and official ecommerce fits. |
| `store_locator_search` | A locator search has business value beyond generic search. | `locator_type`, `search_scope`, `result_count` | Raw address or precise user location would be sent. |
| `appointment_start` | Appointment scheduling begins but is not yet a valid lead. | `appointment_type`, `cta_location`, `journey_name` | The completed appointment request is the event; use `generate_lead` or a booked custom success. |
| `appointment_booked` | A confirmed appointment is a macro conversion but not a transaction. | `appointment_type`, `booking_channel`, `location_id` when non-personal | A paid booking exists; consider ecommerce `purchase`. |
| `calculator_start` | A simulator/calculator is a distinct business tool. | `tool_name`, `tool_step`, `entry_point` | It is just a generic content page view. |
| `calculator_complete` | Tool completion predicts lead, quote, or eligibility. | `tool_name`, `result_type`, `journey_name` | Result values are sensitive, personal, financial, or health data. |
| `quote_step_submit` | A quote funnel has meaningful intermediate validation. | `quote_type`, `form_step`, `validation_status` | A standard form event answers the need. |
| `checkout_error` | Checkout errors explain revenue loss and can be safely categorized. | `checkout_step`, `error_type`, `error_code` | Error values include payment details, addresses, or user-entered text. |
| `support_article_feedback` | Helpful/not helpful feedback is used for support deflection. | `content_id`, `content_type`, `feedback_value` | Feedback is free text or not reviewed operationally. |
| `account_access_intent` | Entry to login/member area matters before authentication. | `account_area`, `cta_location`, `login_status` | Successful login occurs; use `login`. |

## Select Item, View Item, Filter, Sort

- Use `select_item` when a user selects a product or item from a list, carousel, recommendation module, or search result. It describes the click from a list context.
- Use `view_item` when an item or product detail is displayed. It describes item-detail exposure, not list selection.
- Use `view_item_list` when a list of products/items is displayed and item data is available.
- Use `filter_apply` or `sort_apply` for the user's filter/sort choice when that choice is analytically needed.
- After a filter or sort changes a product list, send `view_item_list` for the resulting list if item impressions are available. Do not overload `view_item_list` to carry the filter choice by itself.

## Naming And Values

- Event names: lowercase `snake_case`, semantic, stable, no accents.
- Controlled values: lowercase ASCII `snake_case`; remove French accents; keep official IDs, ISO codes, numeric values, and safe raw terms only when required.
- Do not use `button_click`, `cta_click`, `menu_click`, `link_click`, `interaction`, `custom_event`, `eventCategory`, `eventAction`, or `eventLabel`.

## Required Custom Rationale

For each custom event, document:

- official alternatives considered
- business question or decision supported
- page, component, or journey step
- required parameters and value rules
- custom dimensions or metrics to register
- privacy/cardinality risk
- QA reproduction and expected network payload
