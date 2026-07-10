# Workbook Generation

Use this workflow for the analyst-facing XLSX deliverable.

1. Create or migrate the GA4-only structured plan.
2. Validate the JSON.
3. Confirm journey grouping, event consolidation, parameter availability, and
   ecommerce isolation.
4. Add one explicit screenshot-evidence row for every event. Use a single
   shared row when one image deliberately supports several events.
5. Put screenshot files in a `screenshots` folder beside the JSON, or pass a
   folder explicitly.
6. Generate the workbook.
7. Review every visible sheet at normal spreadsheet zoom.

```powershell
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx
python scripts/generate_tracking_plan_workbook.py plan.json --output plan.xlsx --screenshot-dir screenshots
```

Use `scripts/annotate_screenshot.py` when an interaction target needs a red
rectangle. Store crop and annotation coordinates in `screenshot_evidence` so
the generated preview is reproducible.

## Human Readability

- Keep the Overview limited to document details, navigation, and version history.
- Keep official links and implementation rules in GTM Protocol.
- Use human labels, value rules, availability, and owners in Parameter Reference.
- Keep Event Matrix as the main working tab and group related journeys.
- Keep screenshot rows concise and link them explicitly to events.
- Do not expose internal IDs, rationale, agent instructions, or runtime test cases.
- Use compact, standardized previews rather than shrinking full-page captures.
