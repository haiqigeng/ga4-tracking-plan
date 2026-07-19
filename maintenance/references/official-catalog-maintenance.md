# Official Catalog Maintenance

Use this workflow when Google changes the GA4 recommended, ecommerce,
automatic, or enhanced-measurement references, or before a release that changes
official event guidance.

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
2. Regenerate the recommended-event and scenario catalogs. Regeneration also
   verifies the governed automatic and enhanced-measurement trigger and
   parameter records against their live source pages.
3. Review required, conditional, recommended, and optional parameter meaning.
4. Update scenario judgement only when the official semantics changed.
5. Run package validation and scenario regression tests before release.

Catalog regeneration requires live access to all governed official Google sources and
stops without modifying the catalogs when fetching or parsing fails. Use the
offline checker only to validate the already bundled metadata; never use an
offline fallback to claim that a catalog was refreshed.

The bundled catalog supports drafting and makes unavailable documentation
visible; it does not prove a publication-date live check. A final plan uses
`check_official_catalog.py --plan ... --receipt ...`, then
`resolve_tracking_plan.py` to bind the live receipt and resolved semantics to a
new artifact. The receipt must cover every official plan URL, match the local
catalog signature, and be dated on publication day. When browsing is
unavailable, keep verification pending and tell the analyst; never manufacture
a receipt or stamp the delivery date.
