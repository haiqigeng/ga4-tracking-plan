from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from validate_tracking_plan import validate_plan_data  # noqa: E402


class TrackingPlanValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))

    def codes(self, plan: dict) -> set[str]:
        return {issue.code for issue in validate_plan_data(plan)}

    def test_generic_fixture_passes(self) -> None:
        self.assertEqual(validate_plan_data(copy.deepcopy(self.fixture)), [])

    def test_missing_event_evidence_is_rejected(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_evidence"] = plan["screenshot_evidence"][1:]
        self.assertIn("SCREENSHOT_EVENT_MISSING", self.codes(plan))

    def test_weak_analysis_use_is_rejected(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["analysis_use"] = "reporting"
        self.assertIn("EVENT_ANALYSIS_USE_WEAK", self.codes(plan))

    def test_unconfirmed_parameter_needs_owner(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["parameters"][0]["availability"] = "to_confirm"
        plan["parameters"][0]["data_owner"] = "TBD"
        self.assertIn("PARAMETER_DATA_OWNER_MISSING", self.codes(plan))

    def test_ecommerce_event_requires_items(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["ga4_payload"]["items"] = []
        self.assertIn("ECOMMERCE_ITEMS_MISSING", self.codes(plan))

    def test_value_requires_currency(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["ga4_payload"]["parameters"]["value"] = 25.0
        event["ga4_payload"]["parameters"].pop("currency", None)
        self.assertIn("CURRENCY_MISSING", self.codes(plan))

    def test_official_event_cannot_be_marked_custom(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "search")
        event["classification"] = "custom"
        self.assertIn("GA4_OFFICIAL_EVENT_MARKED_CUSTOM", self.codes(plan))


if __name__ == "__main__":
    unittest.main()
