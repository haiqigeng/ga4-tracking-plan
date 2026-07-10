# Corpus Review Workflow

Use this file when learning from historical tracking plans.

## Privacy-Safe Inventory

On Windows, create an inventory outside the repository:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/analyze_tracking_plan_corpus.ps1 -InputFolder "C:\path\to\tracking-plans" -OutputJson "C:\path\to\inventory.json"
```

The inventory keeps counts, sheet names, dimensions, and GA4/legacy scenario
signals. Do not commit source workbooks or generated inventories.

## Review Steps

1. Classify each source as GA4, Universal Analytics legacy, mixed, or unknown.
2. Extract only reusable patterns: business scenarios, journey grouping,
   parameter families, workbook readability, and anti-patterns.
3. Do not copy client names, URLs, screenshots, IDs, GTM IDs, measurement IDs,
   raw workbook rows, or private business language.
4. Treat Universal Analytics as legacy context only.
5. Promote a lesson only when it is generic, privacy-safe, official-first,
   human-readable, and useful to analysts or developers.

Use `references/03-rules/review-corpus-learning-policy.md` for the decision
policy. Extract business and workbook lessons only. Ignore non-GA4 event names,
parameters, payloads, and platform-specific structures.
