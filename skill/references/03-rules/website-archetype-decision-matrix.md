# Website Archetype Decision Matrix

Use this reference when the user gives a website, page, homepage, or mixed user journey and expects the skill to infer the business needs before proposing events. It sits above the scenario references: identify the archetype and page role first, then load the scenario file(s) that match the selected journey.

## Reasoning Order

1. Map website or journey coverage when the requested scope is broader than a
   single page, using sitemap, navigation, representative templates, existing
   client files, and browser/Playwright exploration when needed.
2. Classify the business model and page role from visible signals.
3. Identify macro conversions, micro conversions, and diagnostic questions.
4. Decide whether the page contains sellable products, lead-capture journeys, authenticated journeys, support intent, publisher/content consumption, media playback, booking/reservation, locator usage, or hybrid combinations.
5. Select official GA4 and Piano events before custom events.
6. Add custom events only for business-specific intent, funnel friction, or diagnostics not covered by official events.
7. List events intentionally not tracked when the interaction is low-signal or duplicate.

Do not infer a full ecommerce checkout only because a page has product-like cards. Use ecommerce checkout and purchase events only when cart, checkout, transaction, refund, or product revenue data is in scope.

## Archetype Matrix

| Archetype / visible signals | Primary business questions | GA4 official-first events | Piano official-first events | Typical custom events only when justified | Usually avoid |
|---|---|---|---|---|---|
| Retail ecommerce with catalog, PDP, cart, checkout | Which products are discovered, added, purchased, refunded, and through which merchandising context? | `view_item_list`, `select_item`, `view_item`, `add_to_cart`, `view_cart`, `begin_checkout`, `add_shipping_info`, `add_payment_info`, `purchase`, `refund`, `view_promotion`, `select_promotion` | Sales Insights: `product.display`, `product.page_display`, `product.add_to_cart`, `cart.creation`, `cart.display`, `cart.delivery`, `cart.payment`, `transaction.confirmation`, `product.purchased` | `filter_apply`, `sort_apply`, `stock_alert_signup`, `size_guide_open`, `checkout_error` | Purchase-like custom events; ecommerce events missing item or transaction data; one event per banner |
| Product catalog without online checkout | Which categories/products generate interest and lead to contact/store/dealer actions? | `page_view`, `view_item_list`, `select_item`, `view_item` when item data is available; `select_content`, `search`, `generate_lead` for submitted interest | `page.display`, `click.navigation`, `click.action`, `product.display`, `product.page_display`, conversion properties when relevant | `contact_intent`, `dealer_locator_start`, `quote_request_start`, `product_compare`, `brochure_request` | `add_to_cart`, `purchase`, or `transaction.confirmation` when no cart/transaction exists |
| Lead generation, quote, contact, appointment | Which sources start the funnel, where do users drop, and which submissions become valid leads? | `form_start`/`form_submit` when enhanced measurement is sufficient; `generate_lead`; `sign_up` for real account/newsletter signup; `login` only after success | `page.display`, `click.action`, conversion properties such as `goal_type`; custom Data Model properties for form taxonomy | `begin_quote`, `form_step_view`, `form_step_submit`, `form_error`, `contact_intent`, `appointment_start`, `appointment_booked`, `calculator_start`, `calculator_complete` | `generate_lead` on CTA click; raw form values; field-focus tracking; raw error text |
| SaaS marketing and product-led signup | Which pricing/feature paths drive signup, trial, upgrade, and product activation? | `sign_up`, `login`, `tutorial_begin`, `tutorial_complete`, `generate_lead`, `purchase` when paid checkout exists, `select_content` | `page.display`, `click.action`, conversion properties; custom Data Model properties for plan/feature taxonomy | `pricing_plan_select`, `trial_start_intent`, `demo_request_start`, `upgrade_intent`, `feature_use`, `workspace_created` | Tracking every dashboard click; using `purchase` for non-paid signup |
| Publisher, content, resource hub, documentation | Which content is consumed, selected, shared, downloaded, or converted to subscription/newsletter? | `page_view`, `scroll`, `select_content`, `share`, `search`, `file_download`, `video_start`, `video_progress`, `video_complete`, `sign_up` | `page.display`, `click.navigation`, `click.download`, `publisher.impression`, `internal_search_result.display`, AV Insights for media | `newsletter_signup_intent`, `paywall_view`, `content_feedback`, `resource_filter_apply` | Duplicate scroll/video/download tracking when native collection is sufficient; one event per card |
| Support, help center, FAQ, service portal | Which support topics drive self-service, contact, login, or resolution? | `page_view`, `search`, `select_content`, `file_download`, `login`, enhanced outbound `click` | `page.display`, `click.action`, `click.navigation`, `click.download` | `contact_intent`, `chat_start`, `support_article_helpful`, `claim_intent`, `account_access_intent` | Claim descriptions, ticket text, account IDs, chat transcripts, every FAQ click if not actionable |
| Account portal and authentication | Which entry points create account demand and which auth methods succeed? | `login` after successful auth, `sign_up` after successful account creation | `page.display`, `click.action`, conversion properties if signup/login is modeled as conversion | `account_access_intent`, `password_reset_start`, `authentication_error` | Using `login` for an account-link click; sending user/account/customer IDs |
| Booking, reservation, travel, appointment commerce | Which searches, availability checks, selections, and bookings convert? | `search`, `view_item_list`, `select_item`, `view_item`, `begin_checkout`, `add_payment_info`, `purchase` for paid booking; `generate_lead` for request-only booking | `page.display`, `click.action`, Sales Insights only when product/cart/transaction semantics fit | `booking_start`, `booking_step_view`, `booking_step_submit`, `availability_filter_apply`, `booking_error`, `appointment_booked` | `purchase` when no payment/transaction is confirmed; raw dates or personal itinerary details when sensitive |
| Marketplace, classifieds, directory | Which listings are searched, filtered, viewed, saved, and contacted? | `search`, `view_item_list`, `select_item`, `view_item`, `generate_lead` for valid contact, `select_content` | `page.display`, `click.action`, `click.navigation`, product events only when listings are modeled as products | `seller_contact_intent`, `save_listing`, `alert_signup`, `listing_map_interaction`, `filter_apply` | Raw addresses, seller/buyer personal IDs, every map movement |
| Locator, store finder, branch network | Which locations are searched, viewed, selected, and contacted? | `search`, `select_content`, `generate_lead` for submitted appointment/contact, enhanced outbound `click` | `page.display`, `click.action`, `click.navigation` | `locator_search`, `store_select`, `directions_click`, `appointment_start`, `contact_intent` | Precise personal addresses, every map pan/zoom, raw query text with PII |
| Media player, webinar, audio/video | Which media starts, progresses, completes, pauses, and drives conversions? | Enhanced `video_start`, `video_progress`, `video_complete` when supported; custom only for unsupported players or business-specific metadata | AV Insights: `av.play`, `av.start`, `av.heartbeat`, `av.pause`, `av.resume`, `av.stop`, seek, buffer, ad events | `webinar_register_intent`, `media_error`, custom player events for unsupported players | Duplicate native and custom video tracking; raw viewer identifiers |
| Regulated finance, insurance, healthcare | Which journeys create qualified demand while respecting sensitive data limits? | `generate_lead`, `sign_up`, `login`, `search`, `select_content`, `file_download`, ecommerce only for real online sale | `page.display`, `click.action`, conversion properties; custom Data Model properties only when privacy-approved | `begin_quote`, `calculator_start`, `calculator_complete`, `eligibility_error`, `document_download`, `contact_intent` | Health/financial/claim details, policy numbers, customer IDs, free-text messages, exact sensitive values |

## Hybrid Composition Rules

- For a homepage, combine page display, meaningful promotion exposure/click, search, account/support intent, and selected content; do not include checkout or purchase unless the homepage itself supports those actions.
- For an ecommerce site with editorial modules, keep ecommerce product/promotion events separate from `select_content` editorial events.
- For a lead site with product cards, use product/list ecommerce events only when product entities and item data are meaningful for merchandising; otherwise use `select_content`, `begin_quote`, or `contact_intent`.
- For authenticated SaaS or portals, separate public marketing journeys from in-product feature analytics; do not overtrack every app control.
- For support and resource hubs, prefer official enhanced measurement for downloads, outbound clicks, and supported video before custom tracking.

## Custom Event Acceptance Gate

Accept a custom event only when it passes all checks:

| Check | Required answer |
|---|---|
| Business question | What report, decision, audience, or optimization action will use it? |
| Official event rejected | Which official GA4 or Piano event was considered and why is it insufficient? |
| Trigger | What precise user action or page state fires it? |
| Parameters | Which finite, normalized, privacy-safe values make it useful? |
| Registration | Which GA4 custom dimension/metric or Piano Data Model property is needed? |
| QA | Can a tester reproduce it and verify dataLayer/SDK plus network payload? |

Weak examples to reject or rewrite: `button_click`, `cta_click`, `link_click`, `menu_click`, `click_banner`, `custom_event`, `interaction`, `generic_click`.

Better semantic examples when justified: `account_access_intent`, `contact_intent`, `begin_quote`, `form_error`, `filter_apply`, `pricing_plan_select`, `stock_alert_signup`, `appointment_start`, `support_article_helpful`.

## Parameter Strategy By Business Need

| Need | Useful parameters | Notes |
|---|---|---|
| Component performance | `component_type`, `component_id`, `component_name`, `cta_location` | Use controlled lowercase ASCII values. |
| Content selection | `content_type`, `content_id`, `content_name` | Prefer stable IDs/slugs over changing text. |
| Product merchandising | Official item parameters such as `items[].item_id`, `items[].item_name`, `items[].item_category`, `items[].price`, `items[].quantity` | Use official GA4 item names and Piano product properties. |
| Search and listing | `search_term`, `result_count`, `filter_category`, `filter_value`, `sort_type` | Scrub PII and avoid every keystroke. |
| Lead funnel | `form_name`, `form_step`, `lead_type`, `validation_status`, `error_type`, `error_field_group` | Never send user-entered personal values. |
| Account/support | `login_status`, `contact_channel`, `support_topic`, `entry_point` | Do not send customer/account IDs or message text. |

## QA Implications

- Every macro conversion and key micro conversion needs clear reproduction
  context, expected platform payload, and network expectation for a future QA
  skill. Do not expose QA-only identifiers in the analyst-facing Event Matrix.
- When official events are automatic or enhanced measurement, QA should state how to confirm the native event and avoid duplicate custom tracking.
- When custom events are accepted, QA must verify that normalized parameter values match the allowed values in the plan.
