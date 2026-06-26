# Lead Generation Scenario Reference

Use this reference for quote funnels, contact forms, newsletter signup, appointment booking, callback requests, account creation, and other lead-capture journeys.

## Analyst Rules

- Start by separating intent events, form progression, successful lead submission, and errors.
- Prefer official recommended events when their meaning fits, especially `generate_lead`, `sign_up`, and `login`.
- Do not use `generate_lead` for every lead-form click. Reserve it for a successful lead or qualified submission.
- Avoid sending raw form values, personal details, free-text messages, email, phone number, postal address, policy number, or customer number.
- Use step names, form names, and error categories as controlled lowercase ASCII `snake_case` values.

## Event Selection

| Scenario | Prefer event | Classification | Notes |
|---|---|---|---|
| Lead form start | `begin_quote`, `form_start`, or scenario-specific custom event | custom | Use when no official GA4 event represents the start intent clearly |
| Lead form step view | `form_step_view` | custom | Useful for multi-step funnels when page_view is not enough |
| Lead form step complete | `form_step_complete` | custom | Use only when progression analysis is needed |
| Validation error | `form_error` | custom | Send generic error category and field group, never raw values |
| Successful lead | `generate_lead` | recommended | Use for completed quote/contact/lead submission |
| Signup success | `sign_up` | recommended | Use for account creation or newsletter signup when it is truly signup |
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

## QA Contract

- Validate the start, each tracked step, and the final success event with clean test data.
- Confirm failed validation does not fire `generate_lead`.
- Confirm errors contain only generic categories.
- Confirm no direct PII appears in dataLayer, GTM variables, GA4 requests, DebugView, or screenshots.

