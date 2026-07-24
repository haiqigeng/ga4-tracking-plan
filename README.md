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
- specifies exact website triggers, event-specific parameters, source paths,
  and quoted dataLayer pushes;
- adapts a supplied workbook semantically or uses the integrated default XLSX
  template;
- imports, compares, and consolidates previous plans for maintenance work.

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

Validate selected semantics against current official Google sources:

```powershell
python scripts/check_official_sources.py plan.json --output official-check.json
```

Validate and render:

```powershell
python scripts/validate_tracking_plan.py plan.json
python scripts/generate_tracking_plan_workbook.py plan.json --output tracking-plan.xlsx
```

Inspect and adapt a supplied workbook:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-map.json
python scripts/adapt_tracking_plan_workbook.py plan.json client-template.xlsx --mapping template-map.json --output tracking-plan.xlsx
```

Maintain an existing plan:

```powershell
python scripts/import_tracking_plan_workbook.py previous-plan.xlsx --output previous-plan.json
python scripts/diff_tracking_plans.py previous-plan.json updated-plan.json --output changes.json
python scripts/generate_tracking_plan_workbook.py updated-plan.json --changes changes.json --output updated-tracking-plan.xlsx
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

The package validator checks metadata and schema consistency, the generic
example, strict semantic validation, exact XLSX round-trip behavior, release
contents, and repository cleanliness.

## Boundaries

The skill does not:

- configure, publish, audit, or clean GTM;
- execute GTM Preview, DebugView, network, or runtime recette;
- make legal or privacy approval decisions;
- create a plan for another analytics platform;
- maximize event or parameter counts.

## Versioning

Version `2.0.0` introduces schema `4.0.0` and replaces the governance-heavy
workbook architecture with one event-centered semantic model and a lean,
human-first default workbook. Future minor releases may add compatible
capabilities; patch releases fix documentation, validation, rendering, or
packaging defects.

## Privacy And Safety

Do not commit client workbooks, generated plans, screenshots, container IDs,
measurement IDs, credentials, personal data, payment data, or private business
information. Generic examples use `example.com` and synthetic values only.

## License

[MIT](LICENSE)
