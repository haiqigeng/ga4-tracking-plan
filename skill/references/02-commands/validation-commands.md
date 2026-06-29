# Validation Commands

Use this file to decide which local checks to run and when.

## Package Checks

Run before committing or releasing the reusable skill package:

```powershell
ruff check .
python -m compileall -q scripts skill/scripts tests
python -m unittest discover -s tests
python scripts/validate_package.py
git diff --check
git status --short
```

If Python is unavailable, run the non-Python checks and state the Python
blocker.

## Tracking Plan JSON Checks

Run when producing or reviewing a structured tracking plan:

```powershell
python scripts/validate_tracking_plan.py path\to\tracking-plan.json
python scripts/validate_tracking_plan.py path\to\tracking-plan.json --warnings-as-errors
```

The validator checks structure, journey alignment, event classifications,
official GA4 and Piano rules, ecommerce parameter scope, custom-event
justification, execution mode, template policy, website coverage decisions,
official verification, collection source, duplicate-risk decisions,
privacy-sensitive field names, and QA links.

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
python -m playwright install chromium
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --output path\to\site_discovery_rendered.json
```

The Playwright helper samples rendered pages without submitting forms, logging
in, placing orders, or mutating live state. Mark credential-gated journeys as
skipped or blocked unless approved test access is available.

## Workbook And CSV Checks

Run when generating reviewer-facing files:

```powershell
python scripts/generate_tracking_plan_workbook.py path\to\tracking-plan.json --output path\to\tracking-plan.xlsx
python scripts/export_tracking_plan_csv.py path\to\tracking-plan.json --output path\to\tracking-plan.csv
```

Generated files should remain outside the reusable skill package unless they
are deliberate, generic examples.

## Release Package

Run before attaching release assets manually:

```powershell
python scripts/create_release_package.py --version vX.Y.Z
```

The generated zip belongs in the ignored `release/` folder and should contain
only public reusable package files.
