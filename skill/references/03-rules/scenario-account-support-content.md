# Account, Support, And Content Scenario Reference

Use this reference for account entry, authentication context, self-service support, FAQ, editorial content, documents, videos, downloads, outbound links, and contact channels.

## Analyst Rules

- Prefer official enhanced measurement for scroll, file downloads, outbound clicks, site search, and video interactions when it is enabled and sufficient.
- Use `login` only after successful authentication, not for an account-link click.
- Use `select_content` for meaningful content/module selections when enhanced measurement click data is not sufficient.
- Use custom account/support intent events when the interaction is business-specific and not represented by official GA4 events.
- Avoid tracking every click in support pages; prioritize actions tied to intent, deflection, contact, or resolution.
- For scientific libraries, protocol libraries, document centers, and resource hubs, keep the analyst layer focused on search/filter, content selection, and file download outcomes instead of one event per visible card.
- For embedded videos, prefer GA4 enhanced measurement video events when they work for the player. Use custom video events only for non-supported players or business-specific webinar/live metadata.

## Event Selection

| Scenario | Prefer event | Classification | Notes |
|---|---|---|---|
| Account access click before auth result | `account_access_intent` | custom | Useful for account-entry demand; not the same as login |
| Successful login | `login` | recommended | Include `method` when available and non-sensitive |
| Successful signup | `sign_up` | recommended | Include `method` when available |
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
| `login_status` | `logged`, `not_logged`, `unknown`; never send personal IDs |

## DataLayer Pattern

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
- Keep email, phone, customer number, message text, and ticket details out of account/support events.
- Use screenshots that show the content or action context without personal information.
- Do not duplicate enhanced `file_download`, outbound `click`, or supported video events with custom resource-library events.
