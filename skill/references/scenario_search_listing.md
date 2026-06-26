# Search And Listing Scenario Reference

Use this reference for internal search, category listing pages, filters, sorting, pagination, recommendation modules, and result selection.

## Analyst Rules

- Use `search` for submitted internal search when a user query is available and privacy-safe.
- Use ecommerce `view_item_list` and `select_item` when the listing contains products or sellable items and official ecommerce item data is available.
- Use `select_content` for non-product content modules, editorial lists, navigation categories, or service links.
- Track filters and sorts only when they answer analysis questions; avoid one noisy event for every UI micro-change.
- Normalize controlled values to lowercase ASCII `snake_case`, but preserve product IDs, ISO codes, numeric values, and safe raw search terms when required.

## Event Selection

| Scenario | Prefer event | Classification | Notes |
|---|---|---|---|
| Search submitted | `search` | recommended | Requires `search_term`; scrub PII |
| Search results viewed | `view_search_results` or `page_view` with search context | custom or automatic | Use custom only when page_view cannot carry result context |
| Product list viewed | `view_item_list` | recommended_ecommerce | Requires `items`; list metadata recommended |
| Product selected | `select_item` | recommended_ecommerce | Requires clicked item data |
| Non-product content selected | `select_content` | recommended | Use `content_type` and `content_id` |
| Filter applied | `filter_apply` | custom | Use when merchandising/search analysis needs filter usage |
| Sort applied | `sort_apply` | custom | Use controlled values such as `price_asc` |
| Pagination / load more | `pagination` or `load_more` | custom | Track only if useful for UX/listing analysis |

## Suggested Parameters

| Parameter | Value rules |
|---|---|
| `search_term` | User-entered term after PII scrubbing |
| `search_results_number` | Integer count when available |
| `filter_type` | `category`, `size`, `color`, `price`, `brand`, or project taxonomy |
| `filter_value` | Normalized value; avoid high cardinality when possible |
| `sort_type` | `recommended`, `price_asc`, `price_desc`, `newest`, `rating` |
| `item_list_id` | Stable list ID |
| `item_list_name` | Normalized list name |

## DataLayer Pattern

```js
dataLayer.push({ event_data: null });
dataLayer.push({
  event: "search",
  event_data: {
    search_term: "summer_dress",
    search_results_number: 24
  }
});
```

## QA Contract

- Test one successful search, one zero-result search if relevant, and one PII-like input to confirm scrubbing.
- For ecommerce listings, verify item array completeness and list metadata.
- For filters and sorting, verify value normalization and confirm repeated UI changes do not create duplicate noise.

