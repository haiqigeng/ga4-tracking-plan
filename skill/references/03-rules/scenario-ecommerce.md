# Ecommerce Scenario Reference

Use this reference when the scoped journey includes merchandising, product discovery, cart, checkout, purchase, refund, coupons, shipping, or promotions.

## Analyst Rules

- Verify selected events and required parameters against current official Google Analytics ecommerce documentation before finalizing.
- Keep ecommerce events in ecommerce-only event blocks in the XLSX matrix.
- Split ecommerce event blocks by compatible parameter family: promotions, product lists, product detail, cart, checkout, and transactions.
- Use official GA4 parameter names in the event matrix: `currency`, `value`, `transaction_id`, `coupon`, `shipping`, `tax`, `items`, `items[].item_id`, `items[].item_name`, and other official item parameters.
- Keep GTM wrapper paths such as `ecommerce.items` in implementation notes or dataLayer examples, not as replacements for official GA4 parameter names.
- Respect event-level versus item-level scope. Prefer event-level `item_list_id`, `item_list_name`, `promotion_id`, `promotion_name`, `creative_name`, and `creative_slot` when all items share the same value. Use item-level equivalents only for mixed-list or mixed-promotion events because item-level values override event-level values.
- Choose one effective scope for each list or promotion value. Do not send the
  same list or promotion value at event and item level. On downstream cart,
  checkout, and transaction events, keep item-level list provenance only when
  a named attribution use justifies it and the source list is reliably
  persisted from selection.
- Show `items[].quantity` in matrices. GA4 defaults quantity to `1` if omitted, but the plan should still state whether the implementation sends `1`, relies on the default, or cannot provide the value.
- Use explicit availability states: `send`, `send_default_quantity`, `event_level_used`, `not_available`, or `not_applicable`.
- If required ecommerce data is unavailable, mark the ecommerce event as not implementable for that scope and consider a separate non-ecommerce intent event.
- Consolidate repeated same-name events when the parameter structure is identical; list allowed values for list names, creative slots, item categories, or component locations.
- Use a custom item parameter such as `items[].availability_status` on
  `view_item` when users switch variants and shortage affects product-detail
  analysis. Do not add it by default to `view_item_list`, `select_item`, or
  `add_to_cart`, where availability may be expensive, unavailable, or redundant.
- Use item availability on `view_cart` only for a documented persistent-cart,
  live-inventory model where previously saved items can become unavailable.
- After `add_payment_info`, represent unsuccessful payment with a custom
  diagnostic `payment_error` or governed `checkout_error`; reserve `purchase`
  for confirmed order success.
- Use `cancel_order` for a backend-confirmed cancellation of an existing order.
  Keep official `refund` for the later financial or item refund. An order can be
  cancelled without an immediate refund, and a refund can be partial.
- Treat browser discovery as evidence, not as the maximum plan scope. For a
  whole-site ecommerce plan, retain applicable official funnel events even when
  checkout or confirmation is blocked. Mark them `recommended`, keep website-
  specific values `to_confirm`, and use precise official or backend outcome
  triggers. Exclude a branch only when the business capability is confirmed
  not applicable; CAPTCHA, login, credentials, and unreachable success pages
  are not exclusion reasons.
- Reconcile the complete physical-retail funnel before delivery:
  `view_item_list`, `select_item`, `view_item`, `add_to_cart`, `view_cart`,
  `remove_from_cart`, `begin_checkout`, `add_shipping_info`,
  `add_payment_info`, `purchase`, and `refund`. Add a payment-failure diagnostic
  after payment submission. When customer service includes returns or order
  cancellation, add governed `start_return` and `cancel_order` outcomes rather
  than substituting `refund` for both.
Read `policy-ga4-ecommerce-parameters.md` before finalizing ecommerce matrices or CSV exports.

## Event Selection

| Scenario | Prefer event | Classification | Required / conditionally required notes |
|---|---|---|---|
| Product list impression | `view_item_list` | recommended_ecommerce | `items`; one of `items[].item_id` or `items[].item_name`; list metadata when available |
| Product click from list | `select_item` | recommended_ecommerce | `items`; one of item ID or item name; `item_list_id` / `item_list_name` when available |
| Product detail view | `view_item` | recommended_ecommerce | `items`; one of item ID or item name |
| Add to cart | `add_to_cart` | recommended_ecommerce | `items`; one of item ID or item name; `currency` required if `value` is sent |
| Remove from cart | `remove_from_cart` | recommended_ecommerce | `items`; one of item ID or item name |
| Cart view | `view_cart` | recommended_ecommerce | `items`; one of item ID or item name |
| Checkout start | `begin_checkout` | recommended_ecommerce | `items`; one of item ID or item name |
| Shipping method | `add_shipping_info` | recommended_ecommerce | `items`; `shipping_tier` when available |
| Payment method | `add_payment_info` | recommended_ecommerce | `items`; `payment_type` when available |
| Purchase confirmation | `purchase` | recommended_ecommerce | `transaction_id`; `items`; one of item ID or item name; `currency` required if `value` is sent |
| Refund | `refund` | recommended_ecommerce | `transaction_id`; item data when item-level refund is available |
| Return request accepted | `start_return` | custom | `transaction_id`; controlled return scope/reason when useful; fire only when the return request is accepted |
| Order cancellation confirmed | `cancel_order` | custom | `transaction_id`, controlled cancellation stage/reason; never raw support notes |
| Promotion impression | `view_promotion` | recommended_ecommerce | promotion metadata and `items` when promotion references items or offers |
| Promotion click | `select_promotion` | recommended_ecommerce | same identifiers as `view_promotion` for impression-to-click analysis |

## DataLayer Pattern

```js
dataLayer.push({ ecommerce: null });
dataLayer.push({
  event: "add_to_cart",
  ecommerce: {
    currency: "EUR",
    value: 59.99,
    items: [
      {
        item_id: "sku_123",
        item_name: "product_name",
        item_category: "category_name",
        price: 59.99,
        quantity: 1
      }
    ]
  }
});
```

## Implementation Notes

- Confirm the ecommerce object is flushed before each ecommerce event when reusable ecommerce data can persist.
- Specify the event name, ecommerce object, and item array at the exact trigger.
- For purchase and refund, document `transaction_id` ownership and uniqueness expectations.
- For promotions, use the same `promotion_id` and `promotion_name` across impression and selection when applicable.
