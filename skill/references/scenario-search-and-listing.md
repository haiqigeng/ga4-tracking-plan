# Search, Listing, And Merchandising Decisions

Use this reference for site search, categories, product or service lists,
recommendation modules, filters, sorting, pagination, and merchandising
promotions.

## Event Decisions

- Use official `search` for a deliberate internal-search submission and include
  official `search_term`. Define zero-result behavior when it supports search
  optimization.
- Use `view_item_list` when a product or service list is actually rendered and
  `select_item` when an item is selected from it. Keep event-level list fields
  for one homogeneous list and item-level fields when provenance differs.
- Consider custom `filter_apply` and `sort_apply` when the choices affect
  merchandising, discovery, or UX decisions. Their absence from the official
  recommended-event catalog is a gap to evaluate, not a reason to omit them.
- Consider a pagination or load-more event only when depth of discovery is an
  actionable question that cannot be answered reliably from list impressions.
- Use official `view_promotion` and `select_promotion` for true merchandising
  placements, offers, or campaign creatives. Do not treat ordinary navigation
  as promotion measurement.
- Use `select_content` for identifiable non-product content objects when its
  official semantics fit. Do not force navigation or business-specific tools
  into it.

## Parameters And Values

Inspect and, when stable and no larger than 50, exhaust:

- list IDs and names when they form a controlled site taxonomy rather than an
  open catalogue;
- filter types, sort types, pagination methods, module locations, and promotion
  types;
- zero-result status or result-count buckets when deliberately modeled.

Do not exhaust raw search terms, product IDs or names, URLs, or changing
inventory. Controlled semantic values use the workbook language and lowercase
ASCII `snake_case`; raw search terms and authoritative labels retain their
source representation.
