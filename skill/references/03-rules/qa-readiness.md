# QA Contract Reference

Use this reference when creating a tracking plan that should later support manual recette, GTM Preview checks, DebugView checks, browser network validation, or an automated testing skill.

## Required QA Fields

When the user asks for QA/recette preparation, each testable event should have:

- `methods`: `DebugView`, `GTM Preview`, `Network`, or another agreed method.
- `steps`: concise reproduction steps.
- `expected_data_layer`: expected keys and values at the trigger point.
- `expected_network`: platform request expectations that explicitly mention the event name and key parameters/properties.
- `debugview_expectation`: what the analyst should see in GA4 DebugView.
- `status`: `OK`, `KO`, `Cannot test`, or `not_started` in JSON drafts.
- `evidence`: execution evidence reference, request export, or notes when tests are executed. The future QA/recette skill can decide how to store screenshot/video artifacts.

Do not expose `event_id`, `screenshot_id`, `qa_id`, or tracking-row identifiers
in the analyst-facing Event Matrix. If a future QA/recette skill needs IDs, it
can generate them during QA execution or use structured JSON fields internally.

## Status Meaning

| Status | Meaning |
|---|---|
| `OK` | Implemented and validated as expected |
| `KO` | Implemented but missing, wrong, duplicated, or using unexpected values |
| `Cannot test` | Blocked by access, environment, data availability, or unavailable journey |
| `not_started` | JSON planning status before manual or automated QA begins |

## Future Testing Skill Expectations

- The tracking plan should provide enough information to identify a page or journey, reproduce the event, inspect the dataLayer, and verify GA4 network payloads.
- Screenshot Register rows should be generated from the event draft and describe
  event-linked capture objectives, automation cues, and evidence status; they
  should not depend on local file paths.
- Use selective evidence statuses such as `capture_required`, `captured`,
  `shared_evidence`, `not_needed`, or `blocked` instead of assuming every event
  needs its own screenshot.
- Screenshots for click, CTA, filter, menu, form submit, or other interaction
  events should mark the relevant element or zone with a red rectangle or
  equivalent visual callout. Prefer no text label in workbook thumbnails; the
  event row should provide the context.
- Passive render/state screenshots such as `page_view`, `view_item_list`,
  `view_item`, or checkout-step render evidence should stay unannotated unless
  the screenshot is specifically documenting an interaction target.
- Expected network checks must reference the event name and important parameters/properties, not only screenshots.
- Ecommerce QA should verify official ecommerce fields and the `items` array.
- Test evidence should stay outside the generic skill repository unless it is a generic fixture.
