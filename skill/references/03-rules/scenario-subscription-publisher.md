# Subscription And Publisher Scenarios

Use this rule for editorial sites, media brands, subscription products,
paywalls, newsletters, and gated content.

## Analyst Questions

- Which content types and topics create meaningful engagement?
- Which content selections lead to registration, subscription, or retention?
- Where do paywall and registration journeys lose users?
- Which newsletter or account actions represent intent versus completed signup?

## Event Decisions

- Use automatic `page_view` and enhanced-measurement events when sufficient.
- Use `select_content` for meaningful article, topic, or module selection.
- Use `share`, `sign_up`, `login`, `begin_checkout`, and `purchase` when their
  official meanings fit.
- Use a custom event for paywall display, subscription-offer selection, or
  article completion only when it supports a concrete editorial or commercial
  decision that official events do not answer.

Keep article text, account identifiers, email addresses, comments, and search
queries containing personal data out of GA4.

## Scalable Parameters

Prefer stable content identifiers and controlled values such as
`content_id`, `content_type`, `content_topic`, `author_id`, `paywall_type`,
`subscription_offer`, and `access_status`. Record availability and ownership;
do not invent CMS metadata that has not been confirmed.
