from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from check_official_catalog import parse_event_names, parse_last_updated  # noqa: E402


class OfficialCatalogTests(unittest.TestCase):
    def test_official_html_parsing(self) -> None:
        page = '<h3 id="login"><code>login</code></h3><h3 id="purchase"><code>purchase</code></h3>Last updated 2026-06-26 UTC'
        self.assertEqual(parse_event_names(page), {"login", "purchase"})
        self.assertEqual(parse_last_updated(page), "2026-06-26")


if __name__ == "__main__":
    unittest.main()
