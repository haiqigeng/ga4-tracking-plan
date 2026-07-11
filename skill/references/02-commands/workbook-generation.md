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
6. Add one explicit screenshot-evidence row for every event. Use a single
   shared row when one image deliberately supports several events.
7. Put screenshot files in a `screenshots` folder beside the JSON, or pass a
   folder explicitly.
8. Generate the default or mapped client workbook.
9. Review every visible sheet at normal spreadsheet zoom.

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
rectangle. Store crop and annotation coordinates in `screenshot_evidence` so
the generated preview is reproducible.

## Human Readability

- Keep the Overview limited to document details, navigation, and version history.
- Keep official links and implementation rules in GTM Protocol.
- Use human labels, value rules, availability, and owners in Parameter Reference.
- Keep Event Matrix as the main working tab and group related journeys.
- Keep complete per-event implementation examples in DataLayer Examples rather
  than expanding Event Matrix cells into long code blocks.
- Keep screenshot rows concise and link them explicitly to events.
- Do not expose internal IDs, rationale, agent instructions, or runtime test cases.
- Use compact, standardized previews rather than shrinking full-page captures.
