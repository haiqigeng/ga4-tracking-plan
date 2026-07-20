# Measurement Coherence Review

Use this reference before finalizing a tracking plan. The goal is to verify
that the plan behaves like a web analyst deliverable, not a list of isolated
events.

## Review Order

For each journey, check:

1. Business role: the journey has a clear business purpose, user intent, and
   success signal.
2. Analysis need: each proposed event answers a reporting, optimization,
   media, product, ecommerce, or diagnostic question.
3. Event role: macro conversions, micro conversions, diagnostics, and context
   events are separated but still explain one measurement flow.
4. Official fit: GA4 automatic, enhanced-measurement, recommended, or
   ecommerce events are used when their semantics match the action.
5. Custom-event fit: each custom event has a business or diagnostic reason that
   official events do not cover cleanly.
6. Parameter synergy: shared business concepts reuse the same parameter names,
   value rules, and controlled values across events.
7. Parameter sufficiency: the selected event's current official parameter table
   is reviewed before any custom field; applicable official fields have a
   reasoned inclusion decision and every custom field identifies the remaining
   official gap.
8. Ecommerce isolation: ecommerce events keep official GA4 ecommerce parameter
   scope and are not mixed with generic interaction-event variables.
9. Not-tracked choices: noisy, duplicate, sensitive, unavailable, or
   non-actionable interactions are explicitly excluded.
10. Screenshot evidence: when screenshots are requested, every event has a
   Screenshot Register row with captured evidence, shared evidence, a blocked
   reason, or a not-needed reason. When screenshots are excluded, the register
   and its rows are absent.
11. Future scale: future pages, markets, components, or funnel variants can
    reuse the event families and parameters without a full redesign.

## Blockers

Do not approve the plan when:

- events have no business question or analysis purpose;
- the same journey is scattered across unrelated blocks without a readable
  grouping;
- custom events replace official GA4 events without a documented reason;
- custom parameters lack a documented official-field review, reporting use,
  source, or governance decision;
- ecommerce events are missing official item, transaction, list, promotion, or
  checkout parameters required for the scenario;
- parameter names change for the same business concept across events;
- requested screenshots or concrete blocked reasons are missing from the Screenshot Register;
- sensitive or user-provided data is hidden in generic parameters;
- Universal Analytics fields are copied into the GA4 schema.

## Output Expectation

The Event Matrix should let a human analyst, developer, or media user
answer these questions quickly:

- What business question does this event answer?
- Which journey and event family does it belong to?
- Which GA4 event should be sent?
- Which parameters and value rules are required?
- What is intentionally not tracked?
- What visual evidence is captured, shared, blocked, or not needed?
