# Cross-Domain And Multi-Market Scenarios

Use this rule when one business journey spans domains, markets, languages,
currencies, brands, or storefront implementations.

## Coverage

- Identify every domain and route participating in the journey.
- Separate shared journey logic from market-specific steps.
- Record where cross-domain configuration, consent behavior, or referral
  handling must be confirmed outside the tracking plan.
- Use representative evidence for each materially different page template.

## Taxonomy

Reuse event names across markets when the business meaning and trigger are the
same. Use controlled parameters such as `site_market`, `nav_language`,
`business_unit`, or `storefront_id` only when they support analysis and are
available consistently.

Keep ISO language, country, and currency codes in their official format. Apply
lowercase ASCII `snake_case` to controlled business labels, not to product IDs,
transaction IDs, URLs, or raw ISO codes.

## Ecommerce

Send each transaction in its actual currency and follow the official GA4
ecommerce model. Do not convert values inside the tracking plan unless a
separate, approved reporting requirement defines that transformation.
