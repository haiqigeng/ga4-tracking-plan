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

## Optional Measurement-Framework Intake

A supplied measurement framework is structured upstream business evidence,
not an implementation authority. Use it to prioritize investigation, establish
a presumption of materiality for applicable journeys and requirements, and
formulate business questions and semantic facts to verify. The framework
creates a duty to investigate and decide, not a duty to implement.

The tracking-plan skill remains responsible for independent live, design, and
technical discovery; scope applicability; official GA4 evaluation; event and
parameter design; triggers; value domains; dataLayer specifications; and the
final human deliverable. Framework absence never proves that an independently
discovered journey is immaterial, and framework presence never proves that a
journey exists or belongs in client-side GA4.

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
- parameter scope, type, requirement, definition, rule, and possible values or example;
- one quoted dataLayer example.

The canonical machine event also retains its concrete business question plus
measurement-opportunity links, parameter conditions, classifications,
destinations, sources, value-domain decisions, and dataLayer paths for
validation and maintenance. Those internal fields are not automatically
visible workbook columns.

The Event Matrix, Parameter Reference, event tabs, and optional exports are
derived views of that same event specification. None is a separately authored
source of truth.

The standard delivery separates audiences without expanding the workbook:

- `tracking-plan.xlsx` for analysts and developers;
- `plan.json` as the canonical semantic model;
- `expected-events.json` and `schemas/<event>.schema.json` for implementation
  and downstream acceptance tooling;
- `handoff.json` for version, approval, artifact hashes, and upstream evidence;
- the original hash-bound rendered discovery report;
- `internal/analysis-context.json` and official, drift, impact, or fidelity
  evidence for machine checks and analyst maintenance.

## Internal Work

Keep these internal unless an exception changes implementation or the user
requests them:

- evidence status and confidence;
- source conflicts and assumptions;
- browser logs and official-source checks;
- business-value hypotheses, journey-variant notes, and event business
  questions;
- ownership and confirmation responsibility;
- GA4 registration decisions;
- privacy, consent, and cardinality review;
- agent reasoning and validation traces.

## Acceptance Test

The result is ready when:

1. Meaningful in-scope journeys, material variants, failures, empty states,
   and post-conversion states are covered or their unresolved boundary is
   stated without fabricated site behavior.
2. Every material journey has a resolved measurement-opportunity ledger, every
   generated interaction-family candidate has an explicit measure,
   covered-elsewhere, or exclude decision, every measured opportunity maps to
   an event, and every
   non-context event maps back to a concrete opportunity.
3. Official semantics are current and correctly applied.
4. Custom semantics have a concrete official gap and business need.
5. Each event contains only its own parameters.
6. Definitions, triggers, value rules, and dataLayer examples agree.
7. An analyst can review or change the plan without understanding the internal
   machinery.
8. A developer can implement the dataLayer without inventing missing
   semantics.
9. The workbook contains no unnecessary reading barriers.
10. Every non-context event supports a concrete internal business question, and
   overlapping purposes or triggers have been reconciled across the plan.
11. Parameter meaning, scope, type, destination, and journey-level commerce or
   outcome logic are coherent across events.
12. Page and user context share one core context push, and any authenticated
   User-ID is mapped as a GA4 configuration setting rather than an event
   parameter or user property.
13. Material journey coverage and every finite or dynamic value-domain
    decision are backed by the validated analysis context; not-tested,
    partial, and externally blocked states are explicit and distinct from
    analyst resolution.
14. Every discovery hint and journey is bound to the current run ID and report
    hash, then mapped to an explicit opportunity or coverage row. Every
    controlled finite value has one localized label, and no sampled or
    disagreeing control set is described as exhaustive.
15. The rendered workbook, event schemas, expected-events contract, official
    check, and hash-stamped handoff all validate as one delivery.
16. Visible workbook edits cannot be silently overridden by an older embedded
    model, supplied-template content outside mapped regions is unchanged, and
    every mapped semantic region matches the canonical model.
17. When a measurement framework is supplied, every applicable material
    journey or web-measurement requirement is investigated and dispositioned,
    while the normal discovery process remains able to add needs absent from
    that framework.
18. Supplied or observed authenticated roles are rediscovered independently
    after login, session and consequential boundaries are explicit, and no
    factual progression, submission or success state outruns its direct
    evidence.
19. A supplied template passes a SHA-bound mapping/capacity gate, writer
    preflight, canonical semantic parity, complete structural comparison and
    package preservation checks; unsupported richness causes an exact refusal,
    never silent degradation.

## Non-Goals

Do not:

- configure, publish, audit, or clean GTM;
- execute runtime QA, Preview, DebugView, or network recette;
- create plans for another analytics platform;
- make legal or privacy approval decisions;
- copy Universal Analytics structures into GA4;
- expose automatic or enhanced-measurement events as implementation rows;
- treat the workbook as a report about the agent's work.
