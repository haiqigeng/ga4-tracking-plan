# Workbook Generation

Use this workflow for the analyst-facing XLSX deliverable.

1. Create or migrate the GA4-only structured plan.
2. When a client template exists, inspect its sheets, headers, formulas,
   formatting, and protected structure before deciding the mapping.
3. Validate the JSON.
4. Confirm journey grouping, event consolidation, parameter availability, and
   ecommerce isolation.
5. Confirm every event has a complete dataLayer example or an explicit
   no-manual-push decision and that GTM paths map to final GA4 parameters.
6. After the event model is final, assign screenshot coverage: one
   representative scenario for repetitive generic events, or every materially
   different visible scenario for finite events.
7. Capture 1920 x 1080 viewport evidence where practical. Use no labels or
   captions inside images; add only a bold red rectangle around an interaction
   area, confirmation, or error state. Page views normally need no rectangle.
8. Put screenshot files in a `screenshots` folder beside the JSON, or pass a
   folder explicitly.
9. Generate the default or mapped client workbook.
10. Review every 480 x 270 preview at normal spreadsheet zoom.

```powershell
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx --screenshot-dir screenshots
```

Inspect and adapt a client template:

```powershell
python scripts/inspect_tracking_plan_template.py client-template.xlsx --output template-inventory.json
python scripts/adapt_tracking_plan_workbook.py plan.json client-template.xlsx --mapping sheet-mapping.json --output plan.xlsx
```

The optional mapping is a JSON object whose keys are canonical sheet names and
whose values are client sheet names. Unmapped client-owned sheets are retained.
Review the adapted workbook because formulas, protected ranges, and unusual
merged layouts can require analyst judgement.

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
- Use human labels, value rules, availability, and owners in Parameter Reference.
- Keep Event Matrix as the main working tab and group related journeys.
- Keep complete per-event implementation examples in DataLayer Examples rather
  than expanding Event Matrix cells into long code blocks.
- Keep screenshot rows concise and link them explicitly to events.
- Do not expose internal IDs, rationale, agent instructions, or runtime test cases.
- Use standardized 480 x 270 previews rather than shrinking full-page captures.
- Reject duplicate rendered previews; use one shared-evidence row or capture
  the actual distinct scenario.
