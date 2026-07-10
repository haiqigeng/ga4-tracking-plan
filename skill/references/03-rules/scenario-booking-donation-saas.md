# Booking, Donation, And SaaS Scenarios

Use this rule when the website's primary outcome is not conventional retail.

## Booking

Use ecommerce events when a confirmed booking is a paid transaction with
stable item, currency, value, and transaction data. Use `generate_lead` for an
appointment or reservation request that creates a lead but no transaction.
Custom intermediate events are justified only for meaningful availability,
selection, or multi-step diagnostics.

## Donation And Membership

Use `begin_checkout` and `purchase` when a completed donation or membership is
processed as a transaction. Represent the contribution or membership product
consistently in `items`. Never send donor identity, free-text dedication,
payment data, or sensitive cause information.

## SaaS And Product-Led Growth

Use `sign_up`, `login`, `tutorial_begin`, `tutorial_complete`, `select_content`,
and `purchase` when they fit. Track feature usage only for product capabilities
that support adoption, retention, or commercial decisions. Consolidate feature
events through controlled `feature_name`, `feature_area`, and `plan_type`
values rather than creating one event per interface control.

For every model, distinguish observed website behavior from inferred future
journeys and state whether required data already exists or needs development.
