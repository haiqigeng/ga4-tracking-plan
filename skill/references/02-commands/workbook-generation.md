# Workbook Generation

Use this workflow for the analyst-facing XLSX deliverable.

1. Create or migrate the GA4-only structured plan.
2. Decide the workbook and controlled-value languages from the client template,
   website language scope, selector, locale routes, and market structure.
3. When a client template exists, inspect its complete workbook surface before
   deciding the mapping: sheets, states, dimensions, merges, styles, formulas,
   tables, filters, validations, conditional formatting, comments, links,
   images, print setup, protection, named ranges, and unsupported OOXML parts.
4. Resolve every official event definition and parameter row from current
   Google documentation, including attached conditions and source locators.
   Produce a live source receipt for the exact draft and resolve a new JSON
   artifact.
5. Validate the resolved artifact. Rendering must not enrich or repair it.
6. Confirm journey grouping, event consolidation, parameter availability, and
   ecommerce isolation. Review each selected event's complete official table;
   start with mandatory and applicable conditional parameters, then prefer
   other applicable official fields when evidence, use, and a feasible source
   support them. Do not copy every row mechanically, and require explicit
   taxonomy/use evidence for category levels four and five.
7. Confirm every custom parameter records the official gap, reporting purpose,
   event-specific classification, source, registration decision, cardinality,
   privacy, and persistence when carried across events.
8. Use browser or client evidence to exhaust practical finite values and record
   their provenance. Use precise rules for dynamic domains.
9. Confirm every event has a complete dataLayer example or an explicit
   no-manual-push decision and that GTM paths map to final GA4 parameters. Do
   not keep a duplicate GA4 payload or ecommerce profile in the plan.
10. Confirm page/core context uses `core_context_before_cmp_ready`, every other
   manual event uses `after_cmp_ready`, and page/user context is complete.
11. After the event model is final, assign screenshot coverage: one
   representative scenario for repetitive generic events, or every materially
   different visible scenario for finite events.
12. When screenshots are required, actively discover and attempt Playwright MCP
   before using a fallback browser. Only bypass that attempt when final image files
   were supplied by the requester or screenshots were explicitly excluded.
   This screenshot choice never waives required live browser journey discovery.
13. Capture 1920 x 1080 viewport evidence where practical. Use no labels or
   captions inside images; add only a bold red rectangle around an interaction
   area, confirmation, or error state. Page views normally need no rectangle.
14. Record the `screenshot_capture` outcome. For blocked or partial capture,
   write a concise notice that will appear at the top of Screenshot Register and
   repeat it in the delivery response. Use `blocked`, never an unresolved final
   status, when required evidence cannot be captured.
15. Put screenshot files in a `screenshots` folder beside the JSON, or pass a
   folder explicitly.
16. Generate the default workbook from the validated resolved JSON, or apply an
    artifact-bound strict client-template cell write map. The generator rejects
    a row marked captured when its image file is missing.
17. For strict templates, compare the saved result with the source and allow
    only the mapped cell-value changes. Deliver the fidelity report with source,
    mapping, and output hashes. Any other difference blocks delivery.
18. Review every 480 x 270 preview at normal spreadsheet zoom.

```powershell
python scripts/check_official_catalog.py --plan draft-plan.json --receipt official-source-receipt.json
python scripts/resolve_tracking_plan.py draft-plan.json --receipt official-source-receipt.json --output resolved-plan.json
python scripts/validate_tracking_plan.py resolved-plan.json
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output plan.xlsx
python scripts/generate_tracking_plan_workbook.py resolved-plan.json --output plan.xlsx --screenshot-dir screenshots
```

Inspect and adapt a client template:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-inventory.json
python scripts/adapt_tracking_plan_workbook.py resolved-plan.json client-template.xlsx --mapping sheet-mapping.json --output plan.xlsx
```

For final client delivery, use a strict mapping with explicit writes:

```json
{
  "mode": "strict_client_template",
  "mapping_id": "client_tracking_plan_v1",
  "template_sha256": "<sha256 from template inventory>",
  "cell_writes": [
    {"sheet": "Overview", "cell": "B4", "value_path": "$.document.version"},
    {"sheet": "Events", "cell": "V10", "value_path": "$.events[0].event_name"}
  ]
}
```

Strict mode does not create or replace sheets and preserves all formatting and
workbook features outside the write map. Use literal `value` only when the
content is intentionally derived during template mapping. A write that would
replace a formula requires explicit cell-level approval.

Whole-sheet replacement and legacy string-to-string mappings are unsupported.
When the client explicitly approves new structure, use
`approved_structural_extension` with a declared source-sheet clone, target
sheet, approval reason, and mapped writes; the extension fidelity report must pass.

Use `scripts/annotate_screenshot.py` when an interaction target needs a red
rectangle. The utility does not add text. Store crop and annotation coordinates
in `screenshot_evidence` so the generated preview is reproducible. Tall and
full-page sources require an explicit crop; silent top cropping is prohibited.

## Coverage Choice

Use one `representative` scenario for highly repetitive events such as
`page_view`, `view_item_list`, `select_item`, and `view_item`. Do not capture
every page, category, list, or product.

Use `all_material_scenarios` for finite visible outcomes such as header, menu,
submenu, and footer navigation; login or signup success; distinct payment
failure states; form success; returns; cancellation; profile changes; and
preference changes. Capture different triggers or visible states, not every
parameter value.

## Human Readability

- Keep the Overview limited to document details, navigation, and version history.
- Keep official links and implementation rules in GTM Protocol.
- Localize fixed human labels to French when `workbook_language` is `fr`, while
  keeping sheet names and technical event/parameter identifiers stable.
- Use human labels, value rules, availability, and owners in Parameter Reference.
- Use official definitions and attached conditions for official parameters;
  use equally concrete business definitions for custom parameters.
- Keep Event Matrix as the main working tab and group related journeys.
- Keep event summaries separate from precise website-specific triggers.
- Keep complete per-event implementation examples in DataLayer Examples rather
  than expanding Event Matrix cells into long code blocks.
- Keep screenshot rows concise and link them explicitly to events.
- Do not expose internal IDs, rationale, agent instructions, or runtime test cases.
- Use standardized 480 x 270 previews rather than shrinking full-page captures.
- Reject duplicate rendered previews; use one shared-evidence row or capture
  the actual distinct scenario.
