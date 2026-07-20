# Execution Commands

Use only the commands needed for the current plan.

## Scaffold And Browser Preflight

Create a focused v3 draft. Browser discovery remains required independently of
the screenshot choice.

```powershell
python scripts/init_tracking_plan.py https://www.example.com/ --site-scope whole_site --journey-name "Initial journey" --output plan.json
python scripts/inspect_browser_environment.py
```

Use `--screenshots not_requested` only when the requester excludes screenshot
delivery. Set `--workbook-language en|fr` and repeat `--site-language` for every
observed or confirmed site language.

## Website Discovery

Static discovery is supporting evidence only. It exits non-zero when it cannot
produce usable coverage and never authorizes a complete rendered-discovery claim:

```powershell
python scripts/discover_site_journeys.py https://www.example.com/ --output site-discovery.json
```

Rendered discovery captures dynamic navigation and routes without submitting
forms or mutating live state. It reports `completed`, `partial`, or `blocked`
and exits non-zero unless coverage completed:

```powershell
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --browser auto --output site-discovery-rendered.json
```

Use an interactive browser or Playwright MCP with synthetic information for
signup and authenticated journeys. If access fails, record the gap. Do not
claim site-specific gated behavior as observed; retain applicable official or
recurrent sector outcomes only as explicit recommendations with confirmation
dependencies.

## Official Source Check

Resolve official event definitions, trigger guidance, parameter rows, and
conditions from current Google documentation before publication. The local
catalog command checks bundled metadata and compares recommended-event
definitions and parameters, ecommerce trigger guidance, and automatic and
enhanced-measurement triggers and documented parameters with live Google
documentation:

Use offline mode only for catalog maintenance:

```powershell
python scripts/check_official_catalog.py --offline
```

For a deliverable, bind a live receipt to the exact draft, then resolve a new
artifact. The receipt covers every official source referenced by the plan and
the current bundled catalog signature:

```powershell
python scripts/check_official_catalog.py --plan draft-plan.json --receipt official-source-receipt.json
python scripts/resolve_tracking_plan.py draft-plan.json --receipt official-source-receipt.json --output resolved-plan.json
```

A failed, offline, stale, incomplete, or catalog-mismatched receipt blocks
resolution. Never stamp source dates manually.

## Plan Validation

```powershell
python scripts/validate_tracking_plan.py resolved-plan.json
python scripts/validate_tracking_plan.py resolved-plan.json --warnings-as-errors
```

The validator checks v3 structure, journey coherence, official source
locators, canonical wording and trigger basis, event-specific parameter
requiredness, classification, availability and propagated-value lineage,
custom-parameter official-gap decisions, value-level evidence, ecommerce
scope, dataLayer parity, CMP timing, browser coverage, screenshots, privacy,
and client-template policy.

## Human Deliverables

```powershell
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output tracking-plan.xlsx
python scripts/export_tracking_plan_csv.py resolved-plan.json --output tracking-plan.csv
```

Screenshot Register is omitted when screenshots are not requested. When they
are requested, pass `--screenshot-dir screenshots` if the folder is not beside
the JSON.

For a client workbook, inspect first, prepare a SHA-bound structured mapping,
then adapt. The adapter always writes a fidelity report.

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-inventory.json
python scripts/adapt_tracking_plan_workbook.py resolved-plan.json client-template.xlsx --mapping template-mapping.json --output tracking-plan.xlsx
```

If the inventory reports a workbook feature the approved backend cannot
preserve, adaptation stops. Do not switch to an undeclared editor or generate
an approximate clone.
