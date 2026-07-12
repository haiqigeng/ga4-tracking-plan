# Execution Contract

Use this as the canonical sequence for every GA4 plan creation or review.

```text
scope and template
-> website and journey evidence
-> browser readiness and authenticated exploration
-> measurement brief
-> business questions and success signals
-> GA4 official-event decisions
-> parameter availability and ownership
-> dataLayer and GA4 payload specification
-> complete per-event developer examples
-> explicit screenshot evidence mapping
-> human workbook generation
-> deterministic validation
-> analyst review
```

## Required Decisions

1. State whether the work adapts a client template or uses the default workbook.
2. Separate observed, confirmed, inferred, recommended, and unavailable facts.
   Actively discover Playwright MCP before declaring browser evidence unavailable.
3. Tie every event to one journey, business question, and analysis use.
4. Prefer GA4 automatic, enhanced-measurement, recommended, and ecommerce
   events when their semantics fit.
5. Justify every custom event against official alternatives.
6. State whether each parameter is available, needs development, needs a
   backend source, remains to confirm, or is unavailable, and name its owner.
7. Keep ecommerce parameters at their official scope and in canonical order.
8. Mark every event as public, authentication-flow, or authenticated-area.
   Behind-login events require synthetic observation or client confirmation;
   blocked access produces a coverage gap and no gated event.
9. Exhaust practical finite values, keep multilingual controlled values in
   English, and provide a complete dataLayer example per event.
10. After event design, map one representative screenshot for repetitive
    generic events and all material scenarios for finite events. When capture is
    required, attempt Playwright MCP before any fallback. Never infer evidence
    from a loosely matching filename or leave a final row pending or silently skipped.
11. Record the `screenshot_capture` outcome. When blocked or partial, put the
    analyst-facing notice in Screenshot Register and repeat it in the delivery reply.
12. Generate the XLSX as the main human deliverable and keep internal reasoning
   out of visible tabs.
13. Stop after the tracking plan. Do not perform GTM implementation or runtime
    testing under this skill.
