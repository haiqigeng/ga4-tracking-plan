# Account, Navigation, Support, And Content Decisions

## Authentication And Account

Use safe synthetic signup and login when public self-registration is
available. Include only capabilities observed or confirmed for the target
state.

For supplied test access, use one validated access profile per supplied or
observed role. Keep each profile in an isolated browser context, constrain it
to explicit entry URLs and allowed hosts, and use environment-variable names
or an explicit headful SSO/MFA handoff rather than storing secrets. Keep
storage state in memory, verify the authenticated predicate before each
round, retry authentication at most once, and discard state after the run.
Never infer unprovided roles.

Use official `login` and `sign_up` for successful outcomes when their semantics
fit. Custom account events require a meaningful self-service or diagnostic
question beyond a typed page view.

Do not stop account discovery at authentication. When present, inspect password
recovery, account navigation, order history and detail, reorder, wishlist,
profile or preference outcomes, returns, cancellation, refunds, and support
entry points. Measure only the outcomes or diagnostics that answer a concrete
question, but record a decision for every material capability.

After login, rebuild candidates from authenticated menus, links, routes,
locally revealed components and forms with the same discovery engine used for
the public site. Treat each material route, SPA service state, form purpose and
role-specific variant as its own coverage unit. A dashboard page alone is not
account coverage.

For gated forms, distinguish inventory, progression, representative failure,
submission and confirmed success. Do not infer success from disappearance,
generic copy or an analytics hit. Stop at MFA, CAPTCHA, payment, contract,
appointment, deletion and profile-specific consequential boundaries. If a
synthetic registration or request may persist, record a sanitised internal
side-effect entry and tell the user without exposing the synthetic identity.

Inventory relevant user and account fields exposed to the implementation.
Separate dataLayer presence from GA4 destination mapping.

When authentication exists, include `user.user_id` in the same core context
push as page and other user state. Map it only to the official GA4 User-ID
configuration setting. Never treat it as a custom user property or event
parameter.

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
