# GA4 Tracking Plan

[![Latest release](https://img.shields.io/github/v/release/haiqigeng/ga4-tracking-plan)](https://github.com/haiqigeng/ga4-tracking-plan/releases/latest)
[![Validate skill](https://github.com/haiqigeng/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/haiqigeng/ga4-tracking-plan/actions/workflows/validate-skill.yml)
[![License](https://img.shields.io/github/license/haiqigeng/ga4-tracking-plan)](LICENSE)

A utility-first web-analyst skill for creating, reviewing, adapting, and
maintaining complete GA4 tracking plans from real website journeys and the
available business, design, analytics, and technical evidence.

Tracking-plan quality is the product. The workbook is a lean human contract
for web analysts to review and maintain and for developers to implement through
the dataLayer.

## North Star

Turn live website exploration and all available business, design, and technical
evidence into a complete, adapted, and implementation-ready GA4 tracking plan
for the real user journeys. Use current official GA4 events, parameters,
semantics, and wording first; introduce precise custom elements only where
official constructs cannot represent a meaningful business need. Deliver the
result, in the supplied template or the integrated default template, as a clear
and just-enough human contract.

The skill uses one adaptive workflow and one quality standard. It has no small,
large, quick, enterprise, or event-count mode.

## What It Does

- builds a prioritized candidate universe from supplied entry points,
  sitemaps, and rendered links, and never equates a page cap with complete
  journey coverage;
- explores rendered public and safely accessible gated journeys;
- uses synthetic information for safe form, signup, login, and funnel
  investigation unless the user opts out;
- combines website, user, business, Figma, GTM, dataLayer, backend, previous
  plan, and analytics evidence according to what each source can prove;
- starts from business journeys and analysis decisions, not click inventories;
- resolves every selected official event and parameter against current Google
  documentation;
- adds custom events or parameters only after documenting the official gap;
- exhausts stable website value domains of up to 50 values;
- maintains a validated internal analysis context for evidence roles,
  conflicts, journey coverage, gaps, and finite-value provenance;
- specifies exact website triggers, event-specific parameters, source paths,
  and quoted dataLayer pushes;
- adapts a supplied workbook semantically or uses the integrated default XLSX
  template;
- delivers the workbook atomically with canonical JSON, expected events,
  exact per-event JSON Schemas, official-source verification, hashes, and
  approval state;
- imports, reconciles, compares, and consolidates previous plans, and reports
  evidence drift or targeted business-change impact without silently mutating
  the plan.

## Human Output Contract

The canonical unit is one event specification containing:

- journey and technical event name;
- official, official ecommerce, custom, or context classification;
- precise definition and concrete website trigger;
- applicable pages, routes, states, or components;
- only the parameters genuinely sent with that event;
- parameter scope, type, requirement, condition, definition, values or rule,
  example, and implementation path;
- one complete dataLayer example with quoted keys.

The default workbook derives these human views from the same specification:

- `Guide`;
- `Event Matrix`;
- `Parameter Reference`;
- one detailed tab per event or context push;
- `Change Log` only for maintenance deliveries;
- screenshots only when requested or materially useful.

It deliberately omits automatic and enhanced-measurement rows, inherited
variables, agent reasoning, evidence registers, confidence, ownership,
registration, privacy, cardinality, and other internal machinery from the
default visible workbook.

## Official-First Rules

For every selected official event, the skill reads the complete current
official parameter table. It includes:

1. required parameters;
2. applicable conditional parameters;
3. optional official parameters supported by a real analysis, business,
   attribution, or implementation need.

It does not copy all official parameters mechanically. A custom semantic is
valid only when it answers a concrete business need that the appropriate
official construct cannot represent.

Official definitions and attached conditions use official wording. Custom
definitions use equally precise official-like wording. Generic filler is
invalid.

## Language

Workbook language follows, in order:

1. explicit user choice;
2. supplied template;
3. project-team working language;
4. primary analyst and developer audience;
5. dominant in-scope website language.

Human definitions, triggers, conditions, and semantic values are localized.
Technical event names, parameter names, wrappers, paths, codes, and official
identifiers remain English lowercase `snake_case`.

## Installation

Copy `skill/` to:

```text
%USERPROFILE%\.codex\skills\ga4-tracking-plan
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

For another file- and tool-capable agent, place `skill/` in its supported
skills directory and load `SKILL.md` as the entry point.

## Common Commands

Discover rendered candidates and execute an explicitly bounded synthetic
journey:

```powershell
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --output discovery.json
python scripts/build_analysis_context_seed.py discovery.json --output analysis-context.json
# Explicit context overrides website-language evidence when provided:
python scripts/build_analysis_context_seed.py discovery.json --output analysis-context.json --language fr --language-basis user --target-state to_be
python scripts/capture_interactive_journey.py interactive-journey.json --output journey-evidence.json
```

Validate selected semantics against current official Google sources:

```powershell
python scripts/check_official_sources.py plan.json --output official-check.json
```

Validate the evidence checkpoint and build the complete delivery atomically:

```powershell
python scripts/validate_analysis_context.py analysis-context.json --plan plan.json --discovery-report discovery.json --delivery
python scripts/build_tracking_plan_delivery.py plan.json analysis-context.json --discovery-report discovery.json --output-dir delivery
```

Inspect and adapt a supplied workbook:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-map.json
python scripts/build_tracking_plan_delivery.py plan.json analysis-context.json --discovery-report discovery.json --template client-template.xlsx --mapping template-map.json --output-dir delivery
```

Maintain an existing plan:

```powershell
python scripts/import_tracking_plan_workbook.py previous-plan.xlsx --output previous-plan.json
python scripts/import_tracking_plan_workbook.py edited-plan.xlsx --reconcile-visible-edits --output reconciled-plan.json
python scripts/diff_tracking_plans.py previous-plan.json updated-plan.json --output changes.json
python scripts/detect_tracking_plan_drift.py previous-analysis-context.json analysis-context.json updated-plan.json --before-discovery-report previous-discovery.json --after-discovery-report discovery.json --output drift-report.json
python scripts/analyze_tracking_plan_change_impact.py updated-plan.json change-request.json --analysis-context analysis-context.json --output impact-report.json
```

Inspect local browser readiness:

```powershell
python scripts/inspect_browser_environment.py
```

## Repository Structure

- `skill/`: the complete installable runtime skill, default template, schemas,
  references, scripts, and regression tests;
- `scripts/`: root command wrappers and release validation;
- `.github/workflows/`: cross-platform validation, official-source drift, and
  release packaging;
- `pyproject.toml` and `requirements.txt`: synchronized runtime dependencies.

## Validation

Before release:

```powershell
ruff check .
python -m compileall -q scripts skill/scripts skill/tests
python -m unittest discover -s skill/tests
python scripts/validate_package.py
git diff --check
```

The package validator checks metadata and every machine schema/example, strict
semantic and evidence-context validation, exact XLSX round-trip behavior, an
atomic offline delivery build, release contents, and repository cleanliness.
It also extracts the generated zip and runs validation and an offline delivery
through the packaged root wrappers, and generates the archive twice to require
byte-for-byte reproducibility. For an official release, run
`python scripts/validate_package.py --release-tag vX.Y.Z`; this additionally
requires a clean worktree, matching metadata, and a tag that resolves exactly
to `HEAD`. Official package creation applies the same provenance gate.

## Boundaries

The skill does not:

- configure, publish, audit, or clean GTM;
- execute GTM Preview, DebugView, network, or runtime recette;
- make legal or privacy approval decisions;
- create a plan for another analytics platform;
- maximize event or parameter counts.

## Versioning

Version `2.6.0` keeps canonical plan schema `5.0.0` while correcting the
coverage and evidence regressions found in repeated whole-site runs. Rendered
page purpose now uses surface-weighted, whole-word multilingual classification
that excludes global chrome and retains ambiguous candidates as unknown.
Discovery report `1.2.0` inventories bounded interaction families, separates
not-tested, partial, and externally blocked evidence, and requires every hint
to receive an explicit measure/exclude decision without creating a click
inventory. Delivery rejects seed placeholders, unsupported live-opportunity
locations, factual-state rewrites, and semantically duplicate value domains.
Official checkout anchors require `payment_type` on `add_payment_info` and
`shipping_tier` on `add_shipping_info`, while a justified official-to-custom
carry-through remains coherent across events. Supplied-template mappings now
declare their parameter-registry role and validate mapped semantic parity.
The dataLayer renderer adds only two opt-in formatting controls: JavaScript
fragment versus HTML script block, and explicit initialization. Default
workbooks now keep title merges within their real table width, and delivery
validation rejects overlapping merged-cell ranges before Excel can repair the
file on opening.

Version `2.5.0` keeps canonical plan schema `5.0.0` and completes the operational
closure that `2.4.0` started. Rendered discovery now runs automatic targeted
rounds, captures evidence-backed website language, and safely progresses
every distinct material non-transactional funnel variant with synthetic data.
One successful route can no longer close sibling funnel variants. Contextual
hints retain their journey and variant provenance, heuristic candidates remain
separate from material opportunities, and finite-choice discovery covers
native and common custom controls. A valid partial report continues to analyst
resolution instead of failing the pipeline. Its versioned
report is SHA-256-bound to the analysis context: every hint must become an
explicit measure, exclude, or unresolved opportunity and every journey must
remain in coverage at variant level. Delivery rejects missing reports, changed
hashes, vanished hints or variants, and unresolved material decisions. The
release also validates localized
controlled-value labels, compares rendered forms, controls, hints, and
interaction outcomes during drift, infers business-change impact when explicit
selectors are absent, and supplies direct machine handoffs to GTM configuration
and Preview recette.

Version `2.4.0` introduced schema `5.0.0`, broader rendered candidate scoring,
the measurement-opportunity model, stricter official semantics, evidence-backed
value domains, and the lean workbook contract. Its crawler hints, opportunity
ledger, delivery gate, interaction runner, and downstream artifacts were not
yet mechanically connected end to end.

Version `2.3.0` introduced evidence-gated journey coverage, rendered interaction
capture, finite-value provenance, atomic delivery contracts, strict supplied-
template fidelity, visible-edit reconciliation, semantic drift detection, and
targeted change-impact analysis. Its interaction evidence was not yet a
mandatory closure condition between discovery and event selection. Versions
`2.1.0` and `2.2.0` were local development iterations and were not public
GitHub releases; `2.3.0` was the next public release after `2.0.0`.

Compatible capabilities are released as minor versions. Patch releases fix
documentation, validation, rendering, or packaging defects.

## Privacy And Safety

Do not commit client workbooks, generated plans, screenshots, container IDs,
measurement IDs, credentials, personal data, payment data, or private business
information. Generic examples use `example.com` and synthetic values only.

## License

[MIT](LICENSE)
