# Piano Analytics Reference

Use this reference only for Piano Analytics tracking plans or cross-platform mappings that include Piano. Always verify official Piano documentation during the task when browsing is available.

Use `platform-piano-official-events.json` for structured event lookup, mandatory property checks, and cross-platform scenario mapping.

Official sources:

- Standard events: https://developers.piano.io/analytics/data-collection/how-to-send-events/standard-events/
- Send events via SDKs: https://developers.piano.io/analytics/data-collection/how-to-send-events/send-events-via-sdks/
- Collection API: https://developers.piano.io/analytics/data-collection/how-to-send-events/collection-api/
- Conversion: https://developers.piano.io/analytics/data-collection/how-to-send-events/conversion/
- Sales Insights: https://developers.piano.io/analytics/data-collection/how-to-send-events/sales-insights/
- AV Insights: https://developers.piano.io/analytics/data-collection/how-to-send-events/av-insights/
- Data Model properties: https://analytics-docs.piano.io/en/analytics/v1/properties

## Core Model

Piano Analytics is event-driven. A tracking plan should define event names and properties, not GA4-style event parameters.

Common implementation patterns:

- JavaScript SDK: `pa.sendEvent("event.name", { property_name: "value" })`
- Multiple events: `pa.sendEvents([{ name: "event.name", data: { property_name: "value" } }])`
- Collection API body: `events: [{ name: "event.name", data: { property_name: "value" } }]`
- Persistent properties can be set with SDK property methods, but event-level properties are usually clearer in a tracking plan unless the value truly applies to multiple subsequent events.

In the Data Model, property type matters. Custom properties should be defined with the same type that tagging will send.

## Standard Events

Use Piano standard events before custom events when they match the business action.

| Family | Event names | Core properties | Notes |
|---|---|---|---|
| Page | `page.display` | `page`, `page_chapter1`, `page_chapter2`, `page_chapter3` | Use for page views or virtual page displays. |
| Click | `click.action`, `click.navigation`, `click.download`, `click.exit` | `click`, `click_chapter1`, `click_chapter2`, `click_chapter3` | Choose the click event type by user intent: action, internal navigation, download, or outbound exit. |
| Onsite ads | `publisher.impression`, `publisher.click`, `self_promotion.impression`, `self_promotion.click` | `onsitead_type`, `onsitead_campaign`, `onsitead_creation`, `onsitead_variant`, placement and URL properties | Use for advertising or self-promotion placements, not ordinary CTA clicks. |
| Internal search | `internal_search_result.display`, `internal_search_result.click` | `ise_keyword`, `ise_page`, `ise_click_rank` | Use for onsite search results display and result clicks when available in the current docs or Data Model. |
| Multivariate testing | `mv_test.display`, `mv_test.click` | test and variant properties from the official/Data Model setup | Use only when a Piano-supported test taxonomy is in scope. |

## Sales Insights

Sales Insights uses native ecommerce event families and properties. Do not replace them with GA4 ecommerce events.

| Funnel area | Event names | Mandatory properties to check | Typical properties |
|---|---|---|---|
| Product impression | `product.display` | `product_id` | `product`, `product_variant`, `product_brand`, `product_placement`, `product_pricetaxincluded`, `product_pricetaxfree`, `product_stock`, `product_category1` to `product_category4` |
| Product page | `product.page_display` | `product_id` | Same product property family as `product.display` |
| Cart addition | `product.add_to_cart` | `product_id`; add `cart.creation` when this action creates a new cart | `cart_id`, product properties, `product_quantity`, `product_cartcreation` |
| Cart removal | `product.remove_from_cart` | `product_id` | `cart_id`, product properties, `product_quantity` |
| Cart lifecycle | `cart.creation`, `cart.display`, `cart.update`, `cart.delivery`, `cart.payment` | `cart_id` | `cart_currency`, `cart_turnovertaxincluded`, `cart_turnovertaxfree`, `cart_quantity`, `cart_nbdistinctproduct` |
| Awaiting payment | `cart.awaiting_payment`, `product.awaiting_payment` | `cart_id`, `product_id`, `cart_version` where applicable | Use when third-party validation such as 3D Secure delays final confirmation. |
| Transaction | `transaction.confirmation`, `product.purchased` | `transaction_id`; `product_id` for product purchase events | `cart_id`, payment, transaction, cart, and product properties |

When several Piano ecommerce events are emitted from one user action, describe them as an event bundle and keep each official event's mandatory properties visible.

## AV Insights

Use AV Insights events for audio or video players instead of custom media events when media measurement is in scope.

Common event names include:

- `av.play`
- `av.start`
- `av.pause`
- `av.resume`
- `av.stop`
- `av.heartbeat`
- `av.buffer.start`
- `av.buffer.heartbeat`
- `av.rebuffer.start`
- `av.rebuffer.heartbeat`
- `av.seek.start`
- `av.backward`
- `av.forward`
- `av.ad.click`
- `av.ad.skip`
- player-state events such as display, close, volume, subtitle, fullscreen, quality, speed, share, and error when those events are available in the current AV Insights documentation

Only include AV events when the page actually has measurable media. Avoid tracking every player state unless it supports the analysis need.

## Conversions

Piano conversions are commonly marked by setting `goal_type` on the event that represents the conversion. Use a controlled value such as `signup`, `lead`, `purchase`, or the client-approved conversion taxonomy.

## Piano-Specific QA

For each Piano event, include:

- SDK or Collection API event name
- expected properties and types
- whether the event uses `sendEvent`, `sendEvents`, or persistent properties
- Data Model property registration status for custom properties
- consent or privacy mode dependency
- network request expectation, including the event name and key properties
