# Execution Contract

Use this as the canonical sequence for every GA4 plan creation or review.

```text
scope and template
-> website and journey evidence
-> measurement brief
-> business questions and success signals
-> GA4 official-event decisions
-> parameter availability and ownership
-> dataLayer and GA4 payload specification
-> explicit screenshot evidence mapping
-> human workbook generation
-> deterministic validation
-> analyst review
```

## Required Decisions

1. State whether the work adapts a client template or uses the default workbook.
2. Separate observed, confirmed, inferred, recommended, and unavailable facts.
3. Tie every event to one journey, business question, and analysis use.
4. Prefer GA4 automatic, enhanced-measurement, recommended, and ecommerce
   events when their semantics fit.
5. Justify every custom event against official alternatives.
6. State whether each parameter is available, needs development, needs a
   backend source, remains to confirm, or is unavailable, and name its owner.
7. Keep ecommerce parameters at their official scope and in canonical order.
8. Map screenshot evidence explicitly to event IDs; never infer evidence from
   a loosely matching filename.
9. Generate the XLSX as the main human deliverable and keep internal reasoning
   out of visible tabs.
10. Stop after the tracking plan. Do not perform GTM implementation or runtime
    testing under this skill.
