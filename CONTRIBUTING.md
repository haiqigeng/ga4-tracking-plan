# Contributing

Keep contributions focused on the human and implementation utility of GA4 web
tracking plans.

## Rules

- Start from a real analyst or developer need.
- Preserve the single adaptive workflow and single quality standard; do not add
  small, large, quick, enterprise, or event-count modes.
- Resolve selected event and parameter semantics from current official Google
  documentation before designing custom semantics.
- Keep every event contract exact: its trigger, event-specific parameters,
  finite values, source paths, and quoted dataLayer example must agree.
- Keep internal research, confidence, governance, privacy, and agent metadata
  out of the default visible workbook.
- Keep examples generic and free of client or credential data.
- Preserve supplied templates unless a requested semantic change requires an
  explicitly mapped edit.
- Add regression tests for validator, renderer, import, diff, or adaptation
  behavior.

## Validation

```powershell
ruff check .
python -m compileall -q scripts skill/scripts skill/tests
python -m unittest discover -s skill/tests
python scripts/validate_package.py
python scripts/inspect_browser_environment.py
```

For a release, keep `pyproject.toml` and `skill/release.json` synchronized.
Create assets only with `scripts/create_release_package.py`; the tag must match
the semantic version.
