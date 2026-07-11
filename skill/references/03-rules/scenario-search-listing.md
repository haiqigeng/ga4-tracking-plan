# Search And Listing Scenario Reference

Use this reference for internal search, category listing pages, filters, sorting, pagination, recommendation modules, and result selection.

## Analyst Rules

- Use `search` for submitted internal search when a user query is available and privacy-safe.
- Use ecommerce `view_item_list` and `select_item` when the listing contains products or sellable items and official ecommerce item data is available.
- Use `select_content` for non-product editorial cards, guides, or service-content objects. Use the approved client convention or dedicated surface events for header, menu, submenu, and footer navigation.
- Track filters and sorts only when they answer analysis questions; avoid one noisy event for every UI micro-change.
- Fire search and locator events on deliberate submit, result-page render, validated selection, or debounced stable result refresh. Do not fire a new analytics event for every keystroke while the user is typing.
- Normalize controlled values to lowercase ASCII `snake_case`, but preserve product IDs, ISO codes, numeric values, and safe raw search terms when required.

## Event Selection

| Scenario | Prefer event | Classification | Notes |
|---|---|---|---|
| Search submitted | `search` | recommended | Requires `search_term`; scrub PII |
| Search results viewed | `view_search_results` or `page_view` with search context | enhanced_measurement or automatic | Use enhanced measurement when configured query parameters identify the results page |
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

## Implementation Notes

- Define successful and zero-result search behavior when both matter.
- For ecommerce listings, specify complete item arrays and list metadata.
- Normalize filter and sort values and avoid duplicate events from repeated UI changes.
- For autocomplete, locator, or live-search modules, fire only at the agreed stable moment and not for each intermediate character.
