# Mainstream Analytics Tool Policy

Use this reference when a tracking plan may target GA4, Piano Analytics, or another mainstream analytics platform.

## Platform Selection

- If the user explicitly names the analytics tool, design against that tool first.
- If the user asks for GA4 only, keep the tracking plan GA4-first and use GA4 event names, parameters, custom definitions, and QA expectations.
- If the user asks for Piano Analytics, use Piano event names and properties. Do not translate GA4 event names directly into Piano events.
- If the user asks for both tools, keep one business-event inventory but provide separate platform mappings for each tool when official event models differ.
- If the tool is unknown, default to GA4 only when the user asks for a GA4 tracking plan. Otherwise ask once for the target platform when it materially changes the plan.
- If an example uses Universal Analytics, GAU, GA3, GA360, or UA fields such as `eventCategory`, `eventAction`, `eventLabel`, `nonInteraction`, `dimension1`, or `metric1`, treat it as legacy migration context only. Do not propose UA schema because Universal Analytics is sunset.

## Analyst Decision Flow

For every proposed event:

1. Start with the business question and journey step.
2. Decide whether the action is a macro conversion, micro conversion, diagnostic signal, or noise.
3. Check whether the target platform has an official event that matches the business meaning.
4. Use the official event and property model when it fits.
5. Create a custom event only when the official model does not answer the analysis need cleanly.
6. Document why the event exists, which report or audience it supports, and how it will be tested.

## Cross-Platform Mapping Rules

- Treat "business action" and "analytics event name" as separate concepts.
- The same business action may map to different official event names by platform.
- Keep platform-specific parameter or property names intact. For example, GA4 ecommerce uses `items[].item_id`, while Piano Sales Insights uses product and cart properties such as `product_id` and `cart_id`.
- Do not mix platform-specific ecommerce schemas in the same implementation payload.
- Mark every field as native, recommended, ecommerce, custom, or implementation-specific for the selected platform.
- Do not use Piano event names as GA4 custom events, GA4 ecommerce item names as Piano properties, or UA fields as either GA4 or Piano fields.

## Custom Event Rules

Custom events and properties must be justified by:

- the page, component, or journey step concerned
- the analysis question they answer
- why official events or properties are insufficient
- the controlled values expected, normalized to lowercase ASCII `snake_case` unless the platform requires raw IDs or official values
- reporting registration needs, such as GA4 custom dimensions or Piano Data Model properties
- cardinality and privacy risks
- QA reproduction steps and network expectations

Avoid custom tracking for:

- every visual click with no analysis purpose
- transient UI states that cannot be acted on
- raw user-entered text
- identifiers, contact details, or values that can become personal data without explicit governance

## Future QA Readiness

Design each testable event so a later testing skill can use the plan directly:

- trigger description and reproduction steps
- expected dataLayer or SDK call
- expected network event name and key parameters/properties
- screenshot or evidence placeholder
- status placeholder using `OK`, `KO`, or `Cannot test` only in QA/recette
  outputs, not in the analyst-facing Event Matrix

Do not expose QA-only identifiers such as `event_id`, `screenshot_id`, or
`qa_id` in the tracking-plan Event Matrix.
