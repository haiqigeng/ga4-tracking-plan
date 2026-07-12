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

    def test_generic_event_uses_one_representative_screenshot(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["screenshot_coverage"] = {
            "mode": "all_material_scenarios",
            "scenarios": ["homepage", "content_page"],
        }
        self.assertIn("GENERIC_SCREENSHOT_MODE_INVALID", self.codes(plan))

    def test_all_material_screenshot_scenarios_need_evidence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][5]["screenshot_coverage"]["scenarios"].append("account_flyout")
        self.assertIn("SCREENSHOT_SCENARIOS_MISSING", self.codes(plan))

    def test_captured_interaction_screenshot_needs_red_rectangle(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_evidence"][1].update({"status": "captured", "file_name": "promotion.png"})
        self.assertIn("SCREENSHOT_ANNOTATION_MISSING", self.codes(plan))

    def test_required_screenshots_need_a_playwright_mcp_attempt(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_capture"]["playwright_mcp_attempt"]["status"] = "not_required"
        self.assertIn("PLAYWRIGHT_MCP_ATTEMPT_MISSING", self.codes(plan))

    def test_requester_supplied_screenshots_can_bypass_playwright_mcp(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_capture"] = {
            "requirement": "required",
            "playwright_mcp_attempt": {"status": "not_required", "detail": "Final screenshots were supplied by the requester."},
            "outcome": "captured",
            "delivery_notice": "Screenshots supplied by the requester are ready to embed in the workbook.",
        }
        event_names = {event["event_id"]: event["event_name"] for event in plan["events"]}
        for index, evidence in enumerate(plan["screenshot_evidence"], start=1):
            evidence.update({"status": "captured", "file_name": f"supplied_{index}.png"})
            if event_names[evidence["event_ids"][0]] != "page_view":
                evidence["annotation"] = {"x1": 10, "y1": 10, "x2": 100, "y2": 100}
        self.assertNotIn("PLAYWRIGHT_MCP_ATTEMPT_MISSING", self.codes(plan))

    def test_blocked_screenshot_outcome_cannot_leave_pending_evidence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_evidence"][0].update({"status": "captured", "file_name": "page.png"})
        self.assertIn("SCREENSHOT_CAPTURE_BLOCKED_MISMATCH", self.codes(plan))

    def test_no_screenshot_request_needs_not_needed_event_coverage(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_capture"] = {
            "requirement": "not_requested",
            "playwright_mcp_attempt": {"status": "not_required", "detail": "Screenshots were explicitly excluded."},
            "outcome": "not_requested",
            "delivery_notice": "Screenshots were not requested for this delivery.",
        }
        for event in plan["events"]:
            event["screenshot_coverage"] = {"mode": "not_needed", "scenarios": []}
        for evidence in plan["screenshot_evidence"]:
            evidence["status"] = "not_needed"
        self.assertEqual(validate_plan_data(plan), [])

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
