# Discovery And Coverage Closure

Use this reference for every greenfield or materially changed plan. A whole-site
request is a journey-coverage problem, not a request to crawl every URL.

## Discovery Loop

1. Build a broad candidate universe from the root, user-supplied entries,
   robots, all reachable sitemap branches, navigation, footer, and rendered
   links. Preserve link text and component evidence even when the URL was
   already found in a sitemap.
2. Classify page purpose from weighted route, title, headings, main content,
   and local component evidence. Ignore global header/footer copy, use
   whole-word multilingual matching, and retain an `unknown` result with
   competing candidates when evidence is ambiguous. Group candidates by
   business journey, page archetype, route family, and interaction family.
   Repeated product or article URLs do not count as new
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
7. Inventory bounded interaction families such as tabbed forms, locator
   selection, coupon application, FAQ accordions, meaningful downloads,
   business-process errors, modals, and filter/sort application. Record one
   decision per family and variant, not one event per control.
8. Stop only when each material journey, variant, and interaction family is
   observed, confirmed by another source, deliberately excluded, or bounded
   with a concrete gap. Never translate `partial` into `complete` in the
   delivery message.

A structurally valid `partial` report is successful discovery output: continue
with it, expose its explicit gaps, and resolve them in the analysis context.
Only `blocked`, where no usable rendered evidence exists, stops the pipeline.

Use factual boundary states precisely: `not_tested` for work not attempted or
outside the sampling budget, `partial` for evidence that covers only part of a
journey, and `externally_blocked` for an evidenced CAPTCHA, access, browser, or
technical barrier. Analyst resolutions such as excluded or confirmed
elsewhere are separate fields; they must not rewrite the factual state.

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
control or diagnostic. Candidates do not imply measurement, but every
generated candidate must still receive a measure/exclude decision before
delivery. The analyst measures it only when a real business question justifies
it; exclusion is a valid closure.

Run `build_analysis_context_seed.py` against the original discovery report.
It creates one unresolved opportunity for every hint and records the exact
report hash and inventories. Delivery must receive that same report and blocks
on a hash mismatch, an omitted hint, journey, or variant, or an unresolved
opportunity. This is the mechanical closure between exploration and analyst
reasoning; it does not automate the measure/exclude decision. Once a decision
is made, seed placeholders are invalid. A manually added measured opportunity
based on live evidence must retain an exact URL, route, component, or evidence
locator.

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
