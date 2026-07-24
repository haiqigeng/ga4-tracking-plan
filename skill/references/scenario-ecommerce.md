# Ecommerce Decisions

Use current official event-specific tables. Do not copy a universal ecommerce
profile across all events.

Review the real journeys for:

- promotion exposure and selection;
- list exposure and selection;
- product detail and variant choices;
- cart addition, removal, and cart view;
- checkout start, shipping, and payment;
- purchase confirmation;
- cancellation, return initiation, and refund only when the target experience
  or confirmed business process supports them.

Use the product model actually present in the website, design, backend, or
client specification. Retain item provenance where it is available and useful.
Use item-level custom option fields only when separate analysis is needed.

Do not create blocked account, return, cancellation, or refund rows merely
because they are common in ecommerce. Require evidence that they belong to the
target plan.

On purchase, include stable transaction context analysts will repeatedly use
when the confirmed order stores it. Treat fields not prescribed for purchase,
such as `shipping_tier` or `payment_type`, as justified custom event
parameters.
