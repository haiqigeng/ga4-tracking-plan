# Optional Measurement-Framework Intake

Use this reference only when the user supplies a measurement framework. It is
an evidence adapter inside the ordinary tracking-plan workflow, not a separate
mode, workflow, dependency, or deliverable.

## Position And Influence

Treat the framework as strong but rebuttable business evidence:

- a current, applicable framework with passing quality gates establishes high
  investigation priority and a presumption of business materiality;
- a draft or partial framework is a structured hypothesis;
- a failed, stale, or non-applicable framework is an investigation lead only.

The framework creates a duty to investigate and decide, not a duty to
implement. It may guide business scope, journey priority, outcomes, KPI
decision uses, and semantic facts needed for analysis. It cannot prove current
or intended interface behavior, technical feasibility, existing collection,
or appropriate GA4 and dataLayer design.

## Intake Inside The Existing Evidence Step

Prefer the canonical `measurement-framework.json` when it is supplied. Use its
Markdown as the human explanation or as fallback evidence when JSON is absent.
Validate JSON with its declared schema or producer validator when that resource
is available. Otherwise inspect its declared schema version and overall quality
status without claiming independent validation. For Markdown-only input, do
not fabricate canonical IDs or machine status.

Register the artifact in `analysis-context.json` with source type
`measurement_framework`, evidence role `business_requirement`, its target
state, hash when available, and a `framework_intake` summary. Use analysis-
context version `1.1.0` for this optional intake. Put only these references in
`applicable_material_refs`:

- framework journeys that are material and whose declared applicability
  intersects or could plausibly intersect the tracking-plan scope; and
- semantic measurement requirements that are material, plausibly applicable,
  and could affect web measurement or its explicit collection boundary.

Do not add every objective, KPI, formula component, dimension, or candidate to
that list. They guide questions and analytical facts but do not each require a
tracking-plan disposition.

For canonical JSON, use each exact stable framework ID. For Markdown-only
input, use a stable heading or section locator and do not present it as a
canonical framework ID.

## Normal Discovery Still Runs

Use the applicable framework references to prioritize targeted discovery and seed
business questions. Then execute the same rendered, design, and technical
investigation used without a framework. Verify journey existence, route and
component variants, success, failure, empty and post-conversion states, and
implementation capability. Continue looking for material journeys absent from
the framework.

Framework presence is not proof that a journey exists or belongs in this web
plan. Framework absence is not evidence that a discovered journey is
immaterial.

## Adjudication

Bind each applicable material framework reference to a material
`measurement_opportunities` row through `evidence_locations` using the
framework `source_id` and the exact ID or section reference as `locator`.
Record one disposition:

- `measure`: represent it through one or more independently designed tracking
  events;
- `covered_elsewhere`: retain the need, but assign reliable collection to
  native analytics, a backend event, business-system fact, join, or another
  tracking-plan scope;
- `exclude`: do not measure it in the target plan, with a concrete reason; or
- `unresolved`: evidence is insufficient; a material unresolved item blocks
  delivery.

One framework item may map to several opportunities or events, and one event
may support several framework items. Never require a KPI-to-event,
objective-to-event, or requirement-to-parameter one-to-one mapping.

## Evidence Conflicts

Resolve the question using the source that can actually prove it:

| Question | Most relevant evidence |
| --- | --- |
| Business purpose and decision need | Framework plus current business input |
| Current website reality | Rendered live evidence |
| Intended future experience | Approved design and functional specification |
| Current collection | GTM, dataLayer, and runtime evidence |
| Appropriate GA4 semantics | Current official GA4 documentation and tracking-plan reasoning |

Also consider recency, target state, market, language, audience, and platform
applicability. Retain a material disagreement internally; do not silently
rewrite the framework or let it override stronger evidence for another
question.

## Closure And Human Output

Before delivery, every entry in `applicable_material_refs` must be linked to a material
opportunity with a non-unresolved disposition. Additional independently
discovered journeys and opportunities remain valid without framework references.

Keep framework references, quality status, reconciliation, and conflict reasoning in
the analysis context and handoff. Do not add framework, objective, KPI,
confidence, or governance columns to the default workbook.

Examples:

- A framework says company search matters. Investigate the real search,
  zero-result, result, and selection variants, then independently choose the
  useful event design.
- A framework requires backend-qualified lead status. Use
  `covered_elsewhere` instead of inventing a browser success event.
- Live discovery finds newsletter confirmation absent from the framework.
  Evaluate it normally; upstream silence does not exclude it.
