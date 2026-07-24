# Official-First Measurement Design

## Events

For every meaningful action:

1. Define the business outcome or analysis question.
2. Check current official GA4 event documentation.
3. Use the official event when its semantics genuinely match.
4. Use an official ecommerce event when an item, promotion, checkout, or
   transaction action fits its documented semantics.
5. Create a custom event only when the official model cannot represent the
   meaningful business or diagnostic action.

The tracking plan contains manually implemented measurement only. Do not add
automatic events, enhanced-measurement events, native/no-push decisions, or
instructions about enabling native collection.

## Custom Event Gate

A custom event is accepted only when all three answers are concrete:

1. What meaningful business or diagnostic question is not answered by an
   official event?
2. Which official event was considered, and precisely why does it not fit?
3. Are the trigger, parameters, values, and dataLayer example sufficient for
   unambiguous implementation?

Keep this decision in the machine event specification. Do not create a visible
governance column for it.

## Parameters

Read the complete current official parameter table for the selected event
before adding parameters.

Include:

1. every unconditional official requirement;
2. a conditional official parameter when its condition applies to the
   observed, confirmed, or intended implementation;
3. an optional official parameter only when it supports a real analysis,
   business, attribution, activation, or implementation need;
4. a custom parameter only when official fields cannot represent the needed
   concept.

Do not add all optional parameters mechanically. Missing source data does not
remove a mandatory parameter; it creates an implementation dependency that
belongs in the source logic, not in `requirement`.

`requirement` has only:

- `required`
- `conditional`
- `optional`

Write a separate condition for `conditional`.

## Custom Parameter Gate

For a custom event, item, user, or implementation parameter, answer:

1. What required concept is absent from the selected event's official fields?
2. Which official parameters were considered?
3. Are its definition, scope, source, values, and implementation path
   unambiguous?

Use precise official-like wording. Prefer constructions such as:

- "Identifies the..."
- "Specifies the..."
- "Indicates whether..."
- "The number of..."
- "The normalized value of..."

Never use filler such as "Use the official definition," "Value associated with
the event," or "Variable used for tracking."

## Definitions And Triggers

- Official event definition: use the current official wording or a faithful
  localized rendering.
- Official parameter definition: use the current official parameter-row
  wording plus attached conditions when applicable.
- Custom definition: state exactly what the value represents.
- Trigger: state the concrete website action or state, when the push occurs,
  success or failure criteria, and repeat behavior when relevant.

Definitions explain meaning. Triggers explain firing. Do not merge them.

## Finite Values

Exhaust a stable observable domain when it contains up to 50 practical values.
Show normalized values in the selected workbook language unless they are
official codes, technical identifiers, numbers, booleans, or authoritative raw
values.

Do not exhaust:

- item IDs or names;
- transaction IDs;
- URLs;
- search terms;
- user-entered or free text;
- changing inventory;
- domains larger than 50.

Use a precise generation, normalization, or source rule instead.

## Ecommerce

- Keep current event-level and item-level scopes exact.
- When `items` is sent, every item contains `item_id` or `item_name`.
- Use event-level `currency` whenever `value` is sent.
- Treat event-level and item-level `coupon` as independent. Include both only
  when the website genuinely has order-level and item-level coupons.
- Use event-level list or promotion fields as a shared default only when all
  items share the same provenance.
- Use item-level `item_list_id` and `item_list_name` when different item
  provenance exists or when provenance is reliably retained into downstream
  item events.
- For item-related events after list selection, preserve useful item-level list
  provenance when the implementation can retain it.
- Use `item_variant` for the primary product variant representation. When the
  product has multiple separately analysed option dimensions, retain the
  official variant representation and add justified custom item parameters
  such as `item_color` or `item_size`.
- Include category levels only to the evidenced taxonomy depth. Do not
  generate empty levels.
- Carry stable, useful checkout context into `purchase` when it is persisted
  to the confirmed order. `shipping_tier` and `payment_type` are custom on
  `purchase` when used there because they are not prescribed purchase
  parameters.

## User And Context Data

Inventory relevant fields collected or exposed by the website, including
account and contact information when it is part of the implementation model.
For each field, distinguish:

- present in dataLayer;
- mapped as an ordinary GA4 event or item parameter;
- mapped as a GA4 user property or User-ID setting;
- implementation-only or intended for another destination.

Do not silently remove a website field from the data model. Conversely, do not
describe dataLayer presence as permission to send it to GA4. Keep legal
approval outside this skill and surface a concise implementation exception
only when destination handling materially changes the specification.
