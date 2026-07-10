# Official Catalog Maintenance

Use this workflow when Google changes the GA4 recommended-event reference or
before a release that changes event or ecommerce guidance.

Check bundled metadata without network access:

```powershell
python scripts/check_official_catalog.py --offline
```

Compare the bundled catalog with the live official reference:

```powershell
python scripts/check_official_catalog.py
```

When drift is reported:

1. Inspect the official Google documentation change.
2. Regenerate the recommended-event and scenario catalogs.
3. Review required, conditional, recommended, and optional parameter meaning.
4. Update scenario judgement only when the official semantics changed.
5. Run package validation and scenario regression tests before release.

Do not make live-document availability a normal tracking-plan delivery
dependency. The skill must still work from the bundled catalog and mark live
verification unavailable when browsing cannot be used.
