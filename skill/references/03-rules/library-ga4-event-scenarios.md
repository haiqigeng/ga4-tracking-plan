# GA4 Event Scenario Library

Use this reference when creating a GA4 tracking plan from a website, page, or journey.

Decision order:

1. Use automatic or enhanced-measurement events when they already answer the need.
2. Use GA4 recommended events when the semantics match.
3. Use ecommerce recommended events for product, cart, checkout, purchase, refund, and promotion flows.
4. Use custom events only when the interaction is business-specific and no official event fits.
5. Keep custom events stable, low-noise, and tied to a business question.
6. Consolidate repeated same-name events when possible and normalize controlled values to lowercase ASCII snake_case with accents removed.

## Contents

- [Standard Web Events](#standard-web-events)
- [Official Recommended Events](#official-recommended-events)
- [Scenario Playbooks](#scenario-playbooks)
- [Typical Custom Events](#typical-custom-events)
- [DataLayer Patterns](#datalayer-patterns)
- [Sources](#sources)

## Standard Web Events

| Event | Group | Scenario | Parameters | Implementation note |
|---|---|---|---|---|
| `page_view` | automatic / enhanced measurement | page view, SPA route change | page_location, page_referrer, page_title, engagement_time_msec | Usually automatic. Manually control only when SPA/infinite-scroll behavior requires it. |
| `first_visit` | automatic | new user acquisition | client_id, ga_session_id, ga_session_number, page_location, page_referrer, page_title | Automatic; do not implement manually. |
| `session_start` | automatic | session analysis | client_id, ga_session_id, ga_session_number, page_location, page_referrer, page_title | Automatic; do not implement manually. |
| `user_engagement` | automatic | engagement time | engagement_time_msec | Automatic; do not implement manually. |
| `scroll` | enhanced measurement | content engagement | engagement_time_msec | Enhanced measurement. Custom scroll_depth event only if 25/50/75 thresholds are needed. |
| `click` | enhanced measurement | outbound link click | link_classes, link_domain, link_id, link_url, outbound | Enhanced measurement. Avoid duplicating with custom outbound_click unless needed. |
| `view_search_results` | enhanced measurement | search results page | search_term, q_<additional key> | Enhanced measurement. Use recommended search for explicit submitted-search tracking. |
| `video_start` | enhanced measurement | YouTube embedded video | video_current_time, video_duration, video_percent, video_provider, video_title, video_url, visible | Enhanced measurement when YouTube JS API support exists. |
| `video_progress` | enhanced measurement | YouTube embedded video | video_current_time, video_duration, video_percent, video_provider, video_title, video_url, visible | Enhanced measurement when YouTube JS API support exists. |
| `video_complete` | enhanced measurement | YouTube embedded video | video_current_time, video_duration, video_percent, video_provider, video_title, video_url, visible | Enhanced measurement when YouTube JS API support exists. |
| `file_download` | enhanced measurement | downloadable file click | file_extension, file_name, link_classes, link_id, link_text, link_url | Enhanced measurement. Custom file events only for gated downloads or special classifications. |
| `form_start` | enhanced measurement | form engagement | form_id, form_name, form_destination | Enhanced measurement. Custom form_step events when multi-step funnel detail is required. |
| `form_submit` | enhanced measurement | form submission | form_id, form_name, form_destination, form_submit_text | Enhanced measurement. Use generate_lead for validated lead success. |

## Official Recommended Events

### For all properties

| Event | Main parameters | Use |
|---|---|---|
| `earn_virtual_currency` | virtual_currency_name, value | This event measures when a user is awarded virtual currency in a game. Log this along with spend_virtual_currency to better understand your virtual economy. |
| `join_group` | group_id | Log this event when a user joins a group such as a guild, team, or family. Use this event to analyze how popular certain groups or social features are. |
| `login` | method | Send this event to signify that a user has logged in to your website or app. |
| `search` | search_term | Log this event to indicate when the user has performed a search. You can use this event to identify what users are searching for on your website or app. For example, you could send this event when a user views a search results page after performing a search. |
| `select_content` | content_type, content_id | This event signifies that a user has selected some content of a certain type. This event can help you identify popular content and categories of content on your website or app. |
| `share` | method, content_type, item_id | Use this event when a user has shared content. |
| `sign_up` | method | This event indicates that a user has signed up for an account. Use this event to understand the different behaviors of logged in and logged out users. |
| `spend_virtual_currency` | value, virtual_currency_name, item_name | This event measures the sale of virtual goods in your app and helps you identify which virtual goods are the most popular. |
| `tutorial_begin` | - | This event signifies the start of the on-boarding process. Use this in a funnel with tutorial_complete to understand how many users complete the tutorial. |
| `tutorial_complete` | - | This event signifies the user's completion of your on-boarding process. Use this in a funnel with tutorial_begin to understand how many users complete the tutorial. |

### Online sales

| Event | Main parameters | Use |
|---|---|---|
| `add_payment_info` | currency, value, coupon, payment_type, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies a user has submitted their payment information in an ecommerce checkout process. |
| `add_shipping_info` | currency, value, coupon, shipping_tier, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies a user has submitted their shipping information in an ecommerce checkout process. |
| `add_to_cart` | currency, value, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies that an item was added to a cart for purchase. |
| `add_to_wishlist` | currency, value, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | The event signifies that an item was added to a wishlist. Use this event to identify popular gift items in your app. |
| `begin_checkout` | currency, value, coupon, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies that a user has begun a checkout. |
| `purchase` | currency, value, customer_type, transaction_id, coupon, shipping, tax, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies when one or more items is purchased by a user. |
| `refund` | currency, transaction_id, value, coupon, shipping, tax, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies when one or more items is refunded to a user. |
| `remove_from_cart` | currency, value, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies that an item was removed from a cart. |
| `select_item` | item_list_id, item_list_name, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies an item was selected from a list. |
| `select_promotion` | creative_name, creative_slot, promotion_id, promotion_name, items, item_id, item_name, affiliation, coupon, creative_name, creative_slot, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, promotion_id, promotion_name, quantity | This event signifies a promotion was selected from a list. |
| `view_cart` | currency, value, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies that a user viewed their cart. |
| `view_item` | currency, value, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | This event signifies that some content was shown to the user. Use this event to discover the most popular items viewed. |
| `view_item_list` | currency, item_list_id, item_list_name, items, item_id, item_name, affiliation, coupon, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, quantity | Log this event when the user has been presented with a list of items of a certain category. |
| `view_promotion` | creative_name, creative_slot, promotion_id, promotion_name, items, item_id, item_name, affiliation, coupon, creative_name, creative_slot, discount, index, item_brand, item_category, item_category2, item_category3, item_category4, item_category5, item_list_id, item_list_name, item_variant, location_id, price, promotion_id, promotion_name, quantity | This event signifies a promotion was viewed from a list. |

### Games

| Event | Main parameters | Use |
|---|---|---|
| `level_end` | level_name, success | This event signifies that a player has reached the end of a level in a game. |
| `level_start` | level_name | This event signifies that a player has started a level in a game. |
| `level_up` | level, character | This event signifies that a player has leveled up in a game. Use it to gauge the level distribution of your user base and identify levels that are difficult to complete. |
| `post_score` | score, level, character | Send this event when the user posts a score. Use this event to understand how users are performing in your game and correlate high scores with audiences or behaviors. |
| `unlock_achievement` | achievement_id | Log this event when the user has unlocked an achievement. This event can help you understand how users are experiencing your game. |

### Lead generation

| Event | Main parameters | Use |
|---|---|---|
| `close_convert_lead` | currency, value | Log this event when a qualified lead is successfully converted into a customer. This typically signifies the end of the lead nurturing process, such as when a contract is signed, a paid subscription starts, or a final sale is completed. |
| `close_unconvert_lead` | currency, value, unconvert_lead_reason | This event measures when a user is marked as not becoming a converted lead, along with the reason. |
| `disqualify_lead` | currency, value, disqualified_lead_reason | This event measures when a user is marked as disqualified to become a lead, along with the reason for the disqualification. |
| `generate_lead` | currency, value, lead_source | This event measures when a lead has been generated (for example, through a form). Log this to understand the effectiveness of your marketing campaigns and how many customers re-engage with your business after remarketing to the customers. |
| `qualify_lead` | currency, value | This event measures when a user is marked as meeting the criteria to become a qualified lead. |
| `working_lead` | currency, value, lead_status | This event measures when a user contacts or is contacted by a representative. |

## Scenario Playbooks

| Scenario | Official events | Typical custom events | Primary parameters | Notes |
|---|---|---|---|---|
| Content / publisher / blog | page_view, scroll, select_content, share, file_download, video_start, video_progress, video_complete | newsletter_signup_intent, accordion_open, modal_open | page_data.template, content_type, content_id, content_name, link_url, video_title | Prefer enhanced measurement for scroll/video/download when it is sufficient; use select_content for content card/article selections. |
| Lead generation | page_view, search, form_start, form_submit, generate_lead, qualify_lead, disqualify_lead, working_lead, close_convert_lead, close_unconvert_lead | begin_quote, form_step_view, form_step_submit, form_error, contact_intent, calculator_start, calculator_complete | lead_source, form_name, form_step, product_type, quote_entry_point, cta_location | Use generate_lead only after a valid submission or qualified lead action, not on CTA click. |
| Retail ecommerce | view_item_list, select_item, view_item, add_to_wishlist, add_to_cart, remove_from_cart, view_cart, begin_checkout, add_shipping_info, add_payment_info, purchase, refund | filter_apply, sort_apply, size_guide_open, stock_alert_signup | currency, value, transaction_id, items, items[].item_id, items[].item_name, items[].item_category, items[].price, items[].quantity | Use official ecommerce event names and items array. Clear ecommerce object before ecommerce pushes when using GTM/dataLayer. |
| Internal promotions / offer cards | view_promotion, select_promotion | promotion_expand, offer_terms_open | promotion_id, promotion_name, creative_name, creative_slot, items, items[].item_id, items[].item_name | Use promotion events only for real promotions/offers, not every generic content card. |
| SaaS / product-led growth | sign_up, login, tutorial_begin, tutorial_complete, join_group, share, select_content, purchase | feature_use, pricing_plan_select, upgrade_intent, workspace_created | method, group_id, plan_id, feature_name, user_role | Use login/sign_up for successful actions; use intent custom events for pre-auth clicks or plan exploration. |
| Search, listings, and filters | search, view_search_results, view_item_list, select_item, select_content | filter_apply, sort_apply, listing_map_interaction | search_term, result_count, filter_category, filter_value, sort_type, item_list_id | Use search for submitted queries and view_search_results when results page detection via query parameter is enough. |
| Booking / reservation / travel | search, view_item_list, select_item, view_item, begin_checkout, add_payment_info, purchase, generate_lead | booking_start, booking_step_view, booking_step_submit, appointment_booked | destination, dates, guests_count, item_id, item_name, value, currency, transaction_id | Model paid bookings as ecommerce when money is transacted; model appointment requests as leads. |
| Support / customer service | page_view, search, select_content, file_download, login | contact_intent, chat_start, claim_intent, account_access_intent, support_article_helpful | support_topic, contact_method, entry_point, content_id, content_name | Do not send claim descriptions, policy numbers, email, phone, or chat text to GA4. |
| Education / courses | view_item_list, select_item, view_item, sign_up, begin_checkout, purchase, tutorial_begin, tutorial_complete | course_progress, lesson_complete, certificate_download | course_id, course_name, content_type, progress_percent, value, currency | Paid enrollment can use ecommerce. Learning engagement may need custom events. |
| Games | earn_virtual_currency, spend_virtual_currency, level_start, level_end, level_up, post_score, unlock_achievement, tutorial_begin, tutorial_complete | mission_start, mission_complete, item_equipped | level_name, success, score, character, virtual_currency_name, value, achievement_id | Use official game recommended events wherever possible. |

## Typical Custom Events

| Event | Scenario | Use when | Prefer official if | Parameters |
|---|---|---|---|---|
| `begin_quote` | insurance, banking, telco, services quote funnels | User starts a quote flow but no lead has been generated yet. | Use generate_lead after a successful lead/quote submission. | quote_type, product_type, quote_entry_point, cta_location, cta_text |
| `form_step_view` | multi-step lead, signup, booking, checkout-like forms | A form step is displayed and enhanced measurement is too coarse. | Use form_start/form_submit when only generic form engagement is needed. | form_name, form_step, form_step_name, page_location |
| `form_step_submit` | multi-step forms and funnels | A step is completed before final submission. | Use generate_lead/sign_up/purchase when the final business outcome occurs. | form_name, form_step, form_step_name, validation_status |
| `form_error` | forms, checkout, quote funnels | User sees a validation or system error that affects conversion. | No direct GA4 recommended event fits. Avoid raw error text if it may contain PII. | form_name, form_step, error_type, field_name, error_code |
| `filter_apply` | listing pages, search results, catalogs, real estate, jobs | A filter materially changes the displayed results. | Use view_search_results/search if the interaction is a search query. | filter_category, filter_value, result_count, listing_type |
| `sort_apply` | listing pages, catalogs, search results | User changes result ordering. | No direct recommended event fits. | sort_type, previous_sort_type, result_count, listing_type |
| `contact_intent` | lead generation, support, local business | User clicks a contact CTA but does not submit a lead form. | Use generate_lead once a valid lead/contact form is submitted. | contact_method, cta_location, link_url, business_unit |
| `account_access_intent` | customer portals, insurance, banking, SaaS | User clicks account/login entry point before authentication. | Use login after successful authentication. | entry_point, cta_location, destination_url |
| `chat_start` | support and sales chat | User starts a live chat or bot conversation. | Use generate_lead if chat creates a qualified lead. | chat_type, chat_entry_point, business_unit |
| `calculator_start` | loan, mortgage, insurance, savings calculators | User begins using a calculator/tool. | No direct recommended event fits. | tool_name, tool_category, entry_point |
| `calculator_complete` | calculators and simulators | User reaches a calculated result. | Use generate_lead if result submission creates a lead. | tool_name, result_type, value_band |
| `pricing_plan_select` | SaaS, subscription, memberships | User selects a plan before checkout/signup. | Use begin_checkout/purchase if the plan selection enters a checkout. | plan_id, plan_name, billing_period, cta_location |
| `feature_use` | SaaS/product-led growth | A key product feature is used and no recommended event fits. | Use select_content/share/join_group when semantics fit. | feature_name, feature_area, user_role |
| `appointment_start` | healthcare, services, local business, real estate | User starts an appointment booking flow. | Use generate_lead when appointment request is submitted. | appointment_type, entry_point, location_id |
| `appointment_booked` | appointment booking | Appointment booking is confirmed. | Use generate_lead if booked appointment is modeled as a lead. | appointment_type, location_id, lead_source |
| `modal_open` | important overlays/popins | A modal materially changes the journey or blocks/provides conversion path. | Use select_content if it is simply content selection. | modal_id, modal_name, trigger_source |
| `accordion_open` | FAQ and support content | FAQ interaction is a real support/reassurance KPI. | Use select_content if treating FAQ selection as content selection is sufficient. | content_id, content_name, content_type |

## DataLayer Patterns

### Generic interaction event

Use for: Custom interactions that are not ecommerce.

```js
dataLayer.push({'event_data': null});
dataLayer.push({
  'event': 'custom_event_name',
  'event_data': {
    'parameter_name': 'value'
  }
});
```

GTM mapping: Custom Event trigger = custom_event_name. GA4 Event tag event name = {{Event}} or fixed event name. Map event_data.* as event parameters.

### Manual page_view with page_data

Use for: SPA route changes or explicit pageview control.

```js
dataLayer.push({'page_data': null});
dataLayer.push({
  'event': 'page_view',
  'page_data': {
    'location': 'https://example.com/page',
    'title': 'Page title',
    'template': 'homepage',
    'language': 'fr'
  }
});
```

GTM mapping: Trigger on page_view. Map page_data.location/title/template/language into GA4 parameters when needed.

### Recommended search event

Use for: Submitted internal site search.

```js
dataLayer.push({'event_data': null});
dataLayer.push({
  'event': 'search',
  'event_data': {
    'search_term': 'insurance quote',
    'result_count': 12
  }
});
```

GTM mapping: GA4 Event name = search. Map search_term and optional custom result_count.

### Lead success event

Use for: Successful lead/contact/quote form submission.

```js
dataLayer.push({'event_data': null});
dataLayer.push({
  'event': 'generate_lead',
  'event_data': {
    'lead_source': 'homepage',
    'form_name': 'quote_form',
    'product_type': 'auto'
  }
});
```

GTM mapping: GA4 Event name = generate_lead. Map lead_source and business parameters. Mark as key event if appropriate.

### Custom quote start event

Use for: User starts quote flow before a lead exists.

```js
dataLayer.push({'event_data': null});
dataLayer.push({
  'event': 'begin_quote',
  'event_data': {
    'quote_type': 'insurance',
    'product_type': 'auto',
    'quote_entry_point': 'hero_auto',
    'cta_location': 'hero'
  }
});
```

GTM mapping: GA4 Event name = begin_quote. Register key dimensions only if needed for reporting.

### Ecommerce add_to_cart

Use for: User adds item to cart.

```js
dataLayer.push({'ecommerce': null});
dataLayer.push({
  'event': 'add_to_cart',
  'ecommerce': {
    'currency': 'EUR',
    'value': 99.99,
    'items': [{
      'item_id': 'SKU_123',
      'item_name': 'Product name',
      'item_category': 'Category',
      'price': 99.99,
      'quantity': 1
    }]
  }
});
```

GTM mapping: GA4 Event name = add_to_cart. Map official GA4 parameters from the GTM ecommerce dataLayer object, for example currency from ecommerce.currency and items from ecommerce.items.

### Ecommerce purchase

Use for: Order confirmation / purchase success.

```js
dataLayer.push({'ecommerce': null});
dataLayer.push({
  'event': 'purchase',
  'ecommerce': {
    'transaction_id': 'T12345',
    'currency': 'EUR',
    'value': 149.99,
    'tax': 20.00,
    'shipping': 4.99,
    'items': [{
      'item_id': 'SKU_123',
      'item_name': 'Product name',
      'price': 149.99,
      'quantity': 1
    }]
  }
});
```

GTM mapping: GA4 Event name = purchase. transaction_id is required for deduplication/reporting quality. Map official GA4 parameters from the GTM ecommerce dataLayer object.

### Promotion impression/click

Use for: Internal promotions and offer cards.

```js
dataLayer.push({'ecommerce': null});
dataLayer.push({
  'event': 'view_promotion',
  'ecommerce': {
    'promotion_id': 'promo_2026_01',
    'promotion_name': 'homepage_offer',
    'creative_slot': 'homepage_hero_1',
    'items': [{
      'item_id': 'offer_1',
      'item_name': 'homepage_offer'
    }]
  }
});
```

GTM mapping: Use view_promotion for exposure and select_promotion for click, keeping promotion IDs stable across both. Map official GA4 parameters from the GTM ecommerce dataLayer object.

## Sources

| Source | Type | URL | Used for |
|---|---|---|---|
| GA4 automatically collected events | official | https://support.google.com/analytics/answer/9234069?hl=en | Automatic and enhanced-measurement web events and default parameters. |
| GA4 enhanced measurement events | official | https://support.google.com/analytics/answer/9216061?hl=en | Enhanced-measurement event triggers and parameters. |
| GA4 recommended events | official | https://developers.google.com/analytics/devguides/collection/ga4/reference/events | Full recommended event catalog and event-level parameters. |
| GA4 ecommerce measurement | official | https://developers.google.com/analytics/devguides/collection/ga4/ecommerce | Ecommerce dataLayer/gtag examples and items array structure. |
| GA4 event parameters | official | https://support.google.com/analytics/table/13594742?hl=en | Parameter reporting behavior for automatic, enhanced, and recommended events. |
| GA4 event setup | official | https://developers.google.com/analytics/devguides/collection/ga4/events | How recommended/custom events are configured with gtag.js or GTM. |
| GTM data layer | official | https://developers.google.com/tag-platform/tag-manager/datalayer | dataLayer purpose and dataLayer.push implementation rules. |
| GA4 custom events | official | https://support.google.com/analytics/answer/12229021?hl=en | Rule to prefer automatic/enhanced/recommended events before custom events. |
| GA4 event collection limits | official | https://support.google.com/analytics/answer/9267744?hl=en | Event naming length and event-parameter limits. |
| Simo Ahava GA4 ecommerce guide | trusted_practitioner | https://www.simoahava.com/analytics/google-analytics-4-ecommerce-guide-google-tag-manager/ | Implementation judgement for GA4 ecommerce with GTM. |
| Simo Ahava GA4 events implementation guide | trusted_practitioner | https://www.simoahava.com/analytics/implementation-guide-events-google-analytics-4/ | Custom-event design judgement and GA4 implementation considerations. |
| Analytics Mania GA4 custom events | trusted_practitioner | https://www.analyticsmania.com/post/how-to-track-custom-events-with-google-analytics-4/ | Typical GTM custom-event patterns and reporting considerations. |
| Analytics Mania GTM data layer tutorial | trusted_practitioner | https://www.analyticsmania.com/post/ultimate-google-tag-manager-data-layer-tutorial/ | Human explanation and practical dataLayer examples. |
