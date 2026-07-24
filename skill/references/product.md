# Product Contract

## North Star

Turn live website exploration and all available business, design, and technical
evidence into a complete, adapted, and implementation-ready GA4 tracking plan
for the real user journeys. Use current official GA4 events, parameters,
semantics, and wording first; introduce precise custom elements only where
official constructs cannot represent a meaningful business need. Deliver the
result, in the supplied template or the skill's default template, as a clear
and just-enough human contract that web analysts can review and maintain and
developers can implement directly through the dataLayer.

## Product Identity

The skill is a utility-first, heavy operational web-analysis workflow. It is
not a lightweight event generator. Completeness means covering the meaningful
journeys and measurement needs in scope, not maximizing rows, events,
parameters, notes, or governance metadata.

Use one adaptive workflow and one quality standard. Do not create execution
tiers for small, large, simple, standard, enterprise, or complete plans.
Activate only the capabilities relevant to the actual task.

## Primary Users

- Web analysts must be able to understand, double-check, edit, compare, and
  maintain the measurement model.
- Developers must be able to identify exactly what to push, when to push it,
  which values belong to the event, and where those values come from.

Marketing, product, ecommerce, content, and media stakeholders are secondary
readers.

## Human Deliverable

The human tracking plan is the product. Its authoritative unit is an event
specification containing:

- journey and event name;
- official or custom classification;
- precise definition;
- concrete website trigger;
- pages, routes, states, or components;
- event-specific parameters only;
- parameter scope, type, requirement, condition, definition, values, example,
  and implementation path;
- one quoted dataLayer example.

The Event Matrix, Parameter Reference, event tabs, and optional exports are
derived views of that same event specification. None is a separately authored
source of truth.

## Internal Work

Keep these internal unless an exception changes implementation or the user
requests them:

- evidence status and confidence;
- source conflicts and assumptions;
- browser logs and official-source checks;
- ownership and confirmation responsibility;
- GA4 registration decisions;
- privacy, consent, and cardinality review;
- agent reasoning and validation traces.

## Acceptance Test

The result is ready when:

1. Meaningful in-scope journeys are covered or their unresolved boundary is
   stated without fabricated site behavior.
2. Official semantics are current and correctly applied.
3. Custom semantics have a concrete official gap and business need.
4. Each event contains only its own parameters.
5. Definitions, triggers, value rules, and dataLayer examples agree.
6. An analyst can review or change the plan without understanding the internal
   machinery.
7. A developer can implement the dataLayer without inventing missing
   semantics.
8. The workbook contains no unnecessary reading barriers.

## Non-Goals

Do not:

- configure, publish, audit, or clean GTM;
- execute runtime QA, Preview, DebugView, or network recette;
- create plans for another analytics platform;
- make legal or privacy approval decisions;
- copy Universal Analytics structures into GA4;
- expose automatic or enhanced-measurement events as implementation rows;
- treat the workbook as a report about the agent's work.
