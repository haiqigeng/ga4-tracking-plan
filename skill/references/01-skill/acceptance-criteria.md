# Acceptance Criteria

A complete GA4 tracking plan must:

- define the concerned pages, journeys, goals, actions, and analysis needs;
- distinguish observed, confirmed, inferred, recommended, and unavailable facts;
- show website-coverage evidence and gaps for broad scopes;
- connect every event to a journey, business question, and analysis use;
- group related events so the journey is easy to read and implement;
- use official GA4 events when their semantics fit;
- verify official events and parameters with a source and checked date;
- justify custom events against official alternatives;
- isolate GA4 ecommerce events and use the official event and item parameters;
- state collection source and duplicate risk for automatic, enhanced, and
  manually collected events;
- reuse parameter names and controlled values consistently;
- exhaust finite website values when practical, format them with ` | ` in human
  output, and use English controlled taxonomies across multilingual markets;
- give every parameter a reporting purpose, value rules, example, availability,
  data owner, registration decision, privacy risk, and cardinality risk;
- highlight sensitive or user-provided data and the validation it requires;
- investigate public signup and authenticated journeys with synthetic
  information through an interactive browser unless the user explicitly opts
  out;
- record blocked authenticated journeys as coverage gaps and propose customer-
  space events only when observed, synthetically observed, or client-confirmed;
- apply the gated-evidence rule to every event, including generic page and
  ecommerce events, rather than only named customer-space custom events;
- define connected-user state once through a shared `user_context` protocol;
  map opaque `user_id` only to the Google tag User-ID setting and govern
  approved low-cardinality GA4 user properties separately from events;
- provide one complete dataLayer example and GTM-to-GA4 mapping per event,
  including official ecommerce reset and `ecommerce.items` structure;
- model payment failure when a payment journey exists and scope custom item
  availability to justified product-detail or persistent-cart use cases;
- consolidate distinct newsletter, contact, catalogue, quote, and other form
  outcomes under `generate_lead` only through a documented business decision;
- cover meaningful authenticated customer-space outcomes beyond login and
  signup when those capabilities exist;
- distinguish backend-confirmed order cancellation from official refund
  completion;
- inspect client templates before adaptation and refuse destructive replacement
  of formulas, protection, tables, validations, comments, or images without
  explicit analyst approval;
- record noisy, duplicate, unavailable, sensitive, or non-actionable choices
  that should not be tracked;
- actively attempt Playwright MCP before final screenshot capture unless final
  images were supplied or screenshots were explicitly excluded;
- provide an explicit screenshot-evidence row for every event, including
  intentional sharing, not-needed, or blocked decisions, and show a concrete
  capture notice whenever evidence is blocked or partial;
- use only `captured`, `shared_evidence`, `not_needed`, or `blocked` as final
  screenshot evidence states;
- use exactly one representative screenshot for repetitive generic events and
  cover every materially different visible scenario for finite events;
- render readable 480 x 270 previews from 16:9 viewport sources, with no image
  labels and only a bold red rectangle where an interaction or state needs one;
- produce a readable workbook whose supporting tabs remain subordinate to the
  Event Matrix.

Mark the plan incomplete when it copies Universal Analytics fields, invents
unavailable data, omits required ecommerce structure, hides sensitive data,
uses generic click events without business value, or has no coverage evidence
for a whole-site request.
