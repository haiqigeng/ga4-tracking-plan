# SPA Routing Scenario Reference

Use this reference when the website is a single-page app, has client-side route changes, infinite scroll views, modal views that behave like pages, or app screens without full page reloads.

## Analyst Rules

- Determine whether GA4 enhanced measurement history-change tracking is enabled and whether it sends the right page_view events.
- Avoid duplicate `page_view` events on initial load and route changes.
- Treat manual page_view as an implementation decision, not a default requirement.
- Flush and update page context before sending route-specific events.
- For modal or virtual views, decide whether the view is analytically a page, a step, or an interaction before naming the event.

## Recommended Flow

1. On initial load, allow the normal GA4 page_view or send one controlled manual page_view, not both.
2. On route change, update `page_data`.
3. Send `page_view` only if the route should appear as a page/screen in GA4.
4. Send route-specific recommended or custom events after page context is ready.
5. For ecommerce routes, send `page_view` first, then `view_item`, `view_item_list`, cart, checkout, or purchase events.

## DataLayer Pattern

```js
dataLayer.push({ page_data: null });
dataLayer.push({
  event: "page_view",
  page_data: {
    location: "https://example.com/category/dresses",
    title: "Dresses",
    template: "listing_page"
  }
});
```

## QA Contract

- Test initial load, route navigation, browser back/forward, and reload on a deep route.
- Confirm one expected page_view per route view and no duplicates.
- Confirm route-specific events inherit the correct current page context.
- Confirm previous page, ecommerce, or event objects do not persist into the next route.

