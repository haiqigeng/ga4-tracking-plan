# GA4 Tracking Plan

[![Validate skill](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml)

Codex skill package for creating GA4 tracking plans from page or journey context.

## Contents

- `skill/` - Codex skill definition and UI metadata
- `files/lolivier_homepage_ga4_tracking_plan.xlsx` - Example homepage GA4 tracking plan for `https://www.lolivier.fr/`
- `files/daxon_homepage_ga4_tracking_plan.xlsx` - Ecommerce homepage example for `https://www.daxon.fr/`
- `files/ga4_tracking_plan_template_v2_1.xlsx` - Human-ready tracking plan template
- `files/ga4_event_scenario_library.xlsx` - GA4 event and scenario reference library
- `skill/references/` - Machine-readable and Markdown event scenario references used by the skill
- `scripts/create_tracking_plan_template.py` - Regenerates the default XLSX template
- `scripts/create_event_scenario_library.py` - Regenerates GA4 scenario references from official documentation
- `scripts/validate_package.py` - Validates skill structure, workbook tabs, ecommerce matrix rules, and common secret patterns

## Skill Focus

The skill helps design GA4 tracking schemas that start from a measurement brief, verify official GA4 recommended and ecommerce events, classify native versus custom events and parameters, and produce implementation-ready tracking plans.

It is intentionally scoped to tracking-plan creation and review. GTM, dataLayer, and server-side implementation are separate follow-up phases.

The included event scenario library helps map common website scenarios to automatic, enhanced-measurement, recommended, ecommerce, and typical custom events with expected parameters and dataLayer patterns.

Tracking plans generated with this skill consolidate repeated same-name events whenever the same trigger logic and parameter structure can cover multiple components. Controlled analytics values should use lowercase ASCII `snake_case`, with accents removed, so French labels such as `Nouveautes` become `nouveautes`.

Ecommerce events are handled as a stricter case: they should stay in ecommerce-only blocks and use the official GA4 ecommerce parameter names, including required item parameters from Google documentation. GTM/dataLayer wrapper paths such as `ecommerce.items` are implementation mapping details, not replacements for GA4 parameters like `items` and `items[].item_id`.

## Install Locally

Copy the `skill/` folder into your local Codex skills directory and rename it to `ga4-tracking-plan`:

```text
%USERPROFILE%\.codex\skills\ga4-tracking-plan
```

The installed folder should contain:

```text
SKILL.md
agents/openai.yaml
```

## Example Prompt

```text
Use $ga4-tracking-plan to create a GA4 tracking schema for these pages and journeys.
```

## Release Asset

The latest release includes the template, event scenario library, and example XLSX tracking plans as downloadable assets.

## Validate Locally

```text
python -m pip install -r requirements.txt
python scripts/validate_package.py
```
