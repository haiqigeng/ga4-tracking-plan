# Lead, Form, Quote, And Booking Decisions

Model the actual funnel variants rather than forcing one fixed step count.
Different two-step and four-step interfaces can share events when the business
meaning, trigger, and parameter contract are the same. Use parameters such as
`form_step` and `form_step_number` to express the variant.

Separate:

- intentional funnel start;
- meaningful step display when drop-off analysis needs it;
- successful step validation;
- project or request details when they represent a distinct measurement
  concept;
- categorized validation or technical errors;
- final backend-confirmed lead or booking success.

Do not keep two events with the same success trigger and no distinct analysis
meaning. A final step event and `generate_lead` may fire together only when
they represent different facts and analysts need both. Otherwise keep the
final business outcome.

Use `generate_lead` when the completed outcome matches its official semantics.
Use custom journey events only for meaningful progression or outcomes not
represented by official events.

Use safe synthetic information to investigate public funnels. Enumerate stable
form choices up to 50 values. Treat free text and user-entered identifiers as
dynamic rules.
