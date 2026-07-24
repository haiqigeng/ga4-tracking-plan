# Human Workbook Contract

## Supplied Template

A supplied workbook is the delivery contract. Inspect its sheets, tables,
event tabs, parameter dictionary, formulas, validations, styles, images, and
print settings. Map tracking-plan semantics into the corresponding regions.

- Preserve unrelated content and formatting.
- Do not add tabs, columns, or redesigned sections without approval.
- Use semantic table and field mappings rather than a fixed list of unrelated
  cell writes.
- Keep a before/after fidelity report internal.
- If essential information has no legitimate location, report the exact
  conflict instead of silently redesigning the workbook.

## Default Template

When no template is supplied, use `assets/default-tracking-plan.xlsx`. It has:

- `Guide`: concise document information, project-specific dataLayer
  convention, and links for analysts and developers;
- `Event Matrix`: one row per event or context push;
- `Parameter Reference`: the deduplicated dictionary of parameters actually
  used;
- one detailed tab per event, cloned from the hidden event template;
- `Change Log` only for maintenance deliveries;
- screenshot content only when requested or materially useful.

Do not add generic GTM installation lessons, agent instructions, evidence
registers, automatic/enhanced-measurement guidance, advertising guidance, or
generic consent tutorials.

## Event Matrix

Show:

- journey;
- event;
- official, official ecommerce, custom, or context classification;
- definition;
- website-specific trigger;
- pages, routes, or components;
- event-specific variables with their requirement.

Do not show inherited variables, evidence status, confidence, availability,
ownership, privacy, registration, or implementation progress.

## Parameter Reference

Show only:

- variable name;
- scope;
- type;
- definition;
- example;
- exhaustive values or value rule;
- concerned events.

Do not show:

- display name;
- availability by event;
- data owner;
- registration in GA4;
- privacy, consent, or cardinality;
- agent or research metadata.

Concerned events contains event names only.

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
   - separate condition;
   - definition;
   - values or rule;
   - example;
   - dataLayer path or implementation source;
6. one complete dataLayer example with quoted keys;
7. only event-specific implementation notes.

The event tab, Event Matrix, and Parameter Reference are derived from the same
event object and must never be maintained independently.

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

- analysts can scan journeys and events without horizontal obstruction;
- developers can move directly from an event to its parameter table and
  dataLayer example;
- long definitions and code wrap without hiding content;
- event tabs and dictionary values agree;
- no unused or internal columns are present.
