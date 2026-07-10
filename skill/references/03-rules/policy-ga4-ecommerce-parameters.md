# GA4 Ecommerce Parameter Policy

Use this reference whenever a plan includes GA4 ecommerce events or an ecommerce event matrix.

## Official Scope Rules

- Check current official GA4 ecommerce and recommended-event docs before finalizing event names, parameter names, and parameter scope.
- Use event-level `currency` whenever `value` is sent.
- Set every ecommerce parameter that the implementation reliably has, even when the parameter is optional.
- Use `items` for product/item context. Each item needs one of `items[].item_id` or `items[].item_name`.
- `items[].quantity` is optional and GA4 defaults it to `1` when omitted, but tracking plans should still display the intended quantity so analysts and developers do not confuse omission with absence.
- `items[].affiliation` and `items[].location_id` are item-scoped only.
- Event-level and item-level `coupon` are independent. Use item-level `items[].coupon` for item-specific coupons or discounts.
- `item_list_id`, `item_list_name`, `promotion_id`, `promotion_name`, `creative_name`, and `creative_slot` can have event-level and item-level forms. If item-level values are set, they override event-level values. If item-level values are not set, GA4 uses event-level values when present.
- Non-official item fields are custom item-scoped parameters, not GA4 ecommerce item parameters. Classify them as `custom_item_parameter`, document the business question, and register an item-scoped custom dimension when the value must be usable in GA4 UI reporting.
- Use official `items[].item_variant` before creating a separate custom item field for variant, color, size, or other product-option analysis.

## Preferred Planning Convention

Prefer event-level list and promotion parameters when all items in the event share the same list or promotion:

- `item_list_id`, `item_list_name` for homogeneous listing/search/recommendation events
- `promotion_id`, `promotion_name`, `creative_name`, `creative_slot` for homogeneous promotion impressions and clicks

Use item-level equivalents only when items in the same event genuinely come from different lists, promotions, creatives, or placements. In human matrices, show the item-level row as `event_level_used` when that fallback is intentional.

Use these availability values instead of silent blanks:

- `send`: value should be sent.
- `send_default_quantity`: send `items[].quantity = 1` or explicitly document the GA4 default.
- `event_level_used`: item-level value intentionally omitted because event-level value applies.
- `not_available`: parameter would be useful or official but the current implementation/data source is not confirmed.
- `not_applicable`: parameter does not fit the event.

## Matrix Grouping

Do not group ecommerce events together just because they are in the same journey. Group only events that share a compatible parameter family:

- Ecommerce promotions: `view_promotion`, `select_promotion`
- Ecommerce product lists: `view_item_list`, `select_item`
- Ecommerce product detail: `view_item`
- Ecommerce cart: `add_to_cart`, `remove_from_cart`, `view_cart`
- Ecommerce checkout: `begin_checkout`, `add_shipping_info`, `add_payment_info`
- Ecommerce transactions: `purchase`, `refund`

If a block becomes too dense, split it rather than hiding parameters. Keep rows in a stable official-first order so analysts can scan the same parameter in the same position across compatible events.

## Canonical Parameter Profiles

Use `parameter_profile` for every GA4 ecommerce event in structured plans:

- `promotion_profile`: `view_promotion`, `select_promotion`
- `list_profile`: `view_item_list`, `select_item`
- `item_detail_profile`: `view_item`
- `cart_profile`: `add_to_cart`, `remove_from_cart`, `view_cart`
- `checkout_profile`: `begin_checkout`, `add_shipping_info`, `add_payment_info`
- `transaction_profile`: `purchase`
- `refund_profile`: `refund`

The profile records the canonical parameter order used by
`scripts/ecommerce_matrix.py`. Do not reorder related ecommerce parameters per
event unless the exception is explicit and useful for implementation.

## Official-First Row Order

Use a stable order inside each family:

1. Event-level ecommerce parameters: `transaction_id`, `currency`, `value`, `coupon`, `shipping`, `tax`, `customer_type`, `payment_type`, `shipping_tier`, `item_list_id`, `item_list_name`, `promotion_id`, `promotion_name`, `creative_name`, `creative_slot`.
2. `items`.
3. Item-scoped prescribed parameters: `items[].item_id`, `items[].item_name`, `items[].affiliation`, `items[].coupon`, `items[].discount`, `items[].index`, `items[].item_brand`, `items[].item_category`, `items[].item_category2`, `items[].item_category3`, `items[].item_category4`, `items[].item_category5`, `items[].item_list_id`, `items[].item_list_name`, `items[].item_variant`, `items[].location_id`, `items[].price`, `items[].quantity`.
4. Promotion item fallback rows when relevant: `items[].creative_name`, `items[].creative_slot`, `items[].promotion_id`, `items[].promotion_name`.
5. Business-specific item parameters only when analytically justified. Do not prefill custom item parameter names in generic templates; require explicit business need, `custom_item_parameter` classification, and item-scoped custom-dimension registration when needed for GA4 reporting.

## Supplemental CSV Deliverables

When visual density is a concern or the user requests a diffable secondary artifact, produce the long-format CSV from `scripts/export_tracking_plan_csv.py`. It repeats event context for each parameter and includes `parameter_scope`, `requirement`, `expected_value`, `availability`, and `scope_rule`. Do not use the CSV as a replacement for the default XLSX workbook template unless the user explicitly asks for CSV-only output.
