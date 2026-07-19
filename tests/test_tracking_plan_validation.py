from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from official_source_receipt import finalize_receipt, tracking_plan_sha256  # noqa: E402
from validate_tracking_plan import validate_plan_data  # noqa: E402


class TrackingPlanValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))

    def codes(self, plan: dict) -> set[str]:
        return {issue.code for issue in validate_plan_data(plan)}

    def rebind_resolved_plan(self, plan: dict) -> None:
        receipt = copy.deepcopy(plan["official_source_check"])
        receipt["resolved_plan_sha256"] = tracking_plan_sha256(plan)
        plan["official_source_check"] = finalize_receipt(receipt)

    def test_generic_fixture_passes(self) -> None:
        self.assertEqual(validate_plan_data(copy.deepcopy(self.fixture)), [])

    def test_duplicate_payload_snapshot_is_rejected_with_migration_guidance(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["ga4_payload"] = {"event_name": "page_view"}
        self.assertIn("DUPLICATE_DERIVED_STATE", self.codes(plan))

    def test_missing_event_evidence_is_rejected(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_evidence"] = plan["screenshot_evidence"][1:]
        self.assertIn("SCREENSHOT_EVENT_MISSING", self.codes(plan))

    def test_optional_analysis_use_is_not_lexically_scored(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["analysis_use"] = "reporting"
        self.assertNotIn("EVENT_ANALYSIS_USE_WEAK", self.codes(plan))

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
        plan["screenshot_evidence"] = []
        self.rebind_resolved_plan(plan)
        self.assertEqual(validate_plan_data(plan), [])

        plan["screenshot_evidence"] = [{
            "evidence_id": "EVIDENCE-NOT-NEEDED",
            "scenario_id": "not_requested",
            "event_ids": [plan["events"][0]["event_id"]],
            "page_or_state": "No screenshot",
            "capture_objective": "No screenshot",
            "status": "not_needed",
            "file_name": "",
            "shared_reason": "",
            "notes": "Screenshots were excluded.",
        }]
        self.assertIn("SCREENSHOT_EVIDENCE_NOT_REQUESTED", self.codes(plan))

    def test_unconfirmed_parameter_needs_owner(self) -> None:
        plan = copy.deepcopy(self.fixture)
        binding = plan["events"][0]["parameter_bindings"][0]
        binding["availability"] = "to_confirm"
        binding["data_owner"] = "TBD"
        self.assertIn("EVENT_PARAMETER_OWNER_MISSING", self.codes(plan))

    def test_ecommerce_event_requires_items(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["data_layer"]["push"]["ecommerce"]["items"] = []
        self.assertIn("ECOMMERCE_ITEMS_MISSING", self.codes(plan))

    def test_refund_does_not_require_optional_items(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["event_name"] = "refund"
        event["data_layer"]["event_key"] = "refund"
        event["data_layer"]["push"] = {"event": "refund", "ecommerce": {"transaction_id": "T_123"}}
        event["parameter_bindings"] = [
            {
                "parameter_name": "transaction_id",
                "requirement": "required",
                "availability": "confirmed_available",
                "official_source_id": event["official_verification"]["source_id"],
                "official_source_locator": "transaction_id",
            }
        ]
        self.assertNotIn("ECOMMERCE_ITEMS_MISSING", self.codes(plan))

    def test_value_requires_currency(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["data_layer"]["push"]["ecommerce"]["value"] = 25.0
        event["data_layer"]["push"]["ecommerce"].pop("currency", None)
        self.assertIn("CURRENCY_MISSING", self.codes(plan))

    def test_official_event_cannot_be_marked_custom(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "search")
        event["classification"] = "custom"
        self.assertIn("GA4_OFFICIAL_EVENT_MARKED_CUSTOM", self.codes(plan))

    def test_lazy_event_summary_is_rejected(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["event_summary"] = "Official GA4 event."
        self.assertIn("EVENT_SUMMARY_LAZY", self.codes(plan))

    def test_lazy_event_trigger_is_rejected(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["trigger"] = "On page view"
        self.assertIn("EVENT_TRIGGER_LAZY", self.codes(plan))

    def test_generic_parameter_definition_is_rejected(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["parameters"][0]["description"] = "Reusable parameter for applicable events."
        self.assertIn("PARAMETER_DEFINITION_LAZY", self.codes(plan))

    def test_official_event_needs_definition_and_trigger_source_zones(self) -> None:
        plan = copy.deepcopy(self.fixture)
        verification = plan["events"][0]["official_verification"]
        verification.pop("source_section")
        verification.pop("trigger_source_section")
        codes = self.codes(plan)
        self.assertIn("OFFICIAL_SOURCE_SECTION_MISSING", codes)
        self.assertIn("OFFICIAL_TRIGGER_SOURCE_SECTION_MISSING", codes)

    def test_official_source_receipt_must_match_publish_date(self) -> None:
        plan = copy.deepcopy(self.fixture)
        publish_date = date.fromisoformat(plan["document"]["publish_date"])
        checked_at = datetime.combine(publish_date - timedelta(days=1), datetime.min.time(), timezone.utc)
        plan["official_source_check"]["checked_at"] = checked_at.isoformat().replace("+00:00", "Z")
        plan["official_source_check"] = finalize_receipt(plan["official_source_check"])
        self.assertIn("OFFICIAL_SOURCE_RECEIPT_INVALID", self.codes(plan))

        client_source = copy.deepcopy(self.fixture)
        client_source["documentation_sources_checked"].append({
            "source_id": "client_template_example",
            "name": "Client template",
            "url": "client-template.xlsx",
            "source_type": "client_template",
            "checked_for": "Workbook structure and design",
            "checked_date": None,
            "language": "en",
            "content_signature": "",
        })
        self.rebind_resolved_plan(client_source)
        self.assertNotIn("OFFICIAL_SOURCE_RECEIPT_INVALID", self.codes(client_source))

    def test_official_source_receipt_catalog_signature_is_bound(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["official_source_check"]["catalog_signature_sha256"] = "0" * 64
        plan["official_source_check"] = finalize_receipt(plan["official_source_check"])
        self.assertIn("OFFICIAL_SOURCE_RECEIPT_INVALID", self.codes(plan))

    def test_required_ecommerce_parameter_cannot_be_pruned(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["parameter_bindings"] = [
            binding for binding in event["parameter_bindings"]
            if binding["parameter_name"] != "items"
        ]
        self.assertIn("OFFICIAL_REQUIRED_PARAMETER_NOT_SELECTED", self.codes(plan))

    def test_ecommerce_item_identity_cannot_be_pruned(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["parameter_bindings"] = [
            binding for binding in event["parameter_bindings"]
            if binding["parameter_name"] not in {"items[].item_id", "items[].item_name"}
        ]
        self.assertIn("OFFICIAL_ITEM_IDENTITY_NOT_SELECTED", self.codes(plan))

    def test_selected_ecommerce_parameter_must_appear_in_example(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(event for event in plan["events"] if event["event_name"] == "view_promotion")
        event["data_layer"]["push"]["ecommerce"].pop("creative_slot")
        self.assertIn("SELECTED_PARAMETER_NOT_IN_EXAMPLE", self.codes(plan))


if __name__ == "__main__":
    unittest.main()
