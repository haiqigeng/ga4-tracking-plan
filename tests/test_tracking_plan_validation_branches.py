from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from tracking_plan_validation_common import check_duplicates  # noqa: E402
from tracking_plan_validation_model import Issue  # noqa: E402
from tracking_plan_validation_screenshot_capture import check_screenshot_row  # noqa: E402
from validate_tracking_plan import (  # noqa: E402
    main,
    render_text,
    validate_plan_data,
    values_at_keys,
)


class TrackingPlanValidationBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8")
        )

    def codes(self, plan: dict) -> set[str]:
        return {issue.code for issue in validate_plan_data(plan)}

    def test_recursive_keys_and_duplicate_ids(self) -> None:
        found = list(values_at_keys({"a": [{"event": "one"}], "event": "two"}, {"event"}))
        self.assertEqual(found, [("$.a[0].event", "one"), ("$.event", "two")])
        issues: list[Issue] = []
        check_duplicates(["one", "one", ""], "event_id", "$.events", issues)
        self.assertEqual([issue.code for issue in issues], ["DUPLICATE_ID"])

    def test_client_template_contract_requires_policy_artifact_diff_and_preservation(self) -> None:
        plan = copy.deepcopy(self.fixture)
        context = plan["execution_context"]
        context["execution_mode"] = "client_template_adaptation"
        context["input_artifact_inventory"] = []
        context["template_policy"].update(
            {"mode": "default_skill_template", "template_diff_required": True, "preservation_requirements": []}
        )
        context.pop("template_diff_summary", None)
        codes = self.codes(plan)
        self.assertTrue(
            {
                "CLIENT_TEMPLATE_POLICY_MISSING",
                "CLIENT_TEMPLATE_ARTIFACT_MISSING",
                "TEMPLATE_DIFF_SUMMARY_MISSING",
            }
            <= codes
        )

        context["template_policy"]["mode"] = "strict_client_template"
        self.assertIn("TEMPLATE_PRESERVATION_REQUIREMENTS_MISSING", self.codes(plan))

    def test_greenfield_template_policy_warning_is_visible(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["execution_context"]["template_policy"]["mode"] = "not_applicable"
        self.assertIn("GREENFIELD_TEMPLATE_POLICY", self.codes(plan))

    def test_measurement_alignment_and_strategy_fail_closed(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["journey_id"] = "unknown_journey"
        plan["measurement_brief"].append(copy.deepcopy(plan["measurement_brief"][0]))
        plan["measurement_brief"][-1].update({"journey_id": "empty_journey", "success_signals": []})
        plan["measurement_strategy"]["page_roles"][0]["journey_id"] = "strategy_unknown"
        plan["measurement_strategy"]["selected_event_families"][0]["reason"] = "Too short"
        plan["events"][1]["business_event_family"] = "missing_family"
        plan["measurement_strategy"]["custom_event_acceptance"] = []
        codes = self.codes(plan)
        self.assertTrue(
            {
                "EVENT_JOURNEY_UNKNOWN",
                "JOURNEY_HAS_NO_EVENTS",
                "STRATEGY_JOURNEY_UNKNOWN",
                "STRATEGY_EVENT_FAMILY_REASON_WEAK",
                "EVENT_FAMILY_UNKNOWN",
                "CUSTOM_EVENT_ACCEPTANCE_MISSING",
            }
            <= codes
        )

    def test_custom_event_acceptance_needs_reason_and_alternatives(self) -> None:
        plan = copy.deepcopy(self.fixture)
        acceptance = plan["measurement_strategy"]["custom_event_acceptance"][0]
        acceptance.update({"business_reason": "weak", "official_alternatives_considered": []})
        self.assertIn("CUSTOM_EVENT_ACCEPTANCE_WEAK", self.codes(plan))

    def test_coverage_map_requires_evidence_and_consistent_decisions(self) -> None:
        plan = copy.deepcopy(self.fixture)
        coverage = plan["website_coverage_map"]
        item = coverage["journeys_covered"][0]
        item.update(
            {
                "journey_id": "unknown_coverage",
                "coverage_status": "blocked",
                "representative_urls": [],
                "page_templates": [],
                "key_interactions": [],
                "evidence": [],
            }
        )
        coverage["journeys_discovered"][0].update({"journey_id": "unknown_discovered", "decision": "include_in_plan"})
        coverage["journeys_discovered"].append(
            {
                "journey_id": "needs_more",
                "journey_name": "Needs more",
                "source_refs": ["navigation"],
                "representative_urls": ["https://example.com/more"],
                "page_templates": ["page"],
                "key_interactions": ["continue"],
                "decision": "needs_discovery",
                "decision_reason": "More evidence is needed before including this journey.",
            }
        )
        coverage["coverage_gaps"] = []
        codes = self.codes(plan)
        self.assertTrue(
            {
                "COVERAGE_JOURNEY_UNKNOWN",
                "COVERAGE_INCLUDED_BUT_NOT_COVERED",
                "COVERAGE_INCLUDED_EVIDENCE_MISSING",
                "DISCOVERED_JOURNEY_NOT_IN_MEASUREMENT_BRIEF",
                "DISCOVERED_JOURNEY_NOT_COVERED",
                "DISCOVERED_JOURNEY_GAP_MISSING",
                "MEASUREMENT_JOURNEY_NOT_IN_COVERAGE_MAP",
            }
            <= codes
        )

    def test_whole_site_scope_requires_structural_sources_and_discovered_journeys(self) -> None:
        plan = copy.deepcopy(self.fixture)
        coverage = plan["website_coverage_map"]
        coverage.update({"site_scope": "whole_site", "sources_checked": [], "journeys_discovered": []})
        codes = self.codes(plan)
        self.assertIn("WHOLE_SITE_COVERAGE_SOURCE_MISSING", codes)
        self.assertIn("WHOLE_SITE_DISCOVERED_JOURNEYS_MISSING", codes)

    def test_not_tracked_decisions_need_real_rationale(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["not_tracked"] = []
        self.assertIn("NOT_TRACKED_EMPTY", self.codes(plan))
        plan["not_tracked"] = [{"interaction": "decorative hover", "reason": "not needed"}]
        self.assertIn("NOT_TRACKED_REASON_WEAK", self.codes(plan))

    def test_screenshot_row_and_reuse_rules_are_explicit(self) -> None:
        issues: list[Issue] = []
        row = {
            "event_ids": ["UNKNOWN"],
            "status": "shared_evidence",
            "file_name": "",
            "shared_reason": "weak",
        }
        check_screenshot_row(row, 0, {"KNOWN"}, Counter(), defaultdict(list), issues)
        self.assertTrue(
            {"SCREENSHOT_EVENT_UNKNOWN", "SCREENSHOT_FILE_MISSING", "SCREENSHOT_SHARED_WITH_ONE_EVENT", "SCREENSHOT_SHARED_REASON_WEAK"}
            <= {issue.code for issue in issues}
        )

        plan = copy.deepcopy(self.fixture)
        first = plan["screenshot_evidence"][0]
        second = plan["screenshot_evidence"][1]
        first.update({"status": "captured", "file_name": "same.png"})
        second.update({"status": "captured", "file_name": "same.png", "annotation": {"x1": 1, "y1": 1, "x2": 10, "y2": 10}})
        self.assertIn("SCREENSHOT_REUSE_NOT_EXPLICIT", self.codes(plan))

    def test_screenshot_modes_reject_finite_and_not_requested_mismatches(self) -> None:
        plan = copy.deepcopy(self.fixture)
        account = next(event for event in plan["events"] if event["event_name"] == "account_access_intent")
        account.update({"event_name": "login", "classification": "recommended"})
        account["screenshot_coverage"]["mode"] = "representative"
        self.assertIn("FINITE_SCREENSHOT_MODE_INVALID", self.codes(plan))

        plan = copy.deepcopy(self.fixture)
        plan["screenshot_capture"] = {
            "requirement": "not_requested",
            "playwright_mcp_attempt": {"status": "not_required", "detail": "Screenshots were explicitly excluded."},
            "outcome": "not_requested",
            "delivery_notice": "Screenshots were explicitly excluded from this delivery.",
        }
        self.assertIn("SCREENSHOT_COVERAGE_NOT_REQUESTED", self.codes(plan))

    def test_official_source_and_parameter_governance_checks(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["documentation_sources_checked"] = []
        parameter = plan["parameters"][0]
        parameter.update(
            {
                "parameter_name": "session_id",
                "classification": "custom_event_parameter",
                "reporting_purpose": "reporting",
                "value_rules": "text",
                "pii_risk": "high",
                "cardinality_risk": "high",
                "register_custom_definition": True,
            }
        )
        codes = self.codes(plan)
        self.assertTrue(
            {
                "GA4_OFFICIAL_SOURCE_MISSING",
                "GA4_RESERVED_PARAMETER_NAME",
                "HIGH_PII_RISK",
                "HIGH_CARDINALITY_CUSTOM_DIMENSION",
                "PARAMETER_REPORTING_PURPOSE_WEAK",
                "CUSTOM_PARAMETER_VALUE_RULES_WEAK",
            }
            <= codes
        )

    def test_item_parameter_classification_and_scope_are_checked(self) -> None:
        plan = copy.deepcopy(self.fixture)
        official = next(item for item in plan["parameters"] if item["parameter_name"] == "items[].item_id")
        official["classification"] = "custom_item_parameter"
        custom = copy.deepcopy(official)
        custom.update(
            {
                "parameter_name": "items[].stock_status",
                "classification": "ga4_ecommerce_item_parameter",
                "scope": "event",
                "official_verification": {
                    "status": "not_applicable",
                    "source_url": "https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce",
                    "checked_date": "2026-06-29",
                    "scope_note": "Custom item parameter is not official.",
                },
            }
        )
        plan["parameters"].append(custom)
        codes = self.codes(plan)
        self.assertIn("OFFICIAL_ITEM_PARAMETER_MISCLASSIFIED", codes)
        self.assertIn("CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", codes)
        self.assertIn("CUSTOM_ITEM_PARAMETER_SCOPE", codes)

    def test_rendering_and_cli_entrypoint(self) -> None:
        issue = Issue("error", "EXAMPLE", "$.field", "Example message")
        self.assertIn("ERROR EXAMPLE $.field", render_text([issue]))
        self.assertIn("passed", render_text([]))
        with tempfile.TemporaryDirectory() as raw:
            plan_path = Path(raw) / "plan.json"
            plan_path.write_text(json.dumps(self.fixture), encoding="utf-8")
            output = io.StringIO()
            with patch.object(sys, "argv", ["validate_tracking_plan.py", str(plan_path), "--format", "json"]):
                with redirect_stdout(output):
                    self.assertEqual(main(), 0)
            self.assertEqual(json.loads(output.getvalue()), [])


if __name__ == "__main__":
    unittest.main()
