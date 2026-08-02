# Discovery And Coverage Closure

Use this reference for every greenfield or materially changed plan. A whole-site
request is a journey-coverage problem, not a request to crawl every URL.

## Discovery Loop

1. Build a broad candidate universe from the root, user-supplied entries,
   robots, all reachable sitemap branches, navigation, footer, and rendered
   links. Preserve link text and component evidence even when the URL was
   already found in a sitemap.
2. Group candidates by business journey, page template, route family, and
   interaction family. Repeated product or article URLs do not count as new
   coverage unless they expose a materially different template or behavior.
3. Render at least one representative of every material group. Inspect menus,
   forms, filters, sorting, variants, promotions, carts, account entry,
   customer service, post-purchase, and conversion paths when present.
4. Use safe synthetic values and complete accessible non-financial flows by
   default unless the user opts out. Accept the privacy statement needed for
   investigation. Never confirm a paid order, payment, contract, appointment,
   or other irreversible commitment.
5. Generate and execute one bounded recipe for every material safe funnel
   variant, not merely the first form found for a journey. Record the outcome
   against that exact variant. Success on a standard quote form does not prove
   success on a two-step landing-page quote form.
6. The rendered helper inspects the coverage ledger after each round and
   automatically continues with unvisited material families until closure or
   the explicit maximum-round boundary. A page limit ends only one round.
7. Stop only when each material journey, variant, and interaction is observed,
   confirmed by another source, deliberately excluded, or bounded with a
   concrete gap. Never translate `partial` into `complete` in the delivery
message.

A structurally valid `partial` report is successful discovery output: continue
with it, expose its explicit gaps, and resolve them in the analysis context.
Only `blocked`, where no usable rendered evidence exists, stops the pipeline.

## Measurement-Opportunity Ledger

Before event selection, create one internal opportunity for each material
business outcome, useful progression signal, or actionable diagnostic found in
the journeys. Examples include:

- a product list impression and product selection;
- filter or sort application when merchandising decisions use it;
- promotion exposure and selection;
- catalogue request start, meaningful progression, and confirmed request;
- newsletter confirmation;
- checkout payment refusal;
- order-history, return, cancellation, or reorder outcomes;
- lead funnel progression and backend-confirmed success.

For each opportunity, record the business question, evidence, official
candidate, fit decision, and final measure/exclude decision. An official event
name is not required for an opportunity to deserve measurement. Conversely, a
visible control is not enough: exclude noise that supports no decision.

Every material journey must reference its opportunity IDs. Every measured
opportunity must map to one or more canonical events, and every non-context
event must map back to at least one measured opportunity. This is the closure
test that prevents both missing custom events and click-inventory inflation.

Discovery hints have two materiality states. `material` means the rendered
journey itself establishes an outcome or progression that needs an explicit
analyst decision. `candidate` means a heuristic found a potentially useful
control or diagnostic. Candidates still need a measure/exclude decision, but
they do not block delivery merely because the pattern was detected; the
analyst promotes them only when a real business question justifies it.

Run `build_analysis_context_seed.py` against the original discovery report.
It creates one unresolved opportunity for every hint and records the exact
report hash and inventories. Delivery must receive that same report and blocks
on a hash mismatch, an omitted hint, journey, or variant, or an unresolved
material opportunity. This is the mechanical closure between exploration and
analyst reasoning; it does not automate the measure/exclude decision.

## Common Whole-Site Families

Use this as a prompt, not a mandatory event list:

- acquisition landing and promotion surfaces;
- navigation, internal search, listings, filters, sorting, pagination;
- product or service detail, options, guides, availability, wishlist;
- cart, checkout, payment failure, purchase;
- lead, quote, catalogue, appointment, newsletter, and contact funnels;
- signup, login, password recovery, account self-service;
- order history, order detail, reorder, return, cancellation, refund;
- store discovery, support, FAQ, content, and business tools.

Absence from the first crawl is not evidence of business non-applicability.
Investigate candidate evidence and record the resolution.
