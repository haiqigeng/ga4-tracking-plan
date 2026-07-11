from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from validate_tracking_plan import validate_plan_data  # noqa: E402


class DeliveryRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8")
        )

    def codes(self, plan: dict) -> set[str]:
        return {issue.code for issue in validate_plan_data(plan)}

    def test_manual_event_needs_developer_example(self) -> None:
        plan = copy.deepcopy(self.fixture)
        del plan["events"][3]["data_layer"]
        self.assertIn("DATALAYER_EXAMPLE_MISSING", self.codes(plan))

    def test_ecommerce_uses_official_gtm_wrapper(self) -> None:
        plan = copy.deepcopy(self.fixture)
        push = plan["events"][1]["data_layer"]["push"]
        push.update(push.pop("ecommerce"))
        self.assertIn("GTM_ECOMMERCE_WRAPPER_MISSING", self.codes(plan))

    def test_controlled_values_use_english_ascii(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["parameters"][3]["allowed_values"] = ["prêt_a_porter"]
        self.assertIn("CONTROLLED_VALUE_NOT_ENGLISH_ASCII", self.codes(plan))

    def test_whole_site_navigation_needs_surface_model(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        self.assertIn("NAVIGATION_SURFACE_EVENTS_MISSING", self.codes(plan))

    def test_account_scope_needs_authenticated_discovery_decision(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["measurement_brief"][0]["page_type"] = "login"
        del plan["website_coverage_map"]["authenticated_journey"]
        self.assertIn("AUTHENTICATED_DISCOVERY_DECISION_MISSING", self.codes(plan))

    def test_applicable_account_journey_cannot_be_left_unattempted(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["measurement_brief"][0]["page_type"] = "login"
        plan["website_coverage_map"]["authenticated_journey"]["discovery_status"] = "not_attempted"
        self.assertIn("AUTHENTICATED_DISCOVERY_NOT_ATTEMPTED", self.codes(plan))

    def test_variant_availability_is_not_default_list_data(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][1]["parameters"].append("items[].availability_status")
        self.assertIn("AVAILABILITY_STATUS_SCOPE_INVALID", self.codes(plan))

    def test_checkout_needs_payment_failure_branch(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["event_name"] = "add_payment_info"
        plan["events"][1]["event_name"] = "purchase"
        self.assertIn("PAYMENT_FAILURE_BRANCH_MISSING", self.codes(plan))

    def test_multiple_lead_outcomes_need_a_deliberate_event_model(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = copy.deepcopy(plan["events"][3])
        event["event_id"] = "EVT-GENERATE-LEAD"
        event["event_name"] = "generate_lead"
        event["classification"] = "recommended"
        event["trigger"] = "Newsletter, catalogue, or contact submission succeeds."
        event["page_or_component"] = "Newsletter, catalogue, and contact forms"
        event["data_layer"]["event_key"] = "generate_lead"
        event["data_layer"]["push"]["event"] = "generate_lead"
        event["ga4_payload"]["event_name"] = "generate_lead"
        plan["events"].append(event)
        self.assertIn("LEAD_MODEL_NOT_APPLICABLE_CONFLICT", self.codes(plan))

    def test_consolidated_lead_model_maps_outcomes_to_generate_lead(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["measurement_strategy"]["lead_event_model"] = {
            "mode": "consolidated",
            "rationale": "Comparable lead outcomes share one GA4 event and an outcome parameter.",
            "outcome_mappings": [
                {"outcome": "newsletter subscription", "event_name": "newsletter_subscribe", "business_owner": "CRM", "evidence_status": "confirmed"}
            ],
        }
        self.assertIn("LEAD_MODEL_CONSOLIDATED_INVALID", self.codes(plan))

    def test_customer_space_needs_authenticated_outcomes(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["measurement_brief"][0]["scope"] = "Authenticated customer space, account orders and returns"
        plan["website_coverage_map"]["authenticated_journey"]["discovery_status"] = "authenticated_observed"
        self.assertIn("AUTHENTICATED_OUTCOMES_MISSING", self.codes(plan))

    def test_blocked_customer_space_does_not_require_invented_events(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["measurement_brief"][0]["scope"] = "Authenticated customer space, account orders and returns"
        plan["website_coverage_map"]["authenticated_journey"] = {
            "applicable": True,
            "discovery_status": "attempted_blocked",
            "attempted_actions": ["Attempted synthetic account creation"],
            "evidence": ["Signup required a real customer identifier"],
            "gap_reason": "The flow required a real customer identifier that was unavailable.",
        }
        self.assertNotIn("AUTHENTICATED_OUTCOMES_MISSING", self.codes(plan))

    def test_user_id_must_not_be_an_event_parameter(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][3]["parameters"].append("user_id")
        plan["events"][3]["ga4_payload"]["parameters"]["user_id"] = "customer_123"
        self.assertIn("USER_ID_EVENT_PARAMETER_INVALID", self.codes(plan))

    def test_user_property_reuses_parameter_reference_values(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["user_context"]["user_properties"][0]["allowed_values"] = ["signed_in", "signed_out"]
        self.assertIn("USER_PROPERTY_VALUES_MISMATCH", self.codes(plan))

    def test_governed_advertising_user_data_remains_outside_ga4(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["user_context"]["advertising_user_data"] = {
            "status": "planned",
            "data_layer_object": "user_data",
            "destination": "google_ads_only",
            "fields": ["email", "phone_number"],
            "consent_requirements": ["ad_user_data"],
            "handling_rule": "Normalize and hash fields for Google Ads only; never map these identifiers to GA4.",
        }
        self.assertNotIn("AD_USER_DATA_GOVERNANCE_WEAK", self.codes(plan))

    def test_advertising_user_data_needs_consent_and_non_ga4_rule(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["user_context"]["advertising_user_data"] = {
            "status": "planned",
            "data_layer_object": "user_data",
            "destination": "google_ads_only",
            "fields": ["email"],
            "consent_requirements": [],
            "handling_rule": "Send the email value to advertising tags.",
        }
        self.assertIn("AD_USER_DATA_GOVERNANCE_WEAK", self.codes(plan))

    def test_order_cancellation_is_not_covered_by_refund_alone(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["measurement_brief"][0]["scope"] = "Post-purchase order cancellation"
        self.assertIn("ORDER_CANCELLATION_EVENT_MISSING", self.codes(plan))


if __name__ == "__main__":
    unittest.main()
