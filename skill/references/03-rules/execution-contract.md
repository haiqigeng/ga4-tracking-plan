# Execution Contract

Use this sequence for every GA4 plan creation or review.

```text
intake and template decision
-> language decision
-> browser preflight and live journey discovery
-> business and analysis brief
-> journey and evidence model
-> official-first event decisions
-> event-specific parameter decisions
-> finite-value evidence
-> dataLayer examples and CMP timing
-> screenshot capture when requested
-> live official-source receipt
-> official semantic resolution
-> validation of the resolved artifact
-> pure workbook rendering or strict template mapping
-> human and fidelity review
```

## 1. Intake

Record the concerned pages or journeys, journey names, URLs, expected actions,
business goals, analysis needs, success signals, known data, constraints, and
output choice. Ask whether a client template, prior plan, naming convention, or
development specification exists.

Choose one template mode:

- `strict_client_template`: supplied template, mapped cell writes only;
- `approved_structural_extension`: supplied template plus explicitly approved
  cloned structure;
- `default_skill_template`: no usable client template.

## 2. Language

Decide website language scope, workbook language, and controlled-value language
separately. Evidence may come from the user, client template, locale routes,
language selector, or rendered website. Multilingual plans use English.
French-only plans may use French human wording and semantic values. Technical
names remain English lowercase ASCII `snake_case`.

When website language is unknown, leave it unknown. An explicit workbook
language does not prove the website language. Use conservative English
controlled values until site or client evidence resolves the language.

## 3. Website Evidence

Inspect the eligible default browser and Playwright availability. Use rendered
browser exploration for dynamic, form, checkout, signup, and account journeys.
Unless excluded by the user, attempt safe synthetic signup and authenticated
exploration. Static discovery, sitemap, and robots evidence may supplement the
browser but cannot complete a partial or blocked rendered investigation.

Record discovery as `completed`, `partial`, or `blocked`, with attempted and
usable page counts and a delivery notice. Do not infer gated behavior that was
not observed. Keep applicable official or governed recurrent events as
recommendations with structured basis and confirmation ownership.

## 4. Measurement Design

Build a journey-level brief before writing event rows. Events must support a
business, reporting, optimization, implementation, or diagnostic need and be
easy to identify as part of the same journey.

Resolve event choice in this order:

1. automatic or enhanced measurement;
2. recommended GA4 event;
3. recommended ecommerce event;
4. custom event with documented official alternatives and business reason.

For whole-site plans, reconcile live evidence with the relevant scenario rules.
Blocked access does not justify silently omitting common applicable branches.
Recommendations must not claim observation or high confidence.

## 5. Parameter Design

For each event, include:

1. unconditional official requirements;
2. conditional official requirements whose conditions apply;
3. optional official parameters with a concrete need;
4. custom parameters with clear scope, ownership, privacy, and use.

Requiredness and availability belong to the event binding. Unavailable data is
a development dependency, not permission to drop a mandatory parameter.
Official ecommerce requiredness is event-specific. `items` is required only
when the current event table requires it or the analyst selects item detail for
that event; each sent item needs `item_id` or `item_name`.

Exhaust practical finite domains from rendered website or client evidence.
Never present inferred values as observed. Use rules for item IDs, product
names, transaction IDs, URLs, search terms, free text, or other dynamic values.

## 6. Wording And Official Truth

For every official event and parameter, record an exact official source ID,
section, and locator. Event summaries use the official definition. Automatic
and enhanced-measurement trigger bases use the official `Triggered...` row.
Recommended and ecommerce trigger bases use the applicable official event or
implementation section. Parameter definitions and conditions come from that
parameter's row and attached notes.

The website trigger remains separate and states the concrete action or state,
timing, success or failure condition where relevant, and repeat behavior.
Custom wording follows the same concise style. Empty, generic, or tautological
text is invalid; no field is judged by arbitrary word count.

## 7. DataLayer

The canonical implementation state is:

- selected event parameter bindings;
- one `data_layer.push` example per manual event;
- a native/no-manual-push decision where GA4 collects the event itself.

Do not store a duplicate GA4 payload or ecommerce profile in the plan. Derive
GA4 mapping and row order from event name, bindings, and dataLayer.

For manual events, the top-level `event` string is the final GA4 event name.
Use only `page`, `event_data`, `ecommerce`, and `user` wrappers; inner keys
match final GA4 names. Page/core context may omit `event` and uses
`core_context_before_cmp_ready`. Other manual events use `after_cmp_ready`.

## 8. Screenshots

Design events first. If screenshots are requested, attempt Playwright MCP unless
the requester supplied final files. Use representative evidence for repetitive
generic events and all material visible scenarios for finite interactions.
Captured interaction evidence uses a bold red rectangle and no overlay text.
Blocked or partial capture needs a visible notice; missing files cannot be
presented as captured.

## 9. Publication Pipeline

Run the live source check against the draft and create a receipt:

```powershell
python scripts/check_official_catalog.py --plan draft-plan.json --receipt official-source-receipt.json
```

Resolve official semantics into a new artifact:

```powershell
python scripts/resolve_tracking_plan.py draft-plan.json --receipt official-source-receipt.json --output resolved-plan.json
```

Validate and render that exact artifact:

```powershell
python scripts/validate_tracking_plan.py resolved-plan.json
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output tracking-plan.xlsx
```

The receipt must be live, dated on publication day, cover every official plan
URL, match the bundled catalog signature, bind the checked draft hash and the
resolved artifact hash, and have no errors. Offline checks do not authorize
delivery. The renderer performs no semantic enrichment or repair.

For a client workbook, replace the final command with strict adaptation and
deliver the fidelity report. Unsupported workbook features block adaptation;
do not improvise another backend.

## 10. Boundary

Deliver the tracking plan and stop. GTM implementation, publication, container
audit, Preview, DebugView, and network recette belong to other skills.
