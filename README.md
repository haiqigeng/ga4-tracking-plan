# GA4 Tracking Plan

[![Latest release](https://img.shields.io/github/v/release/haiqigeng/ga4-tracking-plan?sort=semver)](https://github.com/haiqigeng/ga4-tracking-plan/releases/latest) ![License](https://img.shields.io/github/license/haiqigeng/ga4-tracking-plan) ![Top language](https://img.shields.io/github/languages/top/haiqigeng/ga4-tracking-plan)

[![Validate skill](https://github.com/haiqigeng/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/haiqigeng/ga4-tracking-plan/actions/workflows/validate-skill.yml)

A reusable web-analyst skill for creating and reviewing human-readable GA4
tracking plans.

It starts from the website, business goals, journeys, expected actions, and
analysis needs. It then selects appropriate GA4 events, defines useful
parameters, states what data is available, and produces an XLSX plan that a web
analyst or developer can use.

## Who It Is For

- Web analysts and analytics consultants.
- Tracking-plan owners and analytics engineers.
- Developers implementing GTM and dataLayer requirements.
- Ecommerce, marketing, product, content, and media teams reviewing the
  measured business outcomes.

## Problems It Solves

- Event lists with no business or analysis purpose.
- Custom events used where GA4 already provides an appropriate event.
- Unrelated newsletter, contact, catalogue, or lead outcomes hidden inside one
  generic conversion event without a business decision.
- Ecommerce events mixed with generic click tracking.
- Whole-site plans that stop at login and omit useful customer-space services.
- Parameters with unclear values, source, ownership, or reporting purpose.
- Tracking plans that invent data the website does not currently expose.
- Journey events scattered across a workbook.
- Unreadable templates filled with internal or agent-oriented information.
- Screenshots guessed from filenames or reused without a clear reason.

## Procedure

1. Confirm the website scope, pages, journeys, template, and naming convention.
2. Understand the business goal, expected actions, analysis needs, and success
   signals.
3. Inspect the available browser environment, then complete public signup and
   authenticated customer-space journeys with synthetic information. If the
   gated journey cannot be entered, retain a coverage gap and no gated events.
4. Select GA4 automatic, enhanced-measurement, recommended, and ecommerce
   events before considering custom events. Decide whether form outcomes share
   `generate_lead` or need separate success events.
5. Exhaust finite English controlled values where practical, then define
   parameter rules, examples, availability, data owners,
   privacy risks, and GA4 registration needs.
6. Specify one complete developer-readable dataLayer and GA4 mapping example
   per event, using Google's official GTM ecommerce structure.
7. Define connected-user state once in GTM Protocol when relevant, with GA4
   User-ID and user-property mappings kept separate from event payloads.
8. After event design, capture one representative screenshot for repetitive
   generic events and all materially different scenarios for finite events.
9. Generate and validate the XLSX tracking plan.

For ecommerce customer spaces, the skill considers meaningful order, return,
cancellation, profile, preference, and reorder outcomes. It keeps confirmed
order cancellation separate from GA4's official `refund` event.

## Inputs

The skill can use:

- a website URL or list of pages;
- user journeys and business requirements;
- an existing tracking plan or workbook template;
- a naming convention or development specification;
- screenshots, navigation, sitemap, or browser evidence;
- known GTM, dataLayer, CMS, ecommerce, SPA, or consent context.

When information is missing, the skill makes conservative assumptions, marks
them as inferred, and states what must be confirmed.

## Outputs

The main output is an XLSX workbook with six tabs:

- `00 Overview`: document details, navigation, and version history;
- `01 GTM Protocol`: shared GTM/dataLayer rules and official links;
- `02 Parameter Reference`: definitions, values, availability, owners, and GA4
  registration needs;
- `03 Event Matrix`: the main tracking plan grouped by journey;
- `04 DataLayer Examples`: complete per-event GTM implementation examples;
- `05 Screenshot Register`: explicit page and interaction evidence.

The skill can also produce validated JSON and a long-format CSV. Machine fields
remain outside the human Event Matrix.

## Non-Goals

This skill does not:

- create plans for another analytics platform;
- audit or clean a GTM container;
- implement or publish GTM changes;
- execute GTM Preview, DebugView, or network recette after implementation;
- approve privacy or legal use;
- preserve Universal Analytics schema;
- maximize event count;
- place direct personal data in ordinary GA4 parameters.

## Repository Structure

- `skill/SKILL.md`: skill workflow and resource routing.
- `skill/references/01-skill/`: product orientation.
- `skill/references/02-commands/`: repeatable commands.
- `skill/references/03-rules/`: analyst judgement, scenarios, policies, and
  the GA4 contract.
- `skill/scripts/`: installed runtime tools.
- `skill/assets/`: default workbook template.
- `scripts/`: repository wrappers and release maintenance.
- `tests/`: unit and integration regression tests.

The three reference branches follow the same convention used by the companion
GTM skill family: orientation, execution, and professional judgement without
using those words as folder names.

## Install

Copy `skill/` to:

```text
%USERPROFILE%\.codex\skills\ga4-tracking-plan
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Playwright is optional for public static work, but an interactive browser or
Playwright MCP is required to investigate an unconfirmed gated journey:

```powershell
python -m pip install playwright
python scripts/inspect_browser_environment.py
```

The preflight prefers the eligible system default browser, including Microsoft
Edge through `msedge`, and reports when another browser build is needed.

## Common Commands

Validate a plan:

```powershell
python scripts/validate_tracking_plan.py plan.json
```

Generate the XLSX:

```powershell
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx
```

Inspect and use a client workbook template:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-inventory.json
python scripts/adapt_tracking_plan_workbook.py plan.json client-template.xlsx --mapping sheet-mapping.json --output plan.xlsx
```

Use explicit screenshots stored beside the plan:

```powershell
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx --screenshot-dir screenshots
```

Use 1920 x 1080 viewport sources where practical. XLSX previews are 480 x 270
with no overlay text; interaction images use only a bold red rectangle.

Export CSV:

```powershell
python scripts/export_tracking_plan_csv.py plan.json --output plan.csv
```

Compare plan versions:

```powershell
python scripts/diff_tracking_plans.py plan-v1.json plan-v2.json
```

Migrate an older contract:

```powershell
python scripts/migrate_tracking_plan.py old-plan.json --output plan-v2.json
```

Check official catalog metadata or live drift:

```powershell
python scripts/check_official_catalog.py --offline
python scripts/check_official_catalog.py
```

Check whether the installed skill matches the repository:

```powershell
python scripts/check_installed_skill_sync.py
```

## Validation

Before release:

```powershell
ruff check .
python -m compileall -q scripts skill/scripts tests
python -m unittest discover -s tests
python -m coverage run --source=skill/scripts -m unittest discover -s tests
python -m coverage report --include="skill/scripts/validate_tracking_plan.py,skill/scripts/tracking_plan_validation_*.py,skill/scripts/ecommerce_matrix.py,skill/scripts/official_ga4_catalog.py,skill/scripts/generate_tracking_plan_workbook.py,skill/scripts/adapt_tracking_plan_workbook.py,skill/scripts/inspect_tracking_plan_template.py" --fail-under=80
python -m coverage report --include="skill/scripts/browser_environment.py,skill/scripts/discover_site_journeys_playwright.py" --fail-under=70
python scripts/check_official_catalog.py --offline
python scripts/validate_package.py
git diff --check
```

The GitHub workflows run the package on Windows and Ubuntu. A scheduled workflow
checks whether the official GA4 recommended-event page has drifted from the
bundled catalog.

## Privacy And Safety

Do not commit client workbooks, generated plans, screenshots, container IDs,
measurement IDs, request logs, credentials, personal data, payment data, or
private business information. Generic examples use `example.com` and placeholder
values only.

## Versioning

The GA4-only v2 contract is a breaking change from earlier multi-platform
drafts. Schema `2.2.0` adds explicit event access context and representative or
all-scenario screenshot coverage. Future minor releases add compatible
analyst or scenario improvements; patch releases fix documentation,
validation, or rendering defects.
