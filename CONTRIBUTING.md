# Contributing

Keep contributions focused on GA4 web tracking-plan creation and review.

Good changes improve business reasoning, journey coverage, official GA4 event
selection, ecommerce correctness, parameter availability, data ownership,
privacy, workbook readability, or deterministic validation.

## Rules

- Start from an analyst or developer use case.
- Check GA4 claims against current official Google documentation.
- Keep detailed rules in `skill/references/03-rules/`.
- Keep `skill/SKILL.md` concise and update it only when behavior changes.
- Keep examples generic and free of client data.
- Keep client-template replacement fail-closed when formulas, protection,
  tables, validations, comments, or images are present.
- Do not add another analytics platform, runtime testing, GTM mutation, or
  unrelated implementation scope.
- Add tests for new validator, renderer, migration, or catalog behavior.

## Validation

```powershell
ruff check .
python -m compileall -q scripts skill/scripts tests
python -m unittest discover -s tests
python -m coverage run --source=skill/scripts -m unittest discover -s tests
python scripts/validate_fresh_agent_evals.py
python scripts/check_official_catalog.py --offline
python scripts/validate_package.py
```

Release assets must be created with `scripts/create_release_package.py` and
must contain only generic reusable files.
