# Website Archetypes

Use archetypes to prompt analyst questions, not to copy a standard event list.
One website can combine several archetypes.

| Archetype | Core questions | Official-first GA4 families | Custom only when justified |
| --- | --- | --- | --- |
| Retail ecommerce | Discovery, merchandising, cart progression, revenue, refund | `view_item_list`, `select_item`, `view_item`, cart, checkout, purchase, refund, promotion events | filters, sorting, stock alerts, checkout diagnostics |
| Lead generation | Intent, form progression, valid lead creation, source quality | `form_start`, `form_submit`, `generate_lead`, search, signup/login where relevant | meaningful form steps, validation errors, quote or calculator milestones |
| Publisher or content | Consumption, selection, sharing, subscription intent | `page_view`, `scroll`, `select_content`, `share`, video, file download | paywall, article completion, unsupported media engagement |
| Booking or travel | Search, availability, selection, booking value | search, item-list, item, checkout and purchase events for paid bookings | availability and non-transactional booking milestones |
| SaaS or product | Acquisition, activation, feature adoption, upgrade | `sign_up`, `login`, tutorial, select content, purchase | high-value feature use and workspace milestones |
| Support or account | Self-service success, contact intent, account access | search, select content, download, login | chat start, contact intent, article feedback |
| Donation or membership | Contribution intent, completed payment, membership choice | checkout and purchase when a transaction exists | non-transactional pledge or volunteer milestones |

## Page Roles

Identify each page or component role before choosing events:

- entry and orientation;
- discovery and comparison;
- detail and reassurance;
- conversion start or progression;
- conversion success;
- account or support;
- diagnostic failure state.

## Decision Record

For every event family, state:

- business question and analysis use;
- evidence and confidence;
- official event considered;
- parameter family and data availability;
- implementation owner;
- privacy and cardinality concerns;
- reason for exclusion when not tracked.
