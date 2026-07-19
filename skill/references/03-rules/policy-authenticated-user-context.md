# Authenticated User Context

Use a shared `user` dataLayer object when signed-in status improves
journey, retention, or customer analysis. This is a state contract, not an
event, so document it in `01 GTM Protocol` and define its fields in
`02 Parameter Reference`. Do not repeat these values in every Event Matrix
payload.

## GA4-Safe Pattern

Push the object when authentication state is known, immediately after a
successful login, and immediately after logout:

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

After logout, clear the identifier and update the state:

```js
dataLayer.push({
  user: {
    user_id: null,
    login_status: "logged_out",
    customer_status: "unknown",
    account_type: "unknown"
  }
});
```

## Mapping Rules

- `user.user_id` is an opaque, stable, non-PII identifier. Map it only
  to the Google tag `user_id` setting. Omit it until sign-in and set it to
  `null` on logout. Never send or register it as an event parameter, user
  property, or custom dimension.
- `login_status`, `customer_status`, and an approved low-cardinality
  `account_type` can be GA4 user properties when they answer a real analysis
  need. Define controlled English lowercase ASCII values and register only the
  properties analysts will use.
- Do not include email, phone, name, postal address, customer number, or other
  directly identifying values in GA4.
- Keep advertising enhanced-conversion or user-provided data in a separately
  governed `user_data` implementation. It needs its own destination, consent,
  normalization or hashing rules, and must never be mapped into GA4 events or
  user properties.

## Official Sources

- GA4 User-ID: https://developers.google.com/analytics/devguides/collection/ga4/user-id
- GA4 user properties: https://developers.google.com/analytics/devguides/collection/protocol/ga4/user-properties
- Consent mode: https://developers.google.com/tag-platform/security/guides/consent
- Avoid sending PII: https://support.google.com/analytics/answer/6366371
- Google Ads enhanced conversions: https://support.google.com/google-ads/answer/13262500
