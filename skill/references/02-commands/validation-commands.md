# Validation Commands

Use this file to decide which local checks to run and when.

## Contents

- [Package Checks](#package-checks)
- [Tracking Plan Scaffold](#tracking-plan-scaffold)
- [Tracking Plan JSON Checks](#tracking-plan-json-checks)
- [Website Discovery Helper](#website-discovery-helper)
- [Contract Migration](#contract-migration)
- [Workbook And CSV Checks](#workbook-and-csv-checks)
- [Fresh-Agent Acceptance](#fresh-agent-acceptance)
- [Release Package](#release-package)

## Package Checks

Run before committing or releasing the reusable skill package:

```powershell
ruff check .
python -m compileall -q scripts skill/scripts tests
python -m unittest discover -s tests
python -m coverage run --source=skill/scripts -m unittest discover -s tests
python -m coverage report --include="skill/scripts/validate_tracking_plan.py" --fail-under=90
python -m coverage report --include="skill/scripts/ecommerce_matrix.py" --fail-under=95
python -m coverage report --include="skill/scripts/adapt_tracking_plan_workbook.py" --fail-under=90
python -m coverage report --include="skill/scripts/inspect_tracking_plan_template.py" --fail-under=90
python -m coverage report --include="skill/scripts/init_tracking_plan.py" --fail-under=90
python -m coverage report --include="skill/scripts/tracking_plan_workbook_layout.py" --fail-under=85
python -m coverage report --include="skill/scripts/validate_tracking_plan.py,skill/scripts/tracking_plan_validation_*.py,skill/scripts/ecommerce_matrix.py,skill/scripts/official_ga4_catalog.py,skill/scripts/generate_tracking_plan_workbook.py,skill/scripts/tracking_plan_workbook_layout.py,skill/scripts/adapt_tracking_plan_workbook.py,skill/scripts/inspect_tracking_plan_template.py,skill/scripts/init_tracking_plan.py" --fail-under=88
python -m coverage report --include="skill/scripts/browser_environment.py,skill/scripts/discover_site_journeys_playwright.py" --fail-under=70
python scripts/validate_fresh_agent_evals.py
python scripts/validate_package.py
python scripts/check_official_catalog.py --offline
git diff --check
git status --short
```

If Python is unavailable, run the non-Python checks and state the Python
blocker.

## Tracking Plan Scaffold

Create the smallest useful page-context draft before website discovery:

```powershell
python scripts/init_tracking_plan.py https://www.example.com/ --journey-name "Initial journey" --output plan.json
```

The default draft remains blocked on the Playwright MCP screenshot attempt.
Use `--screenshots not_requested` only after the requester explicitly excludes
screenshots.

## Tracking Plan JSON Checks

Run when producing or reviewing a structured tracking plan:

```powershell
python scripts/validate_tracking_plan.py path\to\tracking-plan.json
python scripts/validate_tracking_plan.py path\to\tracking-plan.json --warnings-as-errors
```

The validator checks structure, journey alignment, analyst purpose, evidence
confidence, GA4 classifications, ecommerce scope, custom-event justification,
parameter availability and ownership, template policy, website coverage,
official verification, collection source, duplicate risk, screenshot mapping,
capture outcome and Playwright MCP attempt, privacy-sensitive names, and legacy
Universal Analytics fields.

## Website Discovery Helper

Run when a broad website scope needs support URL and journey evidence:

```powershell
python scripts/discover_site_journeys.py https://www.example.com/ --output path\to\site_discovery.json
```

The output is a privacy-safe completeness aid. It does not replace the
user/client scope, existing client files, manual browser exploration, or
Playwright for dynamic checkout, filters, account, forms, modals, or SPA
routes.

Use rendered-DOM discovery when dynamic navigation, filters, forms, or SPA
routes materially affect whole-site coverage:

```powershell
python -m pip install playwright
python scripts/inspect_browser_environment.py
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --browser auto --output path\to\site_discovery_rendered.json
```

The Playwright helper samples rendered pages without submitting forms, logging
in, placing orders, or mutating live state. For a gated journey, use an
interactive browser or Playwright MCP with synthetic information. If the real
journey cannot be completed, create no event behind authentication. When the
tracking plan requires screenshots, actively attempt Playwright MCP first and
record a visible blocked outcome if evidence cannot be captured.

## Contract Migration

Migrate an older plan to the GA4-only schema `2.4.0` contract:

```powershell
python scripts/migrate_tracking_plan.py old-plan.json --output plan-v2.json
```

Migration never invents a Playwright MCP attempt. Resolve any resulting
`not_recorded` screenshot-capture status before delivery.

## Workbook And CSV Checks

Run when generating reviewer-facing files:

```powershell
python scripts/generate_tracking_plan_workbook.py path\to\tracking-plan.json --output path\to\tracking-plan.xlsx
python scripts/export_tracking_plan_csv.py path\to\tracking-plan.json --output path\to\tracking-plan.csv
```

Generated files should remain outside the reusable skill package unless they
are deliberate, generic examples.

## Fresh-Agent Acceptance

Validate the reusable clean-session cases before release:

```powershell
python scripts/validate_fresh_agent_evals.py
python scripts/validate_fresh_agent_evals.py --results path\to\fresh-agent-results.json
```

Follow `fresh-agent-evaluation.md`; keep run artifacts outside the repository.

## Release Package

Run before attaching release assets manually:

```powershell
python scripts/create_release_package.py --version vX.Y.Z
```

The generated zip belongs in the ignored `release/` folder and should contain
only public reusable package files.
