# QA Contract Reference

Use this reference when creating a tracking plan that should later support manual recette, GTM Preview checks, DebugView checks, browser network validation, or an automated testing skill.

## Required QA Fields

Each testable event should have:

- `event_id`: stable identifier used in the plan and QA evidence.
- `qa_id`: stable test case identifier.
- `methods`: `DebugView`, `GTM Preview`, `Network`, or another agreed method.
- `steps`: concise reproduction steps.
- `expected_data_layer`: expected keys and values at the trigger point.
- `expected_network`: GA4 request expectations such as event name and key parameters.
- `debugview_expectation`: what the analyst should see in GA4 DebugView.
- `status`: `OK`, `KO`, `Cannot test`, or `not_started` in JSON drafts.
- `evidence`: screenshot path, video path, request export, or notes when tests are executed.

## Status Meaning

| Status | Meaning |
|---|---|
| `OK` | Implemented and validated as expected |
| `KO` | Implemented but missing, wrong, duplicated, or using unexpected values |
| `Cannot test` | Blocked by access, consent, environment, data availability, or unavailable journey |
| `not_started` | JSON planning status before manual or automated QA begins |

## Future Testing Skill Expectations

- The tracking plan should provide enough information to identify a page or journey, reproduce the event, inspect the dataLayer, and verify GA4 network payloads.
- Expected network checks should reference the event name and important parameters, not only screenshots.
- Ecommerce QA should verify official ecommerce fields and the `items` array.
- Consent-sensitive events should document whether testing requires granted, denied, or mixed consent states.
- Test evidence should stay outside the generic skill repository unless it is a generic fixture.

