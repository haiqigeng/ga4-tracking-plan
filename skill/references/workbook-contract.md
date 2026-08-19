# Human Workbook Contract

## Supplied Template

A supplied workbook is the delivery contract. Inspect its sheets, tables,
event tabs, parameter dictionary, formulas, validations, styles, images, and
print settings. Map tracking-plan semantics into the corresponding regions.

- Preserve unrelated content and formatting.
- Do not add tabs, columns, or redesigned sections without approval.
- Use semantic table and field mappings rather than a fixed list of unrelated
  cell writes.
- Assign the mapped parameter registry `all_used_parameters` by default. Use
  `custom_parameters_only` only when the template's intended semantic role is
  explicitly confirmed; a sheet title alone is not sufficient evidence.
- Keep a before/after fidelity report internal.
- If essential information has no legitimate location, report the exact
  conflict instead of silently redesigning the workbook.
- After saving, validate the Event Matrix, parameter registry, mapped event
  tabs, and dataLayer regions against the same canonical event objects.
- Reject overlapping merged-cell ranges after saving; Excel repairs such
  overlaps by removing records even when a Python workbook reader accepts the
  package.

Inspect to a validated `schema-template-map.json` bound to the exact template
SHA-256. Each repeating region records its semantic role, sheet and fields,
exact existing writable value cells, protected formula cells, prototype row,
capacity, approved growth policy, table/total binding, permitted structural
changes and overflow policy. Event-tab cloning is allowed only from an
explicit hidden prototype. Automatic mapping may proceed when unique; equal-
plausibility regions, formula/value conflicts, an uncertain dataLayer
location, insufficient fixed capacity, or missing prototype require an exact
review boundary.

Before mutation, inventory formulas, names, tables, validations, conditional
formatting, charts, drawings, images, pivots, slicers, external links, custom
XML, macros, workbook/sheet/view and print properties. Use the ordinary writer
only for tested-safe XLSX structures. Route supported rich Windows workbooks
to native Excel with macros disabled, external-link updates off and
calculation manual during mutation. If the required writer is unavailable or
a feature is unsupported/unverified, refuse with the feature, location,
reason and sanctioned next step. Never emit a simplified fallback.

For an existing mapped cell, authorise only its intended value and, where
declared, hyperlink. Continue comparing formula status/type, font, fill,
border, alignment/wrapping, number format, protection and comments. An
approved table or prototype expansion must preserve formulas, totals, table
style, validation, conditional formatting, names, filters and row layout.
Fidelity after saving has three independent layers: canonical semantic parity,
complete unsampled structural comparison, and OOXML package-part/protected-
binary comparison. A masked rendered-layout smoke test is additional evidence
only when a deterministic renderer is available; it is never the primary
gate.

## Default Template

When no template is supplied, use `assets/default-tracking-plan.xlsx`. It has:

- `Guide`: concise document information, project-specific dataLayer
  convention, and links for analysts and developers;
- `Event Matrix`: one row per event or context push, with only its technical
  name and definition;
- `Parameter Reference`: the deduplicated dictionary of parameters actually
  used;
- one detailed tab per event, cloned from the hidden event template;
- `Change Log` only for maintenance deliveries;
- screenshot content only when requested or materially useful.

Do not add generic GTM installation lessons, agent instructions, evidence
registers, automatic/enhanced-measurement guidance, advertising guidance, or
generic consent tutorials.

## Event Matrix

Show only:

- event;
- definition.

Do not show journey, classification, trigger, locations, variables, inherited
context, evidence status, confidence, availability, ownership, privacy,
registration, or implementation progress. Those semantics remain in the
canonical model and the event specification where useful.

## Parameter Reference

Show only:

- variable name;
- scope;
- type;
- definition;
- rule;
- possible values or example.

Do not show:

- display name;
- availability by event;
- data owner;
- registration in GA4;
- privacy, consent, or cardinality;
- agent or research metadata.

## Event Tabs

Each event tab contains:

1. event name and journey;
2. definition;
3. trigger;
4. relevant pages, routes, states, or components;
5. a parameter table with:
   - name;
   - scope;
   - type;
   - requirement;
   - definition;
   - rule;
   - possible values or example;
6. one complete dataLayer example with quoted keys;
7. only event-specific implementation notes.

Keep parameter conditions, source logic, destinations, classifications, and
dataLayer paths in the hidden canonical model. They drive validation and
maintenance but are not visible columns in the default workbook. A supplied
template may retain them when it explicitly provides legitimate locations.
The default event-sheet template may retain its classification row only as a
hidden projection safeguard; generated event tabs must keep that row hidden.

The event tab, Event Matrix, and Parameter Reference are derived from the same
event object and must never be maintained independently.

Generated and adapted workbooks contain a very-hidden canonical model and a
very-hidden visible projection. These are maintenance safeguards, not human
content. If visible cells change, import must either reconcile supported
event-tab edits into canonical JSON or stop with exact conflicts. Event names,
journey membership, locations, parameter identity or scope, wrapper structure,
and dataLayer keys are structural and must be changed in canonical JSON.
Report structural conflicts precisely; do not auto-merge ambiguous additions,
removals, or renames merely because they were visible in a workbook.

Internal `business_question` values justify the event model during design and
coherence review. Do not expose them as a default workbook column or section.

## Language

Localize human labels, definitions, triggers, conditions, and semantic values
to the chosen workbook language. Keep technical event names, parameter names,
wrapper names, paths, codes, and official identifiers unchanged.

## Change Log

For maintenance, add a concise derived sheet containing:

- added, changed, or deprecated journey/event/parameter/value;
- affected event or path;
- plain-language change;
- previous and new value where useful.

Always deliver the complete updated workbook as the current source of truth.

## Human Review

At normal zoom, verify that:

- analysts can scan the event list and definitions without horizontal
  obstruction;
- developers can move directly from an event to its parameter table and
  dataLayer example;
- long definitions and code wrap without hiding content;
- event tabs and dictionary values agree;
- no unused or internal columns are present.
