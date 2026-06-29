# Ecommerce Scenario Reference

Use this reference when the scoped journey includes merchandising, product discovery, cart, checkout, purchase, refund, coupons, shipping, or promotions.

## Analyst Rules

- Verify selected events and required parameters against current official Google Analytics ecommerce documentation before finalizing.
- Keep ecommerce events in ecommerce-only event blocks in the XLSX matrix.
- Split ecommerce event blocks by compatible parameter family: promotions, product lists, product detail, cart, checkout, and transactions.
- Use official GA4 parameter names in the event matrix: `currency`, `value`, `transaction_id`, `coupon`, `shipping`, `tax`, `items`, `items[].item_id`, `items[].item_name`, and other official item parameters.
- Keep GTM wrapper paths such as `ecommerce.items` in implementation notes or dataLayer examples, not as replacements for official GA4 parameter names.
- Respect event-level versus item-level scope. Prefer event-level `item_list_id`, `item_list_name`, `promotion_id`, `promotion_name`, `creative_name`, and `creative_slot` when all items share the same value. Use item-level equivalents only for mixed-list or mixed-promotion events because item-level values override event-level values.
- Show `items[].quantity` in matrices. GA4 defaults quantity to `1` if omitted, but the plan should still state whether the implementation sends `1`, relies on the default, or cannot provide the value.
- Use explicit availability states: `send`, `send_default_quantity`, `event_level_used`, `not_available`, or `not_applicable`.
- If required ecommerce data is unavailable, mark the ecommerce event as not implementable for that scope and consider a separate non-ecommerce intent event.
- Consolidate repeated same-name events when the parameter structure is identical; list allowed values for list names, creative slots, item categories, or component locations.
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

## QA Contract

- Confirm the ecommerce object is flushed before each ecommerce event when reusable ecommerce data can persist.
- In GTM Preview, verify the event name, ecommerce object, and item array at the exact event.
- In network checks, verify GA4 requests contain the expected event name and item parameters.
- For purchase and refund, verify `transaction_id` uniqueness and revenue deduplication behavior.
- For promotions, test impression and click with the same `promotion_id` / `promotion_name` when applicable.
