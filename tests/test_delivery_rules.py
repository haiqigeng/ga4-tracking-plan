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

    @staticmethod
    def add_binding(event: dict, parameter_name: str) -> None:
        event["parameter_bindings"].append(
            {
                "parameter_name": parameter_name,
                "requirement": "optional",
                "condition": "",
                "inclusion_reason": "Supports the scoped attribution or diagnostic analysis for this event.",
                "availability": "to_confirm",
                "data_owner": "Web development team",
                "official_source_id": str(event.get("official_verification", {}).get("source_id", "")),
                "official_source_locator": parameter_name,
            }
        )

    def test_manual_event_needs_developer_example(self) -> None:
        plan = copy.deepcopy(self.fixture)
        del plan["events"][3]["data_layer"]
        self.assertIn("DATALAYER_EXAMPLE_MISSING", self.codes(plan))

    def test_ecommerce_uses_official_gtm_wrapper(self) -> None:
        plan = copy.deepcopy(self.fixture)
        push = plan["events"][1]["data_layer"]["push"]
        push.update(push.pop("ecommerce"))
        self.assertIn("GTM_ECOMMERCE_WRAPPER_MISSING", self.codes(plan))

    def test_non_ecommerce_parameters_use_event_data_wrapper(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "search")
        push = event["data_layer"]["push"]
        push["search_term"] = push["event_data"].pop("search_term")
        self.assertIn("DATALAYER_ROOT_FIELD_UNWRAPPED", self.codes(plan))

    def test_wrapper_key_matches_final_ga4_parameter(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "search")
        push = event["data_layer"]["push"]
        push["event_data"]["query"] = push["event_data"].pop("search_term")
        self.assertIn("DATALAYER_PARAMETER_MAPPING_MISSING", self.codes(plan))

    def test_page_context_uses_page_wrapper(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "page_view")
        push = event["data_layer"]["push"]
        push["page_data"] = push.pop("page")
        self.assertIn("DATALAYER_ROOT_FIELD_UNWRAPPED", self.codes(plan))

        native_plan = copy.deepcopy(self.fixture)
        native_event = next(item for item in native_plan["events"] if item["event_name"] == "page_view")
        native_event["data_layer"]["push"]["event"] = "page_view"
        self.assertIn("NATIVE_EVENT_MANUAL_PUSH", self.codes(native_plan))

        manual_plan = copy.deepcopy(self.fixture)
        manual_event = next(item for item in manual_plan["events"] if item["event_name"] == "page_view")
        manual_event["collection_strategy"]["collection_source"] = "manual_gtm"
        manual_event["data_layer"]["push"]["event"] = "page_view"
        self.assertNotIn("NATIVE_EVENT_MANUAL_PUSH", self.codes(manual_plan))
        self.assertNotIn("DATALAYER_TRIGGER_MISMATCH", self.codes(manual_plan))

    def test_connected_user_state_uses_user_wrapper(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["user_context"]["data_layer_object"] = "user_context"
        self.assertIn("USER_CONTEXT_OBJECT_INVALID", self.codes(plan))

    def test_controlled_values_use_selected_language_ascii_snake_case(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["parameters"][3]["value_domain"]["entries"][0]["normalized_value"] = "prêt_a_porter"
        self.assertIn("CONTROLLED_VALUE_FORMAT_INVALID", self.codes(plan))

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
        self.add_binding(plan["events"][1], "items[].availability_status")
        self.assertIn("AVAILABILITY_STATUS_SCOPE_INVALID", self.codes(plan))

    def test_checkout_needs_payment_failure_branch(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["event_name"] = "add_payment_info"
        plan["events"][1]["event_name"] = "purchase"
        self.assertIn("PAYMENT_FAILURE_BRANCH_MISSING", self.codes(plan))

    def test_ecommerce_list_values_may_use_both_scopes_with_google_precedence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "view_promotion")
        self.add_binding(event, "items[].promotion_id")
        event["data_layer"]["push"]["ecommerce"]["items"][0]["promotion_id"] = "%promotion_id%"
        self.assertNotIn("ECOMMERCE_DUPLICATE_SCOPE_PRECEDENCE", self.codes(plan))

    def test_official_name_used_outside_its_event_needs_binding_classification(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "view_promotion")
        self.add_binding(event, "search_term")
        self.assertIn("EVENT_PARAMETER_CLASSIFICATION_AMBIGUOUS", self.codes(plan))

        binding = next(item for item in event["parameter_bindings"] if item["parameter_name"] == "search_term")
        binding["classification"] = "custom_event_parameter"
        self.assertIn("EVENT_PARAMETER_OFFICIAL_GAP_MISSING", self.codes(plan))

        binding["official_gap"] = "The view_promotion table was reviewed; none of its official fields represents the originating search query needed for promotion-context analysis."
        self.assertNotIn("EVENT_PARAMETER_CLASSIFICATION_AMBIGUOUS", self.codes(plan))
        self.assertNotIn("EVENT_PARAMETER_OFFICIAL_GAP_MISSING", self.codes(plan))

    def test_purchase_propagated_context_needs_source_and_persistence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "view_promotion")
        event["event_name"] = "purchase"
        self.add_binding(event, "payment_type")
        binding = next(item for item in event["parameter_bindings"] if item["parameter_name"] == "payment_type")
        binding["classification"] = "custom_event_parameter"
        codes = self.codes(plan)
        self.assertIn("EVENT_PARAMETER_OFFICIAL_GAP_MISSING", codes)
        self.assertIn("PROPAGATED_PARAMETER_SOURCE_MISSING", codes)
        self.assertIn("PROPAGATED_PARAMETER_PERSISTENCE_MISSING", codes)

        binding["official_gap"] = "The purchase event table was reviewed; it has no official payment method field, while confirmed-order analysis needs the method selected during checkout."
        binding["source_path"] = "checkout.payment_type"
        binding["persistence_rule"] = "Capture after accepted payment selection, persist on the order, omit if unknown, and clear after order completion."
        codes = self.codes(plan)
        self.assertNotIn("EVENT_PARAMETER_OFFICIAL_GAP_MISSING", codes)
        self.assertNotIn("PROPAGATED_PARAMETER_SOURCE_MISSING", codes)
        self.assertNotIn("PROPAGATED_PARAMETER_PERSISTENCE_MISSING", codes)

    def test_custom_parameter_needs_an_official_gap_assessment(self) -> None:
        plan = copy.deepcopy(self.fixture)
        parameter = next(item for item in plan["parameters"] if item["parameter_name"] == "page_template")
        parameter.pop("official_gap")
        self.assertIn("CUSTOM_PARAMETER_OFFICIAL_GAP_MISSING", self.codes(plan))

    def test_downstream_list_attribution_is_not_approved_by_prose_heuristics(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "view_promotion")
        event["event_name"] = "add_to_cart"
        event["data_layer"]["event_key"] = "add_to_cart"
        event["data_layer"]["push"]["event"] = "add_to_cart"
        self.add_binding(event, "items[].item_list_id")
        event["data_layer"]["push"]["ecommerce"]["items"][0]["item_list_id"] = "homepage_recommendations"
        self.assertNotIn("ECOMMERCE_DOWNSTREAM_LIST_ATTRIBUTION_UNJUSTIFIED", self.codes(plan))

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

    def test_blocked_customer_space_still_requires_recommended_outcome_coverage(self) -> None:
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
        self.assertIn("AUTHENTICATED_OUTCOMES_MISSING", self.codes(plan))

    def test_blocked_authentication_allows_official_recommendation(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["authenticated_journey"] = {
            "applicable": True,
            "discovery_status": "attempted_blocked",
            "attempted_actions": ["Attempted synthetic login"],
            "evidence": ["Authentication could not be completed"],
            "gap_reason": "The account required a real customer identifier that was unavailable.",
        }
        event = next(item for item in plan["events"] if item["event_name"] == "search")
        event["access_context"] = "authenticated_area"
        event["trigger"] = "Fire once after the authenticated search results are successfully confirmed by the application."
        event["data_dependencies"].append("Application confirmation that authenticated search results loaded successfully")
        event["evidence_basis"] = {
            "status": "recommended",
            "source_refs": ["Official GA4 recommended search event", "Governed customer-space scenario"],
            "confidence": "medium",
        }
        codes = self.codes(plan)
        self.assertNotIn("UNVERIFIED_AUTHENTICATED_EVENT", codes)
        self.assertNotIn("AUTHENTICATED_EVENT_EVIDENCE_WEAK", codes)

    def test_blocked_authentication_allows_accepted_custom_recommendation(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["authenticated_journey"] = {
            "applicable": True,
            "discovery_status": "attempted_blocked",
            "attempted_actions": ["Attempted synthetic login"],
            "evidence": ["Authentication could not be completed"],
            "gap_reason": "The account required a real customer identifier that was unavailable.",
        }
        event = next(item for item in plan["events"] if item["event_name"] == "account_access_intent")
        event["event_name"] = "view_order_history"
        event["access_context"] = "authenticated_area"
        event["trigger"] = "Fire once after the backend confirms that the authenticated order-history view loaded successfully."
        event["data_layer"]["event_key"] = "view_order_history"
        event["data_layer"]["push"]["event"] = "view_order_history"
        event["evidence_basis"] = {
            "status": "recommended",
            "source_refs": ["Governed retail customer-space scenario"],
            "confidence": "low",
        }
        plan["measurement_strategy"]["custom_event_acceptance"][0]["event_name"] = "view_order_history"
        codes = self.codes(plan)
        self.assertNotIn("UNVERIFIED_AUTHENTICATED_EVENT", codes)
        self.assertNotIn("AUTHENTICATED_EVENT_EVIDENCE_WEAK", codes)

    def test_unobserved_recommendation_cannot_claim_high_confidence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["authenticated_journey"]["discovery_status"] = "attempted_blocked"
        event = next(item for item in plan["events"] if item["event_name"] == "search")
        event["access_context"] = "authenticated_area"
        event["trigger"] = "Fire after the backend confirms successful search results."
        event["evidence_basis"] = {
            "status": "recommended",
            "source_refs": ["Official GA4 recommended search event"],
            "confidence": "high",
        }
        self.assertIn("UNOBSERVED_RECOMMENDATION_CONFIDENCE_HIGH", self.codes(plan))

    def test_generic_event_behind_login_cannot_be_inferred(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["website_coverage_map"]["authenticated_journey"] = {
            "applicable": True,
            "discovery_status": "attempted_blocked",
            "attempted_actions": ["Attempted synthetic login"],
            "evidence": ["Authentication could not be completed"],
            "gap_reason": "The account required a real customer identifier that was unavailable.",
        }
        event = plan["events"][0]
        event["access_context"] = "authenticated_area"
        event["page_type"] = "customer_space_dashboard"
        event["page_or_component"] = "Authenticated customer space dashboard"
        self.assertIn("UNVERIFIED_AUTHENTICATED_EVENT", self.codes(plan))
        self.assertIn("AUTHENTICATED_EVENT_EVIDENCE_WEAK", self.codes(plan))

    def test_authenticated_generic_event_needs_real_evidence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["website_coverage_map"]["authenticated_journey"] = {
            "applicable": True,
            "discovery_status": "authenticated_observed",
            "attempted_actions": ["Created a synthetic account", "Completed login", "Opened the customer dashboard"],
            "evidence": ["Rendered customer dashboard and order navigation observed after login"],
            "gap_reason": "",
        }
        event = plan["events"][0]
        event["access_context"] = "authenticated_area"
        event["page_type"] = "customer_space_dashboard"
        event["page_or_component"] = "Authenticated customer space dashboard"
        event["evidence_basis"] = {
            "status": "synthetic_observation",
            "source_refs": ["Synthetic authenticated browser journey"],
            "confidence": "high",
        }
        codes = self.codes(plan)
        self.assertNotIn("UNVERIFIED_AUTHENTICATED_EVENT", codes)
        self.assertNotIn("AUTHENTICATED_EVENT_EVIDENCE_WEAK", codes)

    def test_french_customer_space_cannot_be_marked_public(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["page_or_component"] = "Espace client mes commandes"
        plan["events"][0]["page_url_pattern"] = "https://example.com/mon-compte/mes-commandes"
        self.assertIn("AUTHENTICATED_CONTEXT_UNDERSTATED", self.codes(plan))

    def test_user_id_must_not_be_an_event_parameter(self) -> None:
        plan = copy.deepcopy(self.fixture)
        self.add_binding(plan["events"][3], "user_id")
        plan["events"][3]["data_layer"]["push"]["event_data"]["user_id"] = "customer_123"
        self.assertIn("USER_ID_EVENT_PARAMETER_INVALID", self.codes(plan))

    def test_user_property_does_not_duplicate_parameter_reference_values(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["user_context"]["user_properties"][0]["allowed_values"] = ["signed_in", "signed_out"]
        self.assertIn("SCHEMA_VALIDATION", self.codes(plan))

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

    def test_scope_prose_does_not_infer_an_order_cancellation_event(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["measurement_brief"][0]["scope"] = "Post-purchase order cancellation"
        self.assertNotIn("ORDER_CANCELLATION_EVENT_MISSING", self.codes(plan))

    def test_whole_site_retail_needs_explicit_funnel_and_service_decisions(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        self.assertIn("WHOLE_SITE_ECOMMERCE_EVENT_DECISION_MISSING", self.codes(plan))

    def test_blocked_browser_access_is_not_an_ecommerce_exclusion_reason(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        plan["not_tracked"].append(
            {
                "interaction": "purchase",
                "reason": "The purchase confirmation was not observed because checkout access was blocked by login.",
            }
        )
        self.assertIn("ECOMMERCE_EVENT_EXCLUSION_UNCONFIRMED", self.codes(plan))


if __name__ == "__main__":
    unittest.main()
