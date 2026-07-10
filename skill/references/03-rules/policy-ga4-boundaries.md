# GA4 Scope Boundaries

Use this rule for every plan created or reviewed by the skill.

## Supported Target

The skill produces GA4 web tracking plans. Use GTM and a dataLayer as the
default implementation model when the user does not provide another GA4
collection context.

The skill can learn business intent, workbook readability, journey grouping,
and implementation habits from historical plans. It must not copy event names,
parameters, payloads, property names, or data structures from another analytics
platform into a GA4 plan.

## Legacy Inputs

Treat Universal Analytics, GA3, GAU, legacy GA360, UA Enhanced Ecommerce,
`eventCategory`, `eventAction`, `eventLabel`, `nonInteraction`, numbered
dimensions, and numbered metrics as migration evidence only. Translate the
business action through current GA4 documentation and the custom-event decision
rules.

## Out Of Scope

- Tracking plans targeting another analytics platform.
- Cross-platform event mapping tables.
- Vendor SDK payload design unrelated to GA4.
- Legal or privacy approval.
- GTM implementation, publishing, or runtime testing.

When another analytics platform is requested, explain that this skill is
GA4-only and use a dedicated platform skill when one is available.
