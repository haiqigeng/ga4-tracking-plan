# Account, Navigation, Support, And Content Decisions

## Authentication And Account

Use safe synthetic signup and login when public self-registration is
available. Include only capabilities observed or confirmed for the target
state.

Use official `login` and `sign_up` for successful outcomes when their semantics
fit. Custom account events require a meaningful self-service or diagnostic
question beyond a typed page view.

Inventory relevant user and account fields exposed to the implementation.
Separate dataLayer presence from GA4 destination mapping.

## Navigation

Do not create one event per link. Consolidate interactions that share meaning,
trigger, and parameter structure. Keep separate navigation events only when
the project convention or analysis needs genuinely distinguish header, menu,
submenu, footer, or another surface.

Use `select_content` only for identifiable content objects whose meaning fits
the official event. Do not force all navigation into it merely because it is
official.

## Content And Support

Measure content or support interactions only when they support a decision such
as discovery, usefulness, self-service success, contact intent, or conversion.
Avoid generic click tracking and automatic/enhanced-measurement rows.

Use controlled content type, identity, and location values when practical.
Never use raw personalized text as a controlled taxonomy.
