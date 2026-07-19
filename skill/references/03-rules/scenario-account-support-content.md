# Account, Support, And Content Scenario Reference

For publicly available signup and customer spaces, use synthetic information to
complete the real authenticated journey with an interactive browser or
Playwright MCP unless the user explicitly opts out. Cover
successful signup and login, password recovery, account navigation, orders,
returns, wishlist, preferences, loyalty, and reorder capabilities when present.
If the environment cannot complete access, record the synthetic-access gap and
the required follow-up. Do not present an inaccessible capability as observed
or client-confirmed. A recurrent account or service outcome may remain in a
whole-site specification only as a visibly `recommended` row when it answers a
named business question; keep its website data `to_confirm` and its confidence
low or medium.

Apply this evidence rule to every event behind login. Official generic events
such as `page_view`, `view_item_list`, `view_item`, or `add_to_cart` are not
exceptions: public navigation or account labels cannot prove that they occur
behind authentication or supply their site-specific pages, values, or trigger
details.

Use this reference for account entry, authentication context, self-service support, FAQ, editorial content, documents, videos, downloads, outbound links, and contact channels.

## Contents

- [Analyst Rules](#analyst-rules)
- [Event Selection](#event-selection)
- [Suggested Parameters](#suggested-parameters)
- [DataLayer Pattern](#datalayer-pattern)
- [Implementation Notes](#implementation-notes)

## Analyst Rules

- Prefer official enhanced measurement for scroll, file downloads, outbound clicks, site search, and video interactions when it is enabled and sufficient.
- Use `login` only after successful authentication, not for an account-link click.
- Use `select_content` for meaningful content/module selections when enhanced measurement click data is not sufficient.
- Use custom account/support intent events when the interaction is business-specific and not represented by official GA4 events.
- Do not stop customer-space coverage at `login` or `sign_up`. Select meaningful
  authenticated outcomes from the actual service capabilities and analysis
  needs; avoid tracking every account click.
- Use official `add_to_cart` for reorder actions that add prior-order products
  back to the cart. Preserve an `item_list_id` or `item_list_name` such as
  `order_history` instead of creating a redundant reorder event.
- Distinguish confirmed order cancellation from refund. Use `cancel_order` only
  after backend confirmation and `refund` when the financial or item refund is
  completed.
- Avoid tracking every click in support pages; prioritize actions tied to intent, deflection, contact, or resolution.
- For scientific libraries, protocol libraries, document centers, and resource hubs, keep the analyst layer focused on search/filter, content selection, and file download outcomes instead of one event per visible card.
- For embedded videos, prefer GA4 enhanced measurement video events when they work for the player. Use custom video events only for non-supported players or business-specific webinar/live metadata.

## Event Selection

| Scenario | Prefer event | Classification | Notes |
|---|---|---|---|
| Account access click before auth result | `account_access_intent` | custom | Useful for account-entry demand; not the same as login |
| Successful login | `login` | recommended | Include `method` when available and non-sensitive |
| Successful signup | `sign_up` | recommended | Include `method` when available |
| Password reset completed | `password_reset` | custom | Track confirmed completion, not email entry or the request click |
| Order history viewed | `view_order_history` | custom | Useful for self-service adoption; page_view alone may suffice when page typing is reliable |
| Order detail viewed | `view_order` | custom | Use controlled status and age buckets; avoid customer and raw order identifiers unless technically required |
| Return initiated | `start_return` | custom | Use controlled return scope and eligibility state, never raw reason text |
| Order cancellation confirmed | `cancel_order` | custom | Backend-confirmed cancellation; keep separate from `refund` |
| Refund completed | `refund` | recommended_ecommerce | Use official transaction semantics and item data when available |
| Previous item added again | `add_to_cart` | recommended_ecommerce | Set order-history list context and send official item data |
| Profile updated | `update_profile` | custom | Send only a controlled field group, never the changed personal value |
| Communication preference updated | `update_preferences` | custom | Send preference type and opt state only when consent governance allows it |
| FAQ question opened | `select_content` or `faq_expand` | recommended or custom | Prefer `select_content` if it fits content selection |
| Contact option selected | `contact_intent` | custom | Useful for support demand; include channel |
| File downloaded | `file_download` | enhanced_measurement | Use enhanced measurement if sufficient |
| Outbound click | `click` | enhanced_measurement | Use enhanced measurement if sufficient |
| Video progress | `video_start`, `video_progress`, `video_complete` | enhanced_measurement | Use native enhanced measurement events if sufficient |
| Resource search/filter | `search`, `select_content`, `filter_apply` | recommended or custom | Use `search` for submitted queries and `filter_apply` only when filter analysis is needed |
| Resource selected | `select_content` | recommended | Use for article, protocol, webinar, FAQ, or document-card selection when download/click events are not enough |

## Suggested Parameters

| Parameter | Value rules |
|---|---|
| `content_type` | `faq_question`, `article`, `support_link`, `document`, `video` |
| `content_id` | Stable ID or slug |
| `content_name` | Normalized readable name if stable |
| `cta_location` | Page area or module |
| `contact_channel` | `phone`, `email`, `chat`, `store`, `callback` |
| `method` | Official login/sign_up method when available |
| `login_status` | `logged_in`, `logged_out`; use as a user property when the analysis need is approved |
| `customer_status` | `new`, `returning`, `unknown`; use only when the source is reliable |
| `account_type` | Controlled low-cardinality English values; avoid labels or statuses that change too frequently |
| `account_section` | `dashboard`, `orders`, `returns`, `profile`, `preferences`, `wishlist`, `loyalty` |
| `order_status` | Controlled lifecycle value; never raw backend text |
| `order_age_bucket` | Stable bucket such as `under_30_days`, not an exact personal timestamp |
| `return_scope` | `full_order` or `selected_items` |
| `cancellation_reason` | Approved non-personal reason category; never free text |
| `profile_field_group` | `identity`, `address`, `contact_preferences`, or another governed group; never field values |
| `preference_type` | Controlled communication or service preference category |
| `preference_state` | `opt_in` or `opt_out` when collection is approved |

## DataLayer Pattern

For shared authenticated state, use the separate `user` dataLayer protocol in
`policy-authenticated-user-context.md`. Do not add those fields to each event.

```js
dataLayer.push({ event_data: null });
dataLayer.push({
  event: "contact_intent",
  event_data: {
    contact_channel: "chat",
    cta_location: "support_page"
  }
});
```

## Implementation Notes

- Do not duplicate enhanced measurement with custom tracking.
- Fire login and signup events only after success.
- Fire cancellation, return, profile, preference, and password events only after
  the backend confirms the corresponding outcome.
- Keep email, phone, customer number, message text, and ticket details out of account/support events.
- Use screenshots that show the content or action context without personal information.
- Do not duplicate enhanced `file_download`, outbound `click`, or supported video events with custom resource-library events.
