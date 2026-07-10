from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

import discover_site_journeys as discovery  # noqa: E402


class DiscoverSiteJourneysTests(unittest.TestCase):
    def test_sitemap_fetch_errors_are_recorded(self) -> None:
        errors: list[discovery.SourceError] = []
        with patch.object(discovery, "fetch_text", side_effect=OSError("network unavailable")):
            urls = discovery.parse_sitemap("https://www.example.com/sitemap.xml", 10, errors)

        self.assertEqual(urls, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].source_type, "sitemap")
        self.assertIn("network unavailable", errors[0].message)

    def test_fetch_error_page_still_summarizes_without_crashing(self) -> None:
        pages = [{"url": "https://www.example.com/broken", "fetch_error": "timeout", "links": [], "forms": [], "buttons": []}]
        journeys = discovery.summarize_journeys(pages)

        self.assertEqual(journeys[0]["journey_id"], "content_navigation")
        self.assertEqual(journeys[0]["key_interactions"], ["page view"])


if __name__ == "__main__":
    unittest.main()
