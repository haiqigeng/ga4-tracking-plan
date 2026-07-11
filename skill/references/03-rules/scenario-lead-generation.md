# Lead Generation Scenario Reference

Use this reference for quote funnels, contact forms, newsletter signup, appointment booking, callback requests, account creation, and other lead-capture journeys.

## Analyst Rules

- Start by separating intent events, form progression, successful lead submission, and errors.
- Prefer official recommended events when their meaning fits, especially `generate_lead`, `sign_up`, and `login`.
- Do not use `generate_lead` for every lead-form click. Reserve it for a successful lead or qualified submission.
- Decide explicitly whether successful forms represent one lead KPI or separate
  business outcomes. Consolidate under `generate_lead` plus a controlled
  `lead_type` only when ownership, value, lifecycle, and reporting are genuinely
  shared. Otherwise prefer distinct success events such as
  `newsletter_subscribe`, `contact_submit`, and `catalog_request`.
- Do not dual-fire `generate_lead` and a dedicated custom success event for the
  same outcome by default. Choose one reporting model and document it.
- Avoid sending raw form values, personal details, free-text messages, email, phone number, postal address, policy number, or customer number.
- Use step names, form names, and error categories as controlled lowercase ASCII `snake_case` values.

## Event Selection

| Scenario | Prefer event | Classification | Notes |
|---|---|---|---|
| Lead form start | `form_start` | enhanced_measurement | Use when enhanced measurement identifies the correct form without duplicates |
| Distinct quote journey start | `begin_quote` | custom | Use only when quote-start intent is analytically different from generic form engagement |
| Lead form step view | `form_step_view` | custom | Useful for multi-step funnels when page_view is not enough |
| Lead form step complete | `form_step_submit` | custom | Use only when progression analysis is needed |
| Validation error | `form_error` | custom | Send generic error category and field group, never raw values |
| Successful lead | `generate_lead` | recommended | Use for a consolidated, qualified lead outcome when the business treats the submissions as one KPI |
| Newsletter subscription | `newsletter_subscribe` or `generate_lead` | custom or recommended | Prefer a dedicated event when permissioned audience growth has its own owner and reporting |
| Contact submission | `contact_submit` or `generate_lead` | custom or recommended | Prefer a dedicated event when service contact and commercial leads are analyzed separately |
| Catalogue request | `catalog_request` or `generate_lead` | custom or recommended | Prefer a dedicated event when fulfilment, stock, or acquisition reporting is distinct |
| Signup success | `sign_up` | recommended | Reserve for account creation, not ordinary newsletter subscription |
| Login success | `login` | recommended | Use only after successful authentication |

## Suggested Parameters

| Parameter | Scope | Value rules |
|---|---|---|
| `form_name` | event | Stable form identifier such as `quote_form` |
| `form_step` | event | `step_1_vehicle`, `step_2_contact`, or another stable convention |
| `form_step_number` | event | Integer step number when useful |
| `lead_type` | event | Controlled business type such as `quote`, `callback`, `appointment` |
| `cta_location` | event | `header`, `hero`, `body`, `footer`, `modal` |
| `error_type` | event | `validation_error`, `technical_error`, `eligibility_error` |
| `error_field_group` | event | Generic field group, not raw field value |

## DataLayer Pattern

```js
dataLayer.push({ event_data: null });
dataLayer.push({
  event: "generate_lead",
  event_data: {
    form_name: "quote_form",
    lead_type: "quote",
    form_step: "success"
  }
});
```

## Implementation Notes

- Define the start, each meaningful tracked step, and the final success trigger clearly.
- Fire `generate_lead` only after successful validation.
- Fire dedicated success events only after the backend or form confirms success;
  a submit-button click remains intent or form engagement.
- Keep errors limited to generic categories.
- Keep direct PII out of the dataLayer, GA4 payload, URLs, and screenshots.
