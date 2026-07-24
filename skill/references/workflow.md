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
- do not place a paid order or create an irreversible financial commitment;
- inspect authenticated areas when public self-registration succeeds;
- enumerate visible finite menus, filters, form options, shipping tiers,
  payment types, markets, languages, and other stable domains;
- record blocked boundaries without inventing hidden pages, values, or
  triggers.

Static HTML, sitemaps, robots files, and URL exports support coverage but do not
replace rendered interaction.

Do not automatically turn a blocked capability into a visible event
recommendation. Include an unobserved journey only when user, business,
design, technical, or historical evidence confirms that it belongs to the
target plan. Otherwise keep it as an internal discovery gap.

## 4. Build The Journey Model

For each journey, determine:

- user intent;
- business purpose and success;
- meaningful progression and failure states;
- decisions analysts will make from the data;
- implementation components and data sources.

Separate business outcomes, progression signals, and diagnostics. Avoid click
inventories and event-per-element designs.

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
- exact and official-like wording;
- no inherited or unrelated parameters;
- human readability;
- supplied-template fidelity.

## 8. Maintain Existing Plans

When a previous plan is supplied:

1. import or reconstruct its semantic model;
2. compare it with new evidence and the updated specification;
3. identify journey, event, trigger, parameter, value, and dataLayer changes;
4. preserve human edits that do not conflict with the new target;
5. deliver a complete consolidated workbook;
6. include a concise change log;
7. never make an addendum the only current source of truth.

The default workbook can be imported automatically. For another client
template, recognize its semantic regions and use analyst judgement to map it.

## 9. Screenshots

Screenshots are conditional. Capture them only when requested or when a visual
reference materially removes implementation ambiguity. Keep screenshot
metadata internal; place a useful visual in the corresponding event
specification or an explicitly requested evidence sheet.
