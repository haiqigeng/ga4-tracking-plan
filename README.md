# GA4 Tracking Plan

[![Latest release](https://img.shields.io/github/v/release/haiqigeng/ga4-tracking-plan?sort=semver)](https://github.com/haiqigeng/ga4-tracking-plan/releases/latest) ![License](https://img.shields.io/github/license/haiqigeng/ga4-tracking-plan) ![Top language](https://img.shields.io/github/languages/top/haiqigeng/ga4-tracking-plan)

[![Validate skill](https://github.com/haiqigeng/ga4-tracking-plan/actions/workflows/validate-skill.yml/badge.svg)](https://github.com/haiqigeng/ga4-tracking-plan/actions/workflows/validate-skill.yml)

A reusable web-analyst skill for creating and reviewing accurate, useful, and
implementation-ready GA4 tracking plans. Tracking-plan quality is the product;
XLSX is one human delivery format.

It starts from the website, business goals, journeys, expected actions, and
analysis needs. It then resolves the selected events' current official Google
tables, retains mandatory and applicable conditional fields, preferentially
includes other applicable official parameters when evidence and use justify
them, and adds custom parameters only for a documented official gap. The result
is a plan that analysts and developers can act on.

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
- Multilingual plans with translated event schemas, inconsistent market values,
  or no explicit workbook-language decision.
- Finite value lists inferred from labels instead of observed in the website or
  confirmed by an authoritative client source.
- Mandatory parameters removed in the name of simplification, or every optional
  parameter copied without an analysis need.
- Generic event triggers and parameter summaries that do not tell a developer
  what the value means or when the event fires.
- Tracking plans that invent data the website does not currently expose.
- Journey events scattered across a workbook.
- Unreadable templates filled with internal or agent-oriented information.
- Screenshots guessed from filenames or reused without a clear reason.
- Screenshot evidence silently omitted even though the plan says it was captured.
- Client workbooks whose layout, formulas, styles, validations, or human working
  conventions are silently replaced during adaptation.

## Procedure

1. Confirm the website scope, pages, journeys, template, and naming convention.
2. Decide the website-language scope, workbook language, and controlled-value
   language. Multilingual plans use English; French-only plans may use French
   human wording and French semantic values while technical names stay English.
3. When a client workbook exists, inventory its sheets, blocks, rows, styles,
   formulas, validations, images, protection, and print settings before planning
   any write.
4. Understand the business goal, expected actions, analysis needs, and success
   signals.
5. Actively discover an available Playwright MCP, inspect browser readiness,
   then complete public signup and authenticated customer-space journeys with
   synthetic information. If the gated journey cannot be entered, record the
   gap and keep only applicable official or recurrent sector outcomes as
   clearly labelled recommendations; never claim site-specific behavior as observed.
6. Resolve official event meanings, implementation sections, parameter rows,
   requiredness, types, examples, and attached conditions from current Google
   documentation.
7. Select GA4 automatic, enhanced-measurement, recommended, and ecommerce
   events before considering custom events. Decide whether form outcomes share
   `generate_lead` or need separate success events.
8. Read the complete current official table for each selected event. Include
   mandatory fields and applicable conditional fields first. Prefer other
   applicable official fields when website evidence, business needs, recurrent
   analysis, activation, or a feasible source supports them, but do not copy
   every row mechanically. Category levels four and five require evidenced
   taxonomy depth and use.
9. Add a custom parameter only when the official fields do not answer the need.
   Record the official gap, event-specific classification, scope, reporting
   purpose, source, availability, ownership, registration decision,
   cardinality, privacy, and cross-event persistence when applicable.
10. Use the live website or authoritative client evidence to exhaust practical
   finite values. Each finite value keeps its original label, normalized value,
   language, mapping method, and evidence source. Dynamic values use precise rules.
11. Specify one complete developer-readable dataLayer and GA4 mapping example
   per event, using the project's `page`, `event_data`, `ecommerce`, and `user`
   wrappers. Native page/core context omits a Custom Event trigger and may
   precede CMP readiness; every other manual
   event follows CMP readiness.
12. Define connected-user state once in GTM Protocol when relevant, with GA4
   User-ID and user-property mappings kept separate from event payloads.
13. After event design, attempt screenshot capture with Playwright MCP: one
   representative image for repetitive generic events and all materially
   different scenarios for finite events.
14. If capture is blocked or partial, show the reason in Screenshot Register and
   tell the reviewer before returning the workbook.
15. Validate semantic quality and, for a client template, prove that only
    approved cells changed before returning the workbook.

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

When information is missing, the skill preserves it as unknown or as a clearly
labelled recommendation with a confirmation owner. It does not invent website
languages, finite values, gated capabilities, or observed journey coverage.

## Outputs

Without a client template, the main output is an XLSX workbook with five core tabs:

- `00 Overview`: document details, navigation, and version history;
- `01 GTM Protocol`: shared GTM/dataLayer rules and official links;
- `02 Parameter Reference`: definitions, values, event-specific classification
  and availability, owners, source lineage, and GA4 registration needs;
- `03 Event Matrix`: the main tracking plan grouped by journey;
- `04 DataLayer Examples`: complete per-event GTM implementation examples;
- `05 Screenshot Register` when screenshots are requested: explicit page and
  interaction evidence, with a visible notice when capture is incomplete.

With a client template, its information scope, sheet order, layout, styles,
formulas, validations, merges, images, and print setup remain the contract. The
skill can also produce validated JSON and a long-format CSV. Machine fields
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
- `scripts/`: repository wrappers and release maintenance.
- `maintenance/`: migrations, corpus review, catalog upkeep, and fresh-agent
  evaluation assets that are not installed with the runtime skill.
- `tests/`: unit and integration regression tests.

The three reference branches follow the same convention used by the companion
GTM skill family: orientation, execution, and professional judgement without
using those words as folder names.

## Install

Copy `skill/` to:

```text
%USERPROFILE%\.codex\skills\ga4-tracking-plan
```

For another AI agent, place `skill/` in that agent's supported skill or
instruction directory and load `SKILL.md` as the entry point. The workflow,
references, JSON contract, and Python tools are agent-neutral;
`skill/agents/openai.yaml` is optional OpenAI interface metadata.

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

When screenshots, dynamic interactions, checkout, forms, or unconfirmed gated
journeys are in scope, the workflow attempts Playwright MCP before a fallback.
The local preflight below checks whether a usable browser is also available:

```powershell
python scripts/inspect_browser_environment.py
```

The preflight prefers the eligible system default browser, including Microsoft
Edge through `msedge`. Playwright and its compatible `greenlet` runtime are
installed by `requirements.txt`; an import or driver failure is reported as a
blocking runtime error even when a supported system browser is present.

## Common Commands

Create a focused initial JSON draft:

```powershell
python scripts/init_tracking_plan.py https://www.example.com/ --journey-name "Initial journey" --site-language fr --workbook-language fr --output plan.json
```

The default draft keeps live browser discovery unresolved, independently of
the screenshot choice. Repeat
`--site-language` for multilingual sites; multilingual output is normalized to
English. Use
`--screenshots not_requested` only when the requester explicitly excludes
screenshots.

Create a live official-source receipt, resolve official wording into a new
artifact, then validate that exact artifact:

```powershell
python scripts/check_official_catalog.py --plan draft-plan.json --receipt official-source-receipt.json
python scripts/resolve_tracking_plan.py draft-plan.json --receipt official-source-receipt.json --output resolved-plan.json
python scripts/validate_tracking_plan.py resolved-plan.json
```

Generate the XLSX from the validated resolved plan:

```powershell
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output plan.xlsx
```

The receipt must come from live Google sources on the publication date, cover
every official URL used by the plan, match the bundled catalog, and bind both
the checked draft and resolved plan hashes. The renderer never enriches or
repairs the plan after validation.

Inspect and use a client workbook template:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-inventory.json
python scripts/adapt_tracking_plan_workbook.py resolved-plan.json client-template.xlsx --mapping strict-cell-mapping.json --output plan.xlsx --fidelity-report template-fidelity.json
```

Strict adaptation writes only explicitly mapped cells and then compares the
saved workbook with the exact SHA-bound source template. The fidelity report
records template, mapping, and output hashes; any unexpected change blocks delivery.
Templates containing features the editing backend cannot guarantee to preserve
are blocked instead of being called strictly adapted. Whole-sheet replacement
and legacy string mappings are unsupported.

Use explicit screenshots stored beside the plan:

```powershell
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output plan.xlsx --screenshot-dir screenshots
```

Use 1920 x 1080 viewport sources where practical. XLSX previews are 480 x 270
with no overlay text; interaction images use only a bold red rectangle.
The generator refuses any row marked captured when the referenced image is not
available, so a workbook cannot quietly claim that a missing screenshot exists.

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
python scripts/migrate_tracking_plan.py old-plan.json --output plan-v3.json
```

Check official catalog metadata without authorizing a delivery:

```powershell
python scripts/check_official_catalog.py --offline
```

Offline mode is maintenance-only. A deliverable uses the receipt-bound live
command shown above; initial scaffolds remain blocked until that step succeeds.

Check whether the installed skill matches the repository:

```powershell
python scripts/check_installed_skill_sync.py
```

## Validation

Before release:

```powershell
ruff check .
python -m compileall -q scripts skill/scripts maintenance/scripts tests
python -m unittest discover -s tests
python scripts/inspect_browser_environment.py
python scripts/validate_package.py
git diff --check
```

`pyproject.toml` and `skill/release.json` must carry the same semantic version.
The release packager rejects a tag/version mismatch, and the package validator
checks dependency parity, Playwright importability, package metadata, generated
outputs, privacy, and release cleanliness.

The GitHub workflows run the package on Windows and Ubuntu. CI validates the
fresh-agent case manifest but does not claim that an agent was executed. Real
fresh-agent results are a separate manual release gate. The cases cover
ecommerce, lead-model judgement, strict client templates, screenshot failure,
multilingual navigation, French localization, blocked authenticated discovery,
official wording, and parameter selection. A scheduled workflow checks event
and parameter semantics, not only names, against the official GA4 recommended,
ecommerce, automatic, and enhanced-measurement pages.

## Privacy And Safety

Do not commit client workbooks, generated plans, screenshots, container IDs,
measurement IDs, request logs, credentials, personal data, payment data, or
private business information. Generic examples use `example.com` and placeholder
values only.

## Versioning

The GA4-only v3 contract is a breaking change from v2. Schema `3.0.0` added
event-specific parameter requiredness and availability, reusable multi-journey
events, evidence-bearing finite values, a normalized official-source registry,
conditional screenshot sheets, and artifact-bound client-template fidelity.
Schema `3.1.0` adds compatible event-binding classification and source/
persistence lineage, plus an explicit official-gap assessment for custom
parameters. Future minor releases add compatible analyst or scenario
improvements; patch releases fix documentation, validation, or rendering
defects.
