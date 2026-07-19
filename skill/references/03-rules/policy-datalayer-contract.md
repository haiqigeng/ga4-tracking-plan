# DataLayer Contract

Use one predictable project dataLayer structure across the tracking plan. The
`page`, `event_data`, and `user` wrappers are project conventions, not
Google-required object names. The top-level `event` behavior and the ecommerce
payload follow GTM and GA4 conventions. Keep the top-level `event` key as the
GTM Custom Event trigger value for manual events and group payload fields under
the project wrapper that owns their lifecycle.

## Project Wrapper Contract

| Top-level key | Purpose |
| --- | --- |
| `event` | Required string containing the final GA4 event name for a manual event. It is not an object because GTM reserves this key for Custom Event triggers. |
| `page` | Page, route, market, language, template, and other reusable on-page context. |
| `event_data` | Parameters that describe the current non-ecommerce interaction or outcome. |
| `ecommerce` | Official GA4 ecommerce event and item data, following the current Google GTM format rather than a freely designed project schema. |
| `user` | Connected-user state and approved low-cardinality user properties. |

Do not place event parameters loosely at the root. Do not use legacy
`page_data`, `user_context`, `event_parameters`, or generic wrapper event names.

## Same-Name Mapping

The inner dataLayer key must match the final GA4 parameter or user-property
name. GTM unwraps the namespace but does not rename the field:

```text
page.page_template -> page_template
event_data.search_term -> search_term
ecommerce.shipping_tier -> shipping_tier
user.login_status -> login_status
user.user_id -> Google tag user_id setting
```

Use official GA4 names unchanged. Use governed English lowercase ASCII
`snake_case` for custom technical names. Wrapper paths are implementation paths
and must not replace final GA4 parameter names in the Event Matrix.

## Page And Core Context

The initial page or core context can be pushed without an `event` key. Populate
only fields that have a reliable source and a concrete implementation or
analysis use:

```js
dataLayer.push({
  page: {
    page_location: "https://example.com/products",
    page_title: "Products",
    page_referrer: "https://example.com/",
    page_template: "product_list",
    nav_language: "en",
    nav_environment: "production"
  },
  user: {
    login_status: "logged_out"
  }
});
```

For a controlled manual page view, keep the trigger string at the root and use
the same final parameter names inside `page`:

```js
dataLayer.push({ page: null });
dataLayer.push({
  event: "page_view",
  page: {
    page_location: "https://example.com/products",
    page_title: "Products",
    page_referrer: "https://example.com/",
    page_template: "product_list",
    nav_language: "en",
    nav_environment: "production"
  },
  user: {
    login_status: "logged_out"
  }
});
```

Use `page_location`, `page_title`, `page_referrer`, `page_template`,
`nav_language`, and `nav_environment` as the normal core baseline. Add
`site_market`, `site_country`, `site_brand`, `content_group`, or equivalent
context only when the website structure and analysis needs justify them.

Set the complete page state on every full page or SPA route change. Clear stale
page or journey fields before replacement when the dataLayer merge behavior
could preserve values from the previous route. Automatic GA4 page fields need
no manual override unless the website implementation requires one.

## Interaction Events

Use `event_data` for ordinary recommended and custom event parameters:

```js
dataLayer.push({ event_data: null });
dataLayer.push({
  event: "search",
  event_data: {
    search_term: "summer dresses",
    search_location: "header"
  }
});
```

## Ecommerce Events

Resolve the current event structure, item structure, requiredness, and reset
guidance from official Google documentation. Keep every ecommerce field under
`ecommerce` and use the final official or approved custom parameter name as the
inner key. Do not duplicate ecommerce fields in `event_data`.

## User State

Push authenticated state independently under `user` when it becomes known and
when it changes:

```js
dataLayer.push({
  user: {
    user_id: "<opaque_stable_id>",
    login_status: "logged_in",
    customer_status: "returning",
    account_type: "standard"
  }
});
```

Map `user.user_id` only to the Google tag User-ID setting. Keep separately
governed advertising user-provided data outside this GA4-safe `user` object.

## Consent Sequence

Mark a page/core context push `core_context_before_cmp_ready`; it may prepare
page and signed-in context before CMP readiness. Every other manual interaction,
lead, account, or ecommerce push is `after_cmp_ready` and must not precede the
CMP event that establishes the applicable consent state. Record the client-
specific queue or replay rule when an action can occur before CMP readiness.

Consent defaults must still be established before commands that send
measurement data. An early page/core dataLayer push does not authorize an
analytics tag to fire before its consent requirements are satisfied.
