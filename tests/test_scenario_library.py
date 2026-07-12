from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "skill" / "references" / "03-rules" / "library-ga4-event-scenarios.json"
PARAMETERS = ROOT / "skill" / "references" / "03-rules" / "library-parameters.json"


class ScenarioLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.library = json.loads(LIBRARY.read_text(encoding="utf-8"))
        cls.parameters = json.loads(PARAMETERS.read_text(encoding="utf-8"))

    def test_distinct_lead_and_customer_space_patterns_are_available(self) -> None:
        names = {item["event"] for item in self.library["typical_custom_events"]}
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

    def test_custom_events_are_unique_governed_and_machine_safe(self) -> None:
        events = self.library["typical_custom_events"]
        names = [item["event"] for item in events]
        self.assertEqual(len(names), len(set(names)))
        for item in events:
            with self.subTest(event=item["event"]):
                self.assertRegex(item["event"], r"^[a-z][a-z0-9_]*$")
                self.assertGreaterEqual(len(item["use_when"].split()), 6)
                self.assertGreaterEqual(len(item["prefer_official_if"].split()), 5)
                self.assertTrue(item["parameters"])

    def test_scenario_playbooks_cover_core_daily_business_models(self) -> None:
        scenarios = " ".join(item["scenario"].lower() for item in self.library["scenario_playbooks"])
        for expected in ("ecommerce", "lead", "account", "subscription", "booking", "saas"):
            with self.subTest(expected=expected):
                self.assertIn(expected, scenarios)
        self.assertIn("Official Google documentation first", self.library["source_priority"])
        self.assertNotIn("Codex-assisted", self.library["scope"])

    def test_parameter_library_has_unique_complete_generic_entries(self) -> None:
        parameters = [parameter for family in self.parameters["families"] for parameter in family["parameters"]]
        names = [parameter["parameter_name"] for parameter in parameters]
        self.assertEqual(len(names), len(set(names)))
        for parameter in parameters:
            with self.subTest(parameter=parameter["parameter_name"]):
                self.assertRegex(parameter["parameter_name"], r"^(?:items\[\][.])?[a-z][a-z0-9_.]*$")
                self.assertTrue(parameter["display_name"])
                self.assertIn(parameter["scope"], {"event", "item", "user", "implementation"})
                self.assertGreaterEqual(len(parameter["value_rules"].split()), 4)
                self.assertFalse(re.search(r"\b(?:women|lingerie|shoes|men)\b", parameter["value_rules"], re.I))


if __name__ == "__main__":
    unittest.main()
