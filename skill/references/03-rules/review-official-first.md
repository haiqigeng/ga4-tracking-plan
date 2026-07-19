# Official-First Review

Use this rule when reviewing an existing plan or translating legacy business
intent into GA4.

## Review Order

1. Identify the business goal, journey, and decision the measurement supports.
2. Separate observed implementation evidence from assumptions and proposals.
3. Check automatic and enhanced-measurement coverage.
4. Check current GA4 recommended and ecommerce events.
5. Accept a custom event only when official semantics do not fit.
6. Verify event and item parameters, scope, availability, ownership, privacy,
   cardinality, and custom-definition need.
7. Produce a live source receipt, resolve a new plan artifact, and validate
   that exact artifact before rendering.
8. Remove Universal Analytics fields, generic wrapper events, and duplicate
   GA4 payload or ecommerce-profile snapshots.
9. Keep only human-useful workbook content.

## Evidence Quality

An event is not justified merely because a button exists. Use website evidence,
client documentation, business requirements, or a clearly labelled analyst
recommendation. Recommendations record a structured basis, confirmation need,
and owner; do not rely on vague prose or arbitrary word counts.

## Human Output

The workbook should let an analyst or developer identify the journey, event,
trigger, parameter paths, expected values, availability, and visual context
without reading internal JSON. Do not include machine identifiers, agent notes,
or runtime testing instructions in visible tabs.
