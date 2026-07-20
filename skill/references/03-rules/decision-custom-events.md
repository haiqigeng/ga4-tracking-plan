# Custom Event Decision Matrix

Use this reference before proposing custom events. A custom event is acceptable only when GA4 automatic, enhanced-measurement, recommended, or ecommerce events do not answer the analysis need cleanly.

## Contents

- [Decision Rules](#decision-rules)
- [GA4 Official-First Replacements](#ga4-official-first-replacements)
- [Common Custom Events](#common-custom-events)
- [Navigation Event Choice](#navigation-event-choice)
- [Select Item, View Item, Filter, Sort](#select-item-view-item-filter-sort)
- [Naming And Values](#naming-and-values)
- [Required Custom Rationale](#required-custom-rationale)

## Decision Rules

1. Name the business action first, not the clicked element.
2. Check the platform's official event model.
3. Use the official event when its meaning matches the action.
4. Consolidate repeated same-name interactions with controlled parameters.
5. Create a custom event only when the action has a distinct business or diagnostic meaning.
6. For every parameter, review the chosen event's official fields before adding
   a custom one. A custom parameter must record the official gap, reporting
   purpose, event or item scope, value source, availability, owner,
   registration decision, cardinality, privacy, and persistence when it crosses
   events.
7. Define required parameters, value rules, reporting registration needs, privacy risk, and implementation expectations.

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
| File download or outbound click | Enhanced measurement `file_download` or outbound `click` | Enhanced measurement is unavailable, insufficiently scoped, or a distinct business action requires deliberate manual collection. |
| Video engagement | Enhanced measurement video events for supported embeds | The player is unsupported, non-YouTube, or needs domain-specific media diagnostics. |
| Content item selected | `select_content` | The action is a richer business intent with its own funnel role. |
| Header, menu, submenu, or footer navigation | Follow the approved client convention; otherwise use `header_click`, `menu_click`, `submenu_click`, and `footer_click` for whole-site plans | Use `select_content` when the selected object is actual content, or when a coherent client convention explicitly consolidates navigation there. |

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
| `checkout_error` | Checkout errors explain revenue loss and can be safely categorized. | `journey_step`, `error_type`, `error_code` | Error values include payment details, addresses, or user-entered text. |
| `support_article_feedback` | Helpful/not helpful feedback is used for support deflection. | `content_id`, `content_type`, `feedback_value` | Feedback is free text or not reviewed operationally. |
| `account_access_intent` | Entry to login/member area matters before authentication. | `account_area`, `cta_location`, `login_status` | Successful login occurs; use `login`. |
| `header_click` | Header and utility navigation require direct reporting separate from other surfaces. | `link_name`, `link_url`, `navigation_group`, `link_position` | A coherent client convention uses one consolidated navigation event. |
| `menu_click` | Top-level menu choices need their own reporting and implementation surface. | `link_name`, `link_url`, `navigation_group`, `link_position` | The selected object is a product tile; use `select_item`. |
| `submenu_click` | Second-level or deeper menu choices need to be distinguished from top-level use. | `link_name`, `link_url`, `navigation_group`, `navigation_level` | Menu depth has no analysis value or the client convention consolidates it. |
| `footer_click` | Footer navigation and service links need direct reporting separate from header and menus. | `link_name`, `link_url`, `navigation_group`, `link_position` | Enhanced outbound click is sufficient and footer-specific reporting is unnecessary. |
| `payment_error` | A submitted payment is refused or fails before confirmed purchase. | `journey_step`, `error_type`, `error_code`, `payment_type`, optional `retry_number` | The event is a successful order; use `purchase`. |
| `newsletter_subscribe` | Newsletter success is a distinct permissioned-audience outcome rather than a generic lead. | `form_name`, `lead_source`, optional governed subscription context | The client intentionally consolidates all successful leads under `generate_lead`. |
| `contact_submit` | A completed contact request has separate service or commercial reporting. | `form_name`, `contact_method`, `support_topic`, `lead_source` | The submission is intentionally governed as the same lead KPI as other forms. |
| `catalog_request` | A confirmed catalogue request has distinct acquisition or fulfilment reporting. | `form_name`, `lead_source`, optional `catalog_type` | The request is intentionally consolidated under `generate_lead`. |
| `cancel_order` | The backend confirms cancellation of an existing order before or independently of refund completion. | `transaction_id`, `cancellation_stage`, `cancellation_reason` | Money or items are refunded; also use official `refund` at refund completion. |
| `view_order_history` | Authenticated order-history use is a meaningful self-service KPI and page typing alone is insufficient. | `account_section`, optional `order_count_bucket` | A reliable `page_view` with account page typing already answers the question. |
| `view_order` | Authenticated order-detail use needs separate analysis. | `account_section`, `order_status`, `order_age_bucket` | Typed `page_view` reporting is sufficient. |
| `start_return` | A customer starts a governed return workflow. | `return_scope`, `order_age_bucket`, optional `eligibility_status` | Only completed financial impact matters; use `refund` when completed. |
| `update_profile` | A profile change is a useful self-service outcome. | `profile_field_group` | The change has no actionable analysis need. |
| `update_preferences` | A governed preference change is analytically useful. | `preference_type`, `preference_state` | Consent or privacy governance does not permit collection. |
| `password_reset` | Password recovery completion is needed to measure access resolution. | `method` or a controlled recovery method | Login success alone sufficiently measures recovery. |

## Navigation Event Choice

`select_content` is an official event, but official status does not make it the
best client convention for every navigation surface.

1. Follow a coherent existing client convention.
2. Without one, use surface-level navigation events for whole-site plans.
3. Reuse the same parameter names and value rules across those events.
4. Consolidate all links within each surface; never create one event per link.
5. Reserve `select_content` for editorial cards, guides, articles, FAQs, tools,
   and other content objects whose meaning fits the official event.

## Select Item, View Item, Filter, Sort

- Use `select_item` when a user selects a product or item from a list, carousel, recommendation module, or search result. It describes the click from a list context.
- Use `view_item` when an item or product detail is displayed. It describes item-detail exposure, not list selection.
- Use `view_item_list` when a list of products/items is displayed and item data is available.
- Use `filter_apply` or `sort_apply` for the user's filter/sort choice when that choice is analytically needed.
- After a filter or sort changes a product list, send `view_item_list` for the resulting list if item impressions are available. Do not overload `view_item_list` to carry the filter choice by itself.

## Naming And Values

- Event names: lowercase `snake_case`, semantic, stable, no accents.
- Controlled values: lowercase ASCII `snake_case`; remove French accents; keep official IDs, ISO codes, numeric values, and safe raw terms only when required.
- Avoid generic `button_click`, `cta_click`, `link_click`, `interaction`, `custom_event`, `eventCategory`, `eventAction`, or `eventLabel`. `menu_click` is acceptable only as the governed navigation surface event defined above.

## Required Custom Rationale

For each custom event, document:

- official alternatives considered
- business question or decision supported
- page, component, or journey step
- required parameters and value rules
- custom dimensions or metrics to register
- privacy/cardinality risk
- reproducible trigger, required source data, and expected GA4 payload

For each custom parameter, additionally document:

- the official event table reviewed and the specific gap left by its fields
- the business question and reporting use that justify collection
- event or item scope and event-specific classification
- source path, availability, owner, and any cross-event persistence/reset rule
- custom-dimension or BigQuery-only decision, cardinality, and privacy risk
