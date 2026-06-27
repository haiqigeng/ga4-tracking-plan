# GA4 Tracking Plan

[![Validate skill](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml)

Codex skill package that acts as a web analyst for GA4-first tracking-plan creation: it frames business context and analysis needs, proposes scalable event and parameter designs, and produces readable XLSX-ready analytics schemas. Piano Analytics is supported when explicitly requested.

## Contents

- `skill/` - Codex skill definition and UI metadata
- `skill/scripts/` - Runtime scripts bundled with the installed skill
- `skill/references/` - Machine-readable and Markdown event scenario references used by the skill
- `skill/assets/ga4_tracking_plan_template.xlsx` - Human-ready default tracking plan template
- `scripts/create_event_scenario_library.py` - Regenerates GA4 scenario references from official documentation
- `scripts/generate_tracking_plan_workbook.py` - Repo wrapper for the bundled JSON-to-XLSX generator
- `scripts/validate_tracking_plan.py` - Repo wrapper for the bundled JSON tracking-plan validator
- `scripts/export_tracking_plan_csv.py` - Repo wrapper for the bundled long-format CSV exporter
- `scripts/analyze_tracking_plan_corpus.ps1` - Repo wrapper for privacy-safe historical-plan inventory on Windows
- `scripts/validate_package.py` - Validates skill structure, JSON contract, runtime scripts, workbook tabs, ecommerce matrix rules, generated workbook/CSV output, generic release surface, and common secret patterns

## Skill Focus

The skill helps design tracking schemas that start from business context, analysis needs, concerned pages or journeys, and reusable measurement decisions. It verifies official platform events, classifies native versus custom events and parameters/properties, and produces implementation-ready tracking plans. GA4 remains the default and strictest supported output path; Piano Analytics is supported through dedicated platform mapping guidance when requested. XLSX output is treated as the primary human-facing deliverable and should remain readable for analysts, developers, media teams, QA, and stakeholders.

It is intentionally scoped to tracking-plan creation and review. GTM, dataLayer, and server-side implementation are separate follow-up phases.

The skill should behave like a real web analyst:

- understand the business model, journey role, macro conversions, micro conversions, and diagnostic needs before proposing events
- prefer official GA4 automatic, enhanced-measurement, recommended, and ecommerce events when their semantics fit
- justify every custom event with the analysis need, official alternatives considered, reusable parameters, privacy checks, and QA expectations
- keep analyst-facing XLSX tabs lean, readable, and useful for humans rather than filled with agent-only rationale
- design event families, naming, controlled values, and QA IDs that can scale to future pages, journeys, markets, and test automation

The included GA4 event scenario library helps map common website scenarios to automatic, enhanced-measurement, recommended, ecommerce, and typical custom events with expected parameters and dataLayer patterns.

The package also includes scenario-specific playbooks for ecommerce, lead generation, search/listing, account/support/content, SPA routing, business-model analysis, website archetype inference, data quality/privacy, official-first review, example comparison, ecommerce parameter policy, Piano Analytics mappings, a structured Piano official-event lookup, mainstream analytics tool policy, and QA readiness. These keep the main skill concise while giving the agent targeted references for different tracking-plan situations.

Tracking plans generated with this skill consolidate repeated same-name events whenever the same trigger logic and parameter structure can cover multiple components. Controlled analytics values should use lowercase ASCII `snake_case`, with accents removed, so French labels such as `Nouveautes` become `nouveautes`.

Ecommerce events are handled as a stricter case: they should stay in ecommerce-only blocks and use the official GA4 ecommerce parameter names, including required item parameters from Google documentation. GTM/dataLayer wrapper paths such as `ecommerce.items` are implementation mapping details, not replacements for GA4 parameters like `items` and `items[].item_id`.

## Canonical JSON Contract

Reusable or QA-ready plans should follow `skill/references/tracking_plan_schema.json`. The schema includes the measurement brief, measurement strategy, scalability notes, event business families, event measurement roles, page/component context, event data dependencies, parameter reporting purposes, custom definitions, key events, not-tracked decisions, documentation sources checked, assumptions, and one QA case per testable event. It also allows optional platform mappings so a business event can carry GA4 and Piano-specific event/property expectations without blending their schemas.

`skill/references/generic_tracking_plan_fixture.json` is a generic GA4-first example of that contract. `skill/references/generic_piano_tracking_plan_fixture.json` is a generic Piano-only content-page example that proves platform-neutral plans do not need fake GA4 payload fields. `skill/references/generic_piano_ecommerce_tracking_plan_fixture.json` is a generic Piano Sales Insights ecommerce example. These fixtures use `example.com` and placeholder values only.

To generate an XLSX workbook from a JSON plan:

```text
python scripts/generate_tracking_plan_workbook.py skill/references/generic_tracking_plan_fixture.json --output generated_tracking_plan.xlsx
```

To validate a JSON plan and export a long-format CSV. The CSV includes GA4 rows and optional platform-mapping rows when the JSON contains Piano or cross-platform mappings:

```text
python scripts/validate_tracking_plan.py skill/references/generic_tracking_plan_fixture.json
python scripts/export_tracking_plan_csv.py skill/references/generic_tracking_plan_fixture.json --output generated_tracking_plan.csv
```

The validator checks schema shape, measurement strategy, event-family coverage, measurement roles, page/component context, event data dependencies, measurement-brief and journey alignment, parameter reporting purposes and value rules, not-tracked decision quality, required platform and official/custom rationale, business-question quality, GA4 official event classification, required GA4 recommended-event parameters, GA4 naming and reserved prefixes, ecommerce parameter scope, Piano mandatory properties, official documentation source coverage, custom-event justification, QA linkage, expected network event-name assertions, PII-looking field names, and platform mappings.

When learning from a folder of historical tracking plans on Windows, generate a privacy-safe inventory outside the repo:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/analyze_tracking_plan_corpus.ps1 -InputFolder "C:\path\to\tracking-plans" -OutputJson "C:\path\to\inventory.json"
```

The inventory keeps counts, sheet names, dimensions, and platform/scenario signals only. Do not commit source workbooks or generated inventories.

Generated client plans, screenshots, GTM previews, request exports, and test evidence should stay outside this generic package unless they are deliberately anonymized fixtures.

## Maintenance Guardrails

- Keep `skill/SKILL.md` under 500 lines and move detailed scenario logic into `skill/references/`.
- Keep bundled references generic, privacy-safe, and platform-separated; do not copy client workbook rows into the skill.
- Validate every schema, workbook, and release surface with `python scripts/validate_package.py`.
- Treat Universal Analytics examples as migration context only; do not promote UA fields or event models into GA4 plans.
- Use `scripts/analyze_tracking_plan_corpus.ps1` only for privacy-safe inventory. Generated inventories belong outside the repo.

## Install Locally

Copy the `skill/` folder into your local Codex skills directory and rename it to `ga4-tracking-plan`:

```text
%USERPROFILE%\.codex\skills\ga4-tracking-plan
```

The installed folder should contain:

```text
SKILL.md
agents/openai.yaml
assets/ga4_tracking_plan_template.xlsx
references/
scripts/
```

## Example Prompt

```text
Use $ga4-tracking-plan to create a GA4 tracking schema for these pages and journeys.
```

## Release Asset

The release bundle should be built from `skill/` plus `requirements.txt`. Release-only files should be generated in a temporary build directory, not committed to the repo. Site-specific tracking plans, tests, client artifacts, and confidential files should not be committed or attached to releases.

## Validate Locally

```text
python -m pip install -r requirements.txt
python scripts/validate_package.py
```
