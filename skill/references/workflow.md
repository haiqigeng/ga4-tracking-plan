# Adaptive Operational Workflow

Use this workflow for every creation, review, adaptation, or maintenance task.
The quality standard does not change with scope. Conditional capabilities
activate only when relevant.

## 1. Resolve The Delivery Context

Determine:

- in-scope website, pages, journeys, markets, and target state;
- supplied workbook or default template;
- prior plan, GTM export, naming convention, or dataLayer specification;
- explicit workbook language and project working language;
- screenshots requested or not;
- current-state, future-state, or hybrid plan.

Language priority:

1. explicit user choice;
2. supplied template;
3. project team's working language;
4. primary analyst and developer audience;
5. website language as supporting evidence.

Never force English merely because a website is multilingual. Technical event,
parameter, wrapper, and dataLayer names remain English lowercase `snake_case`.
If priorities 1 through 4 are genuinely unknown, use the dominant language of
the in-scope website and record that decision internally.

## 2. Ingest Evidence By Role

Treat sources as first-class only for what they can establish:

| Source | Evidence role |
| --- | --- |
| Live rendered website | Current user experience, interactions, visible values |
| User or business brief | Required outcomes, priorities, intended use |
| Figma or design specification | Intended future experience |
| GTM export or dataLayer evidence | Current implementation |
| Backend, API, CMS, or technical specification | Data capability and source logic |
| Previous tracking plan | Historical or approved contract |
| Analytics export | Current data use and implementation symptoms |

Internally record whether evidence describes `as_is`, `to_be`, or both. When
sources conflict, resolve the conflict according to the plan's target state and
keep the difference in the internal analysis context. Do not assign generic
primary/secondary weights.

Use `schema-analysis-context.json` as the checkpoint contract. Record source
IDs and hashes when available, material journey coverage, explicit gaps and
their disposition, and finite or dynamic value domains. Validate this context
against the canonical plan before delivery. This checkpoint is resumable
internal evidence, not another visible workbook sheet.

## 3. Explore The Real Journeys

Actively discover an interactive Playwright MCP or browser. Rendered
investigation is required for dynamic menus, forms, search, filters, carts,
checkout, accounts, modals, and SPAs.

During investigation:

- accept the CMP choice needed to make the journey functional;
- use clearly synthetic names, email addresses, telephone numbers, addresses,
  and other form values;
- submit safe public forms and account flows when needed to observe the real
  journey, unless the user opts out;
- use clearly non-routable or reserved synthetic contact values wherever the
  form accepts them, and never impersonate a real person;
- do not place a paid order or create an irreversible financial commitment;
- stop before appointments, contracts, fulfilment requests, or other
  operational commitments that cannot be safely cancelled;
- inspect authenticated areas when public self-registration succeeds;
- enumerate visible finite menus, filters, form options, shipping tiers,
  payment types, markets, languages, and other stable domains;
- inspect existing dataLayer pushes and identify GTM containers, Google tags,
  and GA4 measurement IDs as internal implementation evidence;
- record blocked boundaries without inventing hidden pages, values, or
  triggers.

Static HTML, sitemaps, robots files, and URL exports support coverage but do not
replace rendered interaction.

Build a candidate universe before sampling. Seed it from the root, supplied
journey URLs, robots and sitemaps, then rendered links. Prioritize materially
different funnels and page templates rather than link order. Report the page
and sitemap caps, candidate count, unvisited high-priority URLs, and an
observed/partial/blocked ledger. A cap or material unvisited candidate prevents
a completeness claim.

For controlled gated evidence, use an explicit interaction recipe. Accept the
privacy statement by default, fill only declared synthetic value kinds, and
capture dataLayer pushes and GA4 request names for each action window. Require
explicit authorization before submitting a non-transactional lead,
authentication, or search form. Never submit a purchase or payment
confirmation. This is discovery evidence, not runtime certification.

Do not automatically turn a blocked capability into a visible event
recommendation. Include an unobserved journey only when user, business,
design, technical, or historical evidence confirms that it belongs to the
target plan. Otherwise keep it as an internal discovery gap.

## 4. Build The Journey Model

Start with an evidence-backed working hypothesis of how the in-scope business
creates value and which user outcomes matter. Keep it proportional: a short
statement and a small set of concrete questions are enough when the evidence
is simple. Do not create a scoring framework, mandatory canvas, or separate
stakeholder artifact.

For each journey, determine:

- representative entry points and user intent;
- business purpose, value, and successful outcome;
- material alternate funnel shapes, templates, components, or user states
  when they change what should be measured;
- meaningful progression, abandonment boundaries, failures, empty states, and
  post-conversion states;
- concrete questions or decisions the resulting data must support;
- implementation components and data sources.

Classify what is observed live, confirmed by another source, planned, or
blocked so an unvisited state is never silently treated as observed behavior.
Capture this distinction internally rather than adding workbook columns.

Separate business outcomes, progression signals, and diagnostics. Avoid click
inventories and event-per-element designs.

For every proposed non-context event, record one internal
`business_question` that states why the event deserves to exist. A context push
is exempt because it carries reusable implementation state rather than
representing a user action or business outcome. If two events fire at the same
moment, keep both only when their distinct purposes and semantics are clear.

## 5. Design Events And Parameters

Follow `official-first.md`. Resolve the selected official event and its complete
parameter table before custom design. Keep every event's parameter contract
specific to that event.

## 6. Specify The dataLayer

Follow an evidenced existing convention when present. Otherwise use:

- top-level `"event"` for a manually implemented event;
- `"page"` for reusable page state;
- `"event_data"` for ordinary interaction or outcome data;
- `"ecommerce"` for GA4 ecommerce data;
- `"user"` for user or account state.

Send reusable `"page"` and `"user"` state together in one core context push
whenever they are available at the same page or route lifecycle moment. A
context push has no `"event"` key. Do not split page context and user context
into separate default pushes.

For authenticated journeys, expose `user.user_id` in that core context and map
it to the GA4 User-ID configuration setting. Do not map `user_id` as a user
property or ordinary event parameter. Do not send it before a user has signed
in; send the stable first-party identifier while signed in and clear the
setting with `null` after sign-out.

Use JSON-style quoted keys in every human example. Clear stale wrapper state
when the client implementation requires it. Never generate an event row
without a complete example, except a context push intentionally lacking an
`"event"` key.

## 7. Validate And Render

Run hard semantic validation, then render from the validated event
specifications. Check:

- official and custom fit;
- event/parameter scope and requiredness;
- dataLayer parity;
- finite values;
- one combined page-and-user core context;
- official User-ID destination handling;
- `customer_type` on `purchase`;
- GA4 collection and custom-definition budgets;
- exact and official-like wording;
- no inherited or unrelated parameters;
- every non-context event has a concrete internal business question;
- exact trigger overlaps are reconciled or intentionally justified;
- the same parameter name and scope retain compatible meaning, type, and
  destination across events;
- list, item, currency, value, intent, outcome, and deduplication logic remain
  coherent across the full journey;
- human readability;
- supplied-template fidelity.

Delivery is strict: schema errors and warnings, unresolved material coverage,
official-source failures, visible-workbook drift, generated-schema failures,
and supplied-template fidelity violations all block the bundle. The atomic
builder writes only after every gate passes and emits:

- the lean workbook and canonical plan;
- expected events and one exact push schema per event;
- current official-source verification;
- shared versioned contract schemas;
- a handoff with approval state, plan and artifact hashes, language, target
  sites, and upstream evidence;
- internal analysis context plus applicable semantic diff, drift, impact, and
  template-fidelity reports.

Code should enforce only objective invariants and flag exact overlaps. Use
analyst reasoning for contextual questions such as whether a progression event
is useful, two simultaneous events express different outcomes, or a journey
variant changes measurement. Review and resolve all validator warnings before
delivery; do not expose the review machinery in the workbook.

## 8. Maintain Existing Plans

When a previous plan is supplied:

1. import or reconstruct its semantic model;
   if an embedded model and visible workbook differ, reconcile only supported
   event-tab fields and reject structural changes outside canonical JSON;
2. compare it with new evidence and the updated specification;
3. identify journey, event, trigger, parameter, value, and dataLayer changes;
4. preserve human edits that do not conflict with the new target;
5. deliver a complete consolidated workbook;
6. include a concise change log;
7. never make an addendum the only current source of truth.

The default workbook can be imported automatically. For another client
template, recognize its semantic regions and use analyst judgement to map it.
Mappings are bound to the inspected workbook SHA-256. Reuse a mapping only
when the template hash still matches. Never repurpose a populated event tab
for another event unless the mapping explicitly marks it reusable.

When a previous analysis context exists, detect source, journey coverage,
coverage-gap, and finite-domain drift, then identify potentially affected
events. For a declared business change, resolve its journey, event, parameter,
or value-domain selectors into affected workbook tabs, canonical semantics,
event schemas, expected events, and downstream recette scenarios. Neither
utility changes or approves the plan automatically.

## 9. Screenshots

Screenshots are conditional. Capture them only when requested or when a visual
reference materially removes implementation ambiguity. Keep screenshot
metadata internal; place a useful visual in the corresponding event
specification or an explicitly requested evidence sheet.
