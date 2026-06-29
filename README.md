# GA4 Tracking Plan

[![Validate skill](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml)

Codex skill package for creating GA4-first tracking plans that are useful in real analytics projects. It helps frame the business context, choose the right events, define clean parameters, and produce a readable XLSX tracking plan. Piano Analytics is supported when explicitly requested.

## What It Helps With

- Understand the pages, journeys, coverage sources, business goals, expected actions, and analysis needs before listing events.
- Choose the correct execution mode: client template adaptation or greenfield best-practice planning.
- Prefer official GA4 automatic, enhanced-measurement, recommended, and ecommerce events when they fit.
- Design custom events only when they answer a clear business or diagnostic question.
- Keep ecommerce events separate and aligned with the official GA4 ecommerce format.
- Record official verification, collection source, duplicate-risk, and ecommerce parameter profile decisions in structured plans.
- Keep parameter names, controlled values, and QA IDs stable enough to scale to future pages and journeys.
- Produce a tracking plan that web analysts, developers, media teams, QA, and stakeholders can read without extra explanation.

## What Is Included

- `skill/` - Codex skill definition and display settings
- `skill/scripts/` - Runtime scripts bundled with the installed skill
- `skill/references/01-skill/` - Purpose, users, questions, inputs, outputs, acceptance criteria, and non-goals
- `skill/references/02-commands/` - Validation, workbook generation, and historical-plan review commands
- `skill/references/03-rules/` - Event, parameter, privacy, QA, platform, scenario, and judgement rules
- `skill/assets/ga4_tracking_plan_template.xlsx` - Default XLSX tracking plan template
- `scripts/create_event_scenario_library.py` - Regenerates GA4 scenario references from official documentation
- `scripts/generate_tracking_plan_workbook.py` - Generates an XLSX tracking plan from a structured plan file
- `scripts/validate_tracking_plan.py` - Checks a structured plan file before workbook generation
- `scripts/export_tracking_plan_csv.py` - Exports a long-format CSV for review or comparison
- `scripts/discover_site_journeys.py` - Creates a privacy-safe first-pass website discovery JSON from robots, sitemap, static links, forms, and inferred journeys
- `scripts/annotate_screenshot.py` - Adds rectangle-only red callouts to screenshots for click, form, CTA, filter, menu, or other interaction evidence
- `scripts/analyze_tracking_plan_corpus.ps1` - Creates a privacy-safe summary of historical tracking-plan files on Windows
- `scripts/validate_package.py` - Runs package checks before publishing changes

## Skill Focus

The skill starts from business context, analysis needs, concerned pages or journeys, website coverage evidence, and reusable measurement decisions. GA4 remains the default and strictest supported output path. Piano Analytics is supported through dedicated platform guidance when requested.

XLSX is the primary delivery format. The workbook should stay readable: lean overview, clear GTM protocol, practical parameter reference, grouped event matrix, and compact evidence or QA-preparation tabs when useful.

The skill is intentionally scoped to tracking-plan creation and review. GTM implementation, dataLayer development, server-side tagging, and automated QA are separate follow-up phases.

The expected behavior is close to a real web analyst:

- understand the business model, journey role, macro conversions, micro conversions, and diagnostic needs before proposing events
- map whole-site or broad journey coverage from sitemap, navigation, representative templates, existing client files, and browser or Playwright exploration when needed
- generate Screenshot Register rows from the event draft, then capture selective evidence previews before final workbook delivery when useful
- preserve client templates when the mode requires it, while still challenging weak existing events
- use official GA4 events and parameters when their meaning fits the action
- justify every custom event with its analysis need, official alternatives, reusable parameters, privacy checks, and QA expectations
- keep the visible workbook focused on what humans need to build and review the plan
- design event families, naming, and controlled values that can scale to future pages, journeys, markets, and later QA automation

The included GA4 event scenario library helps map common website scenarios to automatic, enhanced-measurement, recommended, ecommerce, and typical custom events with expected parameters and dataLayer patterns.

The package also includes scenario guidance for ecommerce, lead generation, search/listing, account/support/content, SPA routing, website coverage mapping, business-model analysis, website archetype inference, data quality/privacy, official-first review, example comparison, ecommerce parameter policy, Piano Analytics mappings, mainstream analytics tool policy, and QA readiness.

Tracking plans generated with this skill consolidate repeated same-name events whenever the same trigger logic and parameter structure can cover multiple components. Controlled analytics values should use lowercase ASCII `snake_case`, with accents removed, so French labels such as `Nouveautes` become `nouveautes`.

Ecommerce events are handled as a stricter case: they should stay in ecommerce-only blocks and use the official GA4 ecommerce parameter names, including required item parameters from Google documentation. GTM/dataLayer wrapper paths such as `ecommerce.items` are implementation mapping details, not replacements for GA4 parameters like `items` and `items[].item_id`.

## Structured Plan Format

Reusable or QA-ready plans should follow `skill/references/03-rules/tracking-plan-schema.json`. This format keeps the execution context, template policy, website coverage map, measurement brief, strategy, scalability notes, events, parameters, official verification, collection strategy, ecommerce profiles, key events, not-tracked decisions, documentation sources, assumptions, and QA cases in one consistent structure.

Example files are included for reference:

- `skill/references/03-rules/generic-tracking-plan-example.json` - GA4-first example
- `skill/references/03-rules/generic-piano-tracking-plan-example.json` - Piano-only content-page example
- `skill/references/03-rules/generic-piano-ecommerce-tracking-plan-example.json` - Piano Sales Insights ecommerce example

These examples use `example.com` and placeholder values only.

To generate an XLSX workbook from a JSON plan:

```text
python scripts/generate_tracking_plan_workbook.py skill/references/03-rules/generic-tracking-plan-example.json --output generated_tracking_plan.xlsx
```

To validate a structured plan and export a long-format CSV:

```text
python scripts/validate_tracking_plan.py skill/references/03-rules/generic-tracking-plan-example.json
python scripts/export_tracking_plan_csv.py skill/references/03-rules/generic-tracking-plan-example.json --output generated_tracking_plan.csv
```

To create a first-pass website discovery JSON:

```text
python scripts/discover_site_journeys.py https://www.example.com/ --output site_discovery.json
```

To annotate an interaction screenshot before embedding it in a workbook:

```text
python scripts/annotate_screenshot.py source.png annotated.png --box x1,y1,x2,y2
```

The validator checks the structure, event classifications, GA4 ecommerce rules, parameter value rules, privacy risks, custom-event justification, official documentation coverage, and QA links.

When learning from a folder of historical tracking plans on Windows, generate a privacy-safe inventory outside the repo:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/analyze_tracking_plan_corpus.ps1 -InputFolder "C:\path\to\tracking-plans" -OutputJson "C:\path\to\inventory.json"
```

The inventory keeps only counts, sheet names, dimensions, and platform/scenario signals. Do not commit source workbooks or generated inventories.

Generated client plans, screenshots, GTM previews, request exports, and test evidence should stay outside this generic package unless they are deliberately anonymized examples.

## Maintenance Checklist

- Keep `skill/SKILL.md` under 500 lines and move detailed scenario logic into `skill/references/03-rules/`.
- Preserve the numbered reference structure: `01-skill` for product orientation, `02-commands` for repeatable checks and generation, and `03-rules` for workload rules.
- Keep references generic, privacy-safe, and platform-separated; do not copy client workbook rows into the skill.
- Validate the package with `python scripts/validate_package.py`.
- Treat Universal Analytics examples as migration context only; do not promote UA fields or event models into GA4 plans.
- Use `scripts/analyze_tracking_plan_corpus.ps1` only for privacy-safe inventory. Generated inventories belong outside the repository.

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
references/01-skill/
references/02-commands/
references/03-rules/
scripts/
```

## Example Prompt

```text
Use $ga4-tracking-plan to create a GA4 tracking plan for these pages and journeys.
```

## Release Package

The release package should contain `skill/` plus `requirements.txt`. Site-specific tracking plans, screenshots, test evidence, and confidential files should never be committed or attached to releases.

## Validate Locally

```text
python -m pip install -r requirements.txt
python scripts/validate_package.py
```
