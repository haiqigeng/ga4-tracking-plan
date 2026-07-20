# GA4 Ecommerce Parameter Policy

Use this reference whenever a plan includes GA4 ecommerce events or an ecommerce event matrix.

## Official Scope Rules

- Check current official GA4 ecommerce and recommended-event docs before finalizing event names, parameter names, and parameter scope.
- Use event-level `currency` whenever `value` is sent.
- Review every field in the selected event's current official table as an
  internal candidate. Retain required fields and applicable conditional fields.
  For other applicable official fields, prefer inclusion when website evidence,
  the business model, a recurrent analysis or activation use, or a feasible
  source supports them; do not fill the client matrix mechanically with the
  complete table. A plausible unresolved conditional field remains visible as
  `to_confirm`, `requires_development`, or `requires_backend` rather than being
  silently excluded.
- Use `items` when product/item detail is part of the event. When `items` is sent, each item needs one of `items[].item_id` or `items[].item_name`. Do not make `items` mandatory for an event such as `refund` when the current official event table marks it optional and the plan intentionally specifies a full-transaction refund.
- `items[].quantity` is optional and GA4 defaults it to `1` when omitted, but tracking plans should still display the intended quantity so analysts and developers do not confuse omission with absence.
- `items[].affiliation` and `items[].location_id` are item-scoped only.
- Event-level and item-level `coupon` are independent. Use item-level `items[].coupon` for item-specific coupons or discounts.
- `item_list_id`, `item_list_name`, `promotion_id`, `promotion_name`, `creative_name`, and `creative_slot` can have event-level and item-level forms. If item-level values are set, they override event-level values. If item-level values are not set, GA4 uses event-level values when present.
- Non-official item fields are custom item-scoped parameters, not GA4 ecommerce item parameters. Classify them as `custom_item_parameter`, document the business question, and register an item-scoped custom dimension when the value must be usable in GA4 UI reporting.
- Use official `items[].item_variant` before creating a separate custom item field for variant, color, size, or other product-option analysis.
- Include `items[].item_category4` and `items[].item_category5` only when the
  website or an authoritative client source confirms that taxonomy depth and a
  named analysis need uses it. Do not generate empty hierarchy levels.
- There is no prescribed `items[].item_size` field. Add it only as a custom item
  parameter when size must be analysed separately and `items[].item_variant`
  cannot answer the question.

## Preferred Planning Convention

Select parameters in this order:

1. Include every unconditionally required official parameter.
2. Include each conditionally required parameter when its condition applies,
   such as `currency` when `value` is sent. When applicability is plausible but
   not yet proven, prefer retaining it with a concrete confirmation or
   development dependency over exclusion.
3. Include at least one item identity field, `items[].item_id` or `items[].item_name`, for every ecommerce item.
4. Add applicable optional official parameters when business questions,
   website or client evidence, recurrent ecommerce analysis, activation, or a
   feasible source justifies them. Prefer inclusion when those signals exist,
   except that category levels four and five require explicit taxonomy and use
   evidence. Do not add every optional field by default.
5. Add a custom event or item parameter only when no official field answers the
   same need and the official gap, reporting purpose, value rule, scope,
   event-specific classification, source, registration decision, cardinality,
   privacy, and owner are explicit.

Do not use a canonical profile as an instruction to add every field. Profiles
control stable row order for the parameters selected by the analyst; they do
not expand the event specification.

Use event-level list and promotion parameters as the current event default when
all items share the same list or promotion:

- `item_list_id`, `item_list_name` for homogeneous listing/search/recommendation events
- `promotion_id`, `promotion_name`, `creative_name`, `creative_slot` for homogeneous promotion impressions and clicks

Use item-level equivalents when items genuinely come from different lists,
promotions, creatives, or placements, or when the implementation reliably
retains each item's originating list or promotion for downstream attribution.
Google permits both scopes: item-level list and promotion values override the
event-level default, while event- and item-level `coupon` values are
independent. Dual scope must be intentional and non-conflicting; it is not an
automatic error. In human matrices, show the item-level row as
`event_level_used` only when the event-level fallback is intentional and no
item override is sent.

## Checkout And Purchase Continuity

Treat `purchase` as the durable transaction record analysts will reuse. Carry
stable, analysis-useful checkout context into `purchase` when the value is
reliably persisted to the confirmed order and has a named reporting use. This
can include originating item list or promotion fields and selected shipping or
payment descriptors. Do not propagate transient UI state, raw errors, or form
input.

`shipping_tier` is prescribed for `add_shipping_info`, and `payment_type` is
prescribed for `add_payment_info`; neither is prescribed in the official
`purchase` event table. If either is deliberately sent on `purchase`, classify
that purchase binding as `custom_event_parameter`, document the official gap,
source path, persistence and reset rule, registration decision, cardinality,
privacy, and owner. The same parameter name may therefore be official on its
checkout event and custom on `purchase`.

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

## Official-First Row Order

The renderer derives stable row order from the event name and official catalog;
the structured plan does not store a second profile or payload snapshot.

Use a stable order inside each family:

1. Event-level ecommerce parameters: `transaction_id`, `currency`, `value`, `coupon`, `shipping`, `tax`, `customer_type`, `payment_type`, `shipping_tier`, `item_list_id`, `item_list_name`, `promotion_id`, `promotion_name`, `creative_name`, `creative_slot`.
2. `items`.
3. Item-scoped prescribed parameters: `items[].item_id`, `items[].item_name`, `items[].affiliation`, `items[].coupon`, `items[].discount`, `items[].index`, `items[].item_brand`, `items[].item_category`, `items[].item_category2`, `items[].item_category3`, `items[].item_category4`, `items[].item_category5`, `items[].item_list_id`, `items[].item_list_name`, `items[].item_variant`, `items[].location_id`, `items[].price`, `items[].quantity`.
4. Promotion item fallback rows when relevant: `items[].creative_name`, `items[].creative_slot`, `items[].promotion_id`, `items[].promotion_name`.
5. Business-specific item parameters only when analytically justified. Do not prefill custom item parameter names in generic templates; require explicit business need, `custom_item_parameter` classification, and item-scoped custom-dimension registration when needed for GA4 reporting.

## Availability Status

`items[].availability_status` is a custom item parameter, not an official GA4
item parameter. Use it by default only on `view_item` when users navigate among
variants and shortage status supports product or merchandising analysis.

Use English controlled values such as:

```text
in_stock | low_stock | out_of_stock | preorder | backorder | discontinued
```

Do not add it by default to `view_item_list` or `select_item`, where obtaining
availability for many products can be expensive, or to `add_to_cart`, where an
unavailable item normally cannot be added. Use it on `view_cart` only for a
documented persistent-cart implementation whose items are refreshed against
live inventory and can become unavailable before purchase.

## Supplemental CSV Deliverables

When visual density is a concern or the user requests a diffable secondary artifact, produce the long-format CSV from `scripts/export_tracking_plan_csv.py`. It repeats event context for each parameter and includes `parameter_scope`, `requirement`, `expected_value`, `availability`, and `scope_rule`. Do not use the CSV as a replacement for the standard generated XLSX workbook unless the user explicitly asks for CSV-only output.
