from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "skill" / "references" / "03-rules" / "library-ga4-event-scenarios.json"


class ScenarioLibraryTests(unittest.TestCase):
    def test_distinct_lead_and_customer_space_patterns_are_available(self) -> None:
        library = json.loads(LIBRARY.read_text(encoding="utf-8"))
        names = {item["event"] for item in library["typical_custom_events"]}
        expected = {
            "newsletter_subscribe",
            "contact_submit",
            "catalog_request",
            "view_order_history",
            "view_order",
            "start_return",
            "cancel_order",
            "update_profile",
            "update_preferences",
            "password_reset",
        }
        self.assertTrue(expected <= names)


if __name__ == "__main__":
    unittest.main()
