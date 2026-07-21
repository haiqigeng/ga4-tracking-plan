# Contributing

Keep contributions focused on GA4 web tracking-plan creation and review.

Good changes improve business reasoning, journey coverage, official GA4 event
selection, ecommerce correctness, parameter availability, data ownership,
privacy, workbook readability, or deterministic validation.

## Rules

- Start from an analyst or developer use case.
- Check the complete event-specific GA4 parameter table against current
  official Google documentation before proposing custom parameters.
- Keep detailed rules in `skill/references/03-rules/`.
- Keep `skill/SKILL.md` concise and update it only when behavior changes.
- Keep examples generic and free of client data.
- Keep client-template replacement fail-closed when formulas, protection,
  tables, validations, comments, or images are present.
- Do not add another analytics platform, runtime testing, GTM mutation, or
  unrelated implementation scope.
- Add tests for new validator, renderer, migration, or catalog behavior.
- Do not add a runtime utility without an explicit product need and maintainer
  approval; prefer extending an existing validated contract or rule.

## Validation

```powershell
ruff check .
python -m compileall -q scripts skill/scripts maintenance/scripts tests
python -m unittest discover -s tests
python -m coverage run --source=skill/scripts -m unittest discover -s tests
python scripts/validate_eval_manifest.py
python scripts/check_official_catalog.py --offline
python scripts/inspect_browser_environment.py
python scripts/validate_package.py
```

Release assets must be created with `scripts/create_release_package.py` and
must contain only generic reusable files. Keep the versions in
`pyproject.toml` and `skill/release.json` synchronized; the release tag must
match that version.

`validate_eval_manifest.py` checks only evaluation-case structure. A real
fresh-agent release gate requires clean sessions and a completed result file:

```powershell
python scripts/validate_fresh_agent_evals.py --results path\to\fresh-agent-results.json
```
