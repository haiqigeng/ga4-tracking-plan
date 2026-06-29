# GA4 Tracking Plan

[![Validate skill](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/HQ-Guillaume/ga4-tracking-plan/actions/workflows/validate-skill.yml)

A reusable AI skill for creating GA4 tracking plans with the mindset of a real
web analyst.

The goal is simple: help analytics, marketing, ecommerce, and implementation
teams decide what a website should measure, why it matters, how it should be
implemented, and how it can be tested later. The skill is not only an event
list generator. It starts from business context, journeys, expected actions,
analysis needs, and future scalability before proposing events and parameters.

GA4 is the default platform. Piano Analytics is supported only when it is
requested or clearly in scope. Universal Analytics is treated as legacy context
only.

## Who This Is For

- Web analysts who need to create or review a tracking plan.
- Marketing teams who need reliable acquisition, ecommerce, lead, and campaign
  measurement.
- Ecommerce teams who need clean product, cart, checkout, and purchase tracking.
- Developers who need a clear GTM/dataLayer implementation specification.
- QA teams who need a plan that can later be tested in GTM Preview, DebugView,
  and network requests.
- Agencies, consultants, or AI agents such as Codex, Claude Code, and Gemini
  that need repeatable tracking-plan rules.

## Problems It Helps Solve

- Tracking plans that list too many events without explaining the business
  reason.
- Ecommerce events mixed with custom click events or non-official parameters.
- Custom events created when a GA4 native, recommended, or ecommerce event would
  be better.
- French labels, campaign names, filter values, or CTA text that are not
  normalized for reporting.
- Parameters that are hard to understand, too high-cardinality, or risky for
  privacy.
- Workbooks that are difficult for humans to read or use in implementation.
- Missing screenshot evidence, unclear QA expectations, or tracking plans that
  cannot scale into a later recette workflow.

The skill is designed to answer one practical question:

> What should this website or journey measure in GA4 so teams can analyse,
> implement, and test the setup reliably?

## How Plan Creation Works

The workflow follows the order a web analyst would normally use.

1. **Confirm the scope and template**
   Identify the website, journeys, pages, existing tracking-plan template,
   naming convention, platform, and expected delivery format.

2. **Understand the business context**
   Clarify what the page or journey is supposed to do: sell products, generate
   leads, help users search, support customer service, create accounts, or move
   users through checkout.

3. **Map website coverage**
   For whole-site work, build a coverage map from user scope, existing files,
   browser or Playwright evidence, navigation, sitemap, robots.txt, and static
   discovery. Sitemap and robots are support evidence, not the only source of
   journey importance.

4. **Choose official-first events**
   Use GA4 automatic, enhanced-measurement, recommended, and ecommerce events
   when their meaning fits the action. Ecommerce events keep the official GA4
   format and stay separate from custom interactions.

5. **Design custom events only when needed**
   A custom event must answer a clear business or diagnostic question. The plan
   records official alternatives considered, required parameters, privacy notes,
   and QA expectations.

6. **Define useful parameters**
   Parameters get human names, descriptions, value rules, examples, custom
   definition guidance, cardinality risk, and privacy risk. Controlled values
   should use lowercase ASCII `snake_case`, with French accents removed.

7. **Prepare the XLSX tracking plan**
   The workbook keeps the overview short, puts links and implementation rules in
   the GTM protocol tab, keeps parameters readable, and groups events by journey
   in the Event Matrix.

8. **Prepare evidence and QA readiness**
   The workbook includes a Screenshot Register row for each event. Accessible
   events can use embedded screenshot evidence. Login, account, checkout,
   payment, and other credential-gated actions can use `skip_allowed` until a
   safe test account or environment is available.

## Inputs

The skill can work from one or more of these sources:

- Website URL or list of URLs.
- Journey description, page scope, business goals, expected actions, and
  analysis needs.
- Existing tracking plan, workbook template, dev specification, naming
  convention, or event inventory.
- Sitemap, robots.txt, navigation evidence, screenshots, or browser findings.
- GA4, GTM, dataLayer, Piano Analytics, or QA context when available.

When no client template or naming convention exists, the skill uses a
greenfield best-practice template.

## Outputs

Depending on the request, the skill can produce:

- A GA4-first XLSX tracking plan.
- A structured JSON plan that can be validated and reused for future QA
  automation.
- A Parameter Reference with variable names, display names, value rules,
  examples, custom definition guidance, and privacy notes.
- A journey-grouped Event Matrix for page, ecommerce, form, account, search,
  lead, support, and interaction events.
- A Screenshot Register with embedded, row-readable screenshot previews when
  evidence is available.
- QA Cases for later recette in GTM Preview, GA4 DebugView, and network checks.
- CSV exports for review or comparison.

## What It Will Not Do

- It will not create GTM tags or publish GTM versions unless a separate
  implementation phase is explicitly requested.
- It will not treat Universal Analytics as a valid target model for new GA4
  plans.
- It will not copy client-specific tracking plans, screenshots, domains, or
  test evidence into the reusable skill package.
- It will not send raw PII, passwords, payment details, customer identifiers,
  message bodies, addresses, emails, or phone numbers as normal GA4 event
  parameters.
- It will not create one custom event for every link, card, or button when one
  reusable event with controlled values is clearer.
- It will not force screenshots for login, checkout, payment, or other gated
  actions when safe credentials or a test environment are unavailable.

## Repository Structure

- `skill/SKILL.md`: agent-facing workflow and routing instructions.
- `skill/agents/openai.yaml`: Codex skill metadata and default prompt.
- `skill/assets/`: default XLSX workbook template.
- `skill/references/01-skill/`: product purpose, users, inputs, outputs,
  acceptance criteria, and non-goals.
- `skill/references/02-commands/`: validation, workbook generation, and corpus
  review commands.
- `skill/references/03-rules/`: scenario rules, GA4 event libraries, ecommerce
  policy, parameter library, privacy rules, QA readiness, Piano references, and
  schema examples.
- `skill/scripts/`: runtime helpers used by the installed skill.
- `scripts/`: root wrappers and repository maintenance scripts.
- `tests/`: regression tests for helper scripts and wrappers.
- `.github/`: validation, release packaging, issue templates, and pull request
  templates.

Rule files stay flat on purpose. Prefixes describe their role:
`analysis-*`, `decision-*`, `scenario-*`, `policy-*`, `library-*`,
`platform-*`, `review-*`, `schema-*`, `example-*`, and `qa-*`.

## Useful Commands

Run from the repository root.

Validate a structured tracking plan:

```powershell
python scripts/validate_tracking_plan.py skill/references/03-rules/example-ga4-tracking-plan.json
```

Generate an XLSX workbook:

```powershell
python scripts/generate_tracking_plan_workbook.py skill/references/03-rules/example-ga4-tracking-plan.json --output generated_tracking_plan.xlsx
```

If a `screenshots/` folder exists next to the JSON plan, the workbook generator
automatically embeds standardized screenshot previews in the Screenshot
Register. You can also pass a folder explicitly:

```powershell
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx --screenshot-dir screenshots
```

Export a CSV review file:

```powershell
python scripts/export_tracking_plan_csv.py skill/references/03-rules/example-ga4-tracking-plan.json --output generated_tracking_plan.csv
```

Create a first-pass website discovery file:

```powershell
python scripts/discover_site_journeys.py https://www.example.com/ --output site_discovery.json
```

Use rendered-DOM discovery only when dynamic menus, filters, forms, or SPA
routes matter:

```powershell
python -m pip install playwright
python -m playwright install chromium
python scripts/discover_site_journeys_playwright.py https://www.example.com/ --output site_discovery_rendered.json
```

Annotate an interaction screenshot before workbook generation:

```powershell
python scripts/annotate_screenshot.py source.png annotated.png --box x1,y1,x2,y2
```

Create a privacy-safe inventory of historical tracking plans:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/analyze_tracking_plan_corpus.ps1 -InputFolder "C:\path\to\tracking-plans" -OutputJson "C:\path\to\inventory.json"
```

Do not commit generated inventories or client source files.

## Safety And Privacy

This repository should only contain reusable skill instructions, generic
scripts, templates, schema examples, and public documentation.

Do not commit client workbooks, generated tracking plans, screenshots, GTM
exports, request logs, container IDs, domains, emails, phone numbers, addresses,
payment details, credentials, API keys, or temporary reports.

Generated deliverables should stay outside the repository unless they are
generic examples using placeholder domains such as `example.com`.

## Install Locally

Copy the `skill/` folder into your local Codex skills directory and rename it
to `ga4-tracking-plan`:

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
Use $ga4-tracking-plan to create a GA4 tracking plan for this ecommerce website.
```

## Validate A Release

```powershell
python -m pip install -r requirements.txt
python -m pip install ruff
ruff check .
python -m compileall -q scripts skill/scripts tests
python -m unittest discover -s tests
python scripts/validate_package.py
git diff --check
git status --short
```

Build a local release package:

```powershell
python scripts/create_release_package.py --version vX.Y.Z
```

The release package contains the reusable `skill/` folder, `requirements.txt`,
`README.md`, and `LICENSE`. Site-specific files should not be included.

## Maintenance Checklist

- Keep the README written for web analysts and marketing teams, not only AI
  agents.
- Keep `skill/SKILL.md` concise and move detailed rules into
  `skill/references/03-rules/`.
- Keep the reference structure stable: `01-skill` for orientation,
  `02-commands` for repeatable checks, and `03-rules` for workload rules.
- Keep examples generic and privacy-safe.
- Keep GA4, Piano Analytics, and legacy Universal Analytics boundaries clear.
- Run `validate_package.py` before every release.
- Run `create_release_package.py` or the GitHub release workflow before
  publishing.

## Versioning

Releases use semantic versioning while the skill is actively evolving:

- Minor versions for visible workflow, workbook, schema, or library
  improvements.
- Patch versions for bug fixes, validation fixes, and documentation cleanup.

Release notes should be written for web analysts and marketing stakeholders:
what improved, why it matters, how it was validated, and what limits remain.
