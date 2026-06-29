# Workbook Generation

Use this file when a tracking plan should be delivered as XLSX.

## Default Flow

1. Create or update the structured tracking-plan JSON.
2. Validate the JSON with `scripts/validate_tracking_plan.py`.
3. Draft the Event Matrix and generate the Screenshot Register from the event
   rows before final workbook generation.
4. Decide screenshot evidence needs for every event:
   - use clean screenshots for passive render/state events;
   - use rectangle-only red callouts for click, form submit, CTA, filter, menu,
     or other interaction targets;
   - use `skip_allowed` for login, credential-gated, account, checkout,
     payment, or otherwise restricted steps when approved credentials or a safe
     test environment are unavailable;
   - mark backend, unavailable, duplicated, or future-recette-only evidence
     clearly instead of forcing a screenshot.
5. Capture and embed representative screenshot previews when useful. One
   screenshot can support several events, and not every event needs a
   screenshot. When screenshots are full-page captures, crop them to a
   row-readable viewport preview before embedding; do not scale a very tall
   page screenshot into a tiny unreadable workbook image.
6. Generate the workbook with `scripts/generate_tracking_plan_workbook.py`.
7. Review the Event Matrix for journey grouping, value rules, and visual
   density.
8. When a client template is in scope, preserve the agreed sheet/column/style
   structure and record any necessary template differences in the structured
   JSON.
9. Keep generated workbooks outside the reusable skill package unless they are
   generic examples.

## Command

```powershell
python scripts/generate_tracking_plan_workbook.py path\to\tracking-plan.json --output path\to\tracking-plan.xlsx
```

To annotate a component/action screenshot before embedding it in a workbook:

```powershell
python scripts/annotate_screenshot.py path\to\source.png path\to\annotated.png --box x1,y1,x2,y2
```

## Human Readability Check

Before delivery, confirm:

- the Overview tab is limited to document details, workbook navigation, and
  version history;
- GTM Protocol contains shared implementation rules and official links;
- Parameter Reference uses human-readable labels and value rules;
- Event Matrix groups events by journey and compatible event family;
- Event Matrix uses one expected value/rule column per event slot and does not
  expose internal `event_id`, `screenshot_id`, `qa_id`, or tracking-row IDs;
- the visible Event Matrix row is called `event`; reserve `event_name` wording
  for GA4 event names or GA4 payload settings;
- Screenshot Register captures page/component evidence requirements and
  automation cues for every event; it should not expose local file-path/link
  columns or become a dense QA execution sheet;
- Screenshot Register status should use `capture_required`, `captured`,
  `shared_evidence`, `skip_allowed`, `not_needed`, or `blocked`;
- captured screenshot evidence should be embedded directly in the Screenshot
  Register, not only stored in a side folder;
- full-page captures should be standardized into compact viewport previews that
  let a reader identify the page or tracked action at normal spreadsheet zoom;
- screenshot previews for click, form submit, CTA, filter, menu, or other
  interaction events should highlight the target element with a red rectangle
  or equivalent callout; prefer rectangle-only annotations in workbook
  thumbnails because the event row already names the event;
- passive render/state evidence such as `page_view`, `view_item_list`,
  `view_item`, or checkout-step render screenshots should remain unannotated
  unless the capture is explicitly documenting a click target;
- QA Cases, when present, are compact support tabs rather than dense QA
  execution sheets;
- internal rationale stays in the structured plan, not as clutter in visible
  workbook tabs.
