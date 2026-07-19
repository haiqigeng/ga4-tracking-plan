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
2. On route change, replace the `page` object with the complete current route
   context.
3. Send `page_view` only if the route should appear as a page/screen in GA4.
4. Send route-specific recommended or custom events after page context is ready.
5. For ecommerce routes, send `page_view` first, then `view_item`, `view_item_list`, cart, checkout, or purchase events.

## DataLayer Pattern

```js
dataLayer.push({ page: null });
dataLayer.push({
  event: "page_view",
  page: {
    page_location: "https://example.com/category/dresses",
    page_title: "Dresses",
    page_referrer: "https://example.com/",
    page_template: "listing_page",
    nav_language: "en",
    nav_environment: "production"
  }
});
```

## Implementation Notes

- Define initial load, route navigation, browser back/forward, and deep-route reload behavior.
- Send one expected `page_view` per route view without duplicates.
- Ensure route-specific events use the current page context.
- Prevent previous page, ecommerce, or event objects from persisting into the next route.
