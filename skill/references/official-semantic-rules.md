# Official GA4 Semantic Rules

Use the current Google event table for event-specific fields, then consult the
linked implementation guidance for rules that the compact table does not fully
state. Preserve the exact checked text in `official_source.official_text`.

## Ecommerce Rules That Commonly Fail

- `index` is zero-based. The first item has `index: 0`, the second has
  `index: 1`. Source: <https://developers.google.com/analytics/devguides/collection/ga4/ecommerce>
- For ecommerce `value`, use the sum of `price * quantity` across `items` and
  exclude shipping and tax unless the selected event's current table states
  otherwise. Source: <https://developers.google.com/analytics/devguides/collection/ga4/reference/events>
- When an item is discounted, `price` is the discounted unit price and
  `discount` is the unit discount. GA4 does not subtract `discount`
  automatically. Source: <https://developers.google.com/analytics/devguides/collection/ga4/apply-discount>
- Event-level and item-level `coupon` represent independent order and item
  concepts. Include both only when both scopes exist.
- Item-level list fields override event-level list defaults. Retain item-level
  provenance downstream only when the source list can be persisted reliably.
- `item_variant` is official. `item_size` and `item_color` are custom item
  parameters when separate option analysis is needed. Item-level `coupon` and
  `item_brand` are official.
- Custom item parameters belong inside each relevant `items` object. GA4 can
  collect up to 27 custom item parameters per ecommerce event; reporting also
  depends on the property's item-scoped custom-dimension capacity. Source:
  <https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce>
- On `purchase`, `customer_type` is conditional and uses only `new` or
  `returning`; omit it when classification is uncertain. Use the current
  recommended-events table for the applicable lookback guidance.

## Authoring Rule

Do not derive an implementation rule from memory or from an example alone.
Check the current event row, its attached notes, and the relevant implementation
guide. A translated visible definition remains traceable to the exact current
official text stored internally.
