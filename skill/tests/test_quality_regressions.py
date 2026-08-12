from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from discover_site_journeys import classify_page_archetype
from discover_site_journeys_playwright import (
    detect_interaction_capabilities,
    measurement_opportunity_hints,
)
from discovery_contract import validate_discovery_report
from tracking_plan_model import datalayer_code
from validate_analysis_context import validate_analysis_context
from validate_tracking_plan import (
    check_plan_parameter_consistency_and_budgets,
    validate_plan,
)


class DiscoveryQualityRegressionTests(unittest.TestCase):
    def analysis_context(self) -> dict:
        return json.loads((ROOT / "references" / "example-analysis-context.json").read_text(encoding="utf-8"))

    def test_contact_page_is_not_misclassified_by_carte_or_global_chrome(self) -> None:
        result = classify_page_archetype(
            "https://example.fr/contact/",
            {
                "title": "Nous contacter",
                "headings": "Contact carte Contact recharge",
                "main": "Choisissez le motif de votre demande.",
                "global_chrome": "Rechercher Nos offres Voir la carte",
            },
        )
        self.assertEqual(result["primary"], "support_or_contact")
        self.assertNotEqual(result["primary"], "cart")
        self.assertNotEqual(result["primary"], "promotion")
        self.assertNotEqual(result["primary"], "search_results")

    def test_global_offer_and_search_controls_do_not_turn_content_into_promotion_or_search(self) -> None:
        result = classify_page_archetype(
            "https://example.fr/qui-sommes-nous/",
            {
                "title": "Qui sommes-nous",
                "headings": "Notre entreprise",
                "main": "Découvrez notre histoire et nos engagements.",
                "global_chrome": "Offres Rechercher",
            },
        )
        self.assertIn(result["primary"], {"unknown", "content_or_other"})
        self.assertNotIn(result["primary"], {"promotion", "search_results"})

    def test_locator_route_and_main_surface_beat_unrelated_global_copy(self) -> None:
        result = classify_page_archetype(
            "https://example.fr/stations-service/",
            {
                "title": "Trouver une station",
                "headings": "Localiser une station proche de vous",
                "main": "Saisissez une ville puis sélectionnez un résultat sur la carte.",
                "global_chrome": "Nos offres et promotions",
            },
        )
        self.assertEqual(result["primary"], "store_locator")

    def test_plural_product_route_distinguishes_detail_from_listing(self) -> None:
        detail = classify_page_archetype("https://example.com/products/example-window")
        listing = classify_page_archetype("https://example.com/products/")
        self.assertEqual(detail["primary"], "product_detail")
        self.assertEqual(listing["primary"], "listing")

    def test_interaction_families_are_detected_once_per_page_not_per_control(self) -> None:
        page = {
            "url": "https://example.fr/contact/",
            "template": "support_or_contact",
            "forms": [{"selector": "#contact-card"}, {"selector": "#contact-topup"}],
            "interactive_controls": [
                {"type": "tab", "label": "Contact carte"},
                {"type": "tab", "label": "Contact recharge"},
                {"type": "tablist", "label": "Type de contact"},
            ],
            "page_surfaces": {
                "title": "Nous contacter",
                "headings": ["Contact carte", "Contact recharge"],
                "main_text": "Choisissez un onglet puis envoyez votre demande.",
                "semantic_counts": {"tab": 2, "tablist": 1, "form": 2},
            },
            "rendered_structure_sha256": "1" * 64,
        }
        capabilities = detect_interaction_capabilities(page)
        families = [item["family"] for item in capabilities]
        self.assertEqual(families.count("tabbed_form"), 1)

        page["interaction_capabilities"] = capabilities
        hints = measurement_opportunity_hints([page])
        tabbed_hints = [item for item in hints if item["hint_key"] == "tabbed_form_outcomes"]
        self.assertEqual(len(tabbed_hints), 1)
        self.assertEqual(tabbed_hints[0]["materiality"], "material")
        self.assertTrue(tabbed_hints[0]["capability_ids"])

    def test_store_locator_selection_becomes_an_explicit_family_decision(self) -> None:
        page = {
            "url": "https://example.fr/stations-service/",
            "template": "store_locator",
            "forms": [],
            "interactive_controls": [],
            "page_surfaces": {
                "title": "Trouver une station",
                "headings": ["Stations proches de vous"],
                "main_text": "Recherchez puis sélectionnez une station sur la carte.",
                "semantic_counts": {"map": 1, "locator_result": 8},
            },
            "rendered_structure_sha256": "2" * 64,
        }
        capabilities = detect_interaction_capabilities(page)
        self.assertIn("locator_selection", {item["family"] for item in capabilities})

    def test_delivery_rejects_unresolved_candidate_discovery_hint(self) -> None:
        context = self.analysis_context()
        context["discovery_reports"][0]["hint_ids"].append("faq_candidate_fixture")
        candidate = copy.deepcopy(context["measurement_opportunities"][0])
        candidate.update(
            {
                "opportunity_id": "faq_candidate_decision",
                "name": "FAQ content usage",
                "material": False,
                "business_question": "Should FAQ use help improve support content?",
                "official_candidate": "select_content",
                "official_fit": "not_applicable",
                "decision": "unresolved",
                "decision_reason": "Pending analyst review against the business need.",
                "event_names": [],
                "discovery_hint_ids": ["faq_candidate_fixture"],
            }
        )
        context["measurement_opportunities"].append(candidate)
        codes = {item.code for item in validate_analysis_context(context, delivery=True)}
        self.assertIn("DISCOVERY_OPPORTUNITY_UNRESOLVED", codes)

    def test_delivery_rejects_seed_placeholder_after_a_decision(self) -> None:
        context = self.analysis_context()
        context["measurement_opportunities"][0]["decision_reason"] = (
            "Pending analyst review against current official GA4 semantics and the business need."
        )
        codes = {item.code for item in validate_analysis_context(context, delivery=True)}
        self.assertIn("OPPORTUNITY_PLACEHOLDER_TEXT", codes)

    def test_not_tested_gap_cannot_be_relabelled_as_externally_blocked(self) -> None:
        context = self.analysis_context()
        context["coverage_gaps"].append(
            {
                "gap_id": "untested_contact_tabs",
                "journey_id": "product_discovery",
                "material": True,
                "evidence_state": "not_tested",
                "resolution": "blocked",
                "description": "The contact tabs were not exercised.",
                "evidence_refs": ["live_site"],
            }
        )
        codes = {item.code for item in validate_analysis_context(context, delivery=True)}
        self.assertIn("UNTESTED_GAP_MISLABELLED_BLOCKED", codes)

    def test_semantically_duplicate_value_domains_are_rejected(self) -> None:
        context = self.analysis_context()
        duplicate = copy.deepcopy(context["value_domains"][0])
        duplicate["domain_id"] = "duplicate_page_templates"
        context["value_domains"].append(duplicate)
        codes = {item.code for item in validate_analysis_context(context, delivery=True)}
        self.assertIn("VALUE_DOMAIN_SEMANTIC_DUPLICATE", codes)

    def test_discovery_1_2_requires_factual_gap_state_without_breaking_1_1(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        report["coverage_gaps"] = [
            {
                "gap_id": "sample_boundary",
                "material": True,
                "description": "A sample boundary remains.",
            }
        ]
        self.assertEqual(validate_discovery_report(report), [])
        report["discovery_version"] = "1.2.0"
        self.assertTrue(any("evidence_state" in error for error in validate_discovery_report(report)))

    def test_defining_official_checkout_choices_cannot_be_silently_omitted(self) -> None:
        plan = json.loads((ROOT / "references" / "example-tracking-plan.json").read_text(encoding="utf-8"))
        event = plan["events"][1]
        catalog = json.loads((ROOT / "references" / "library-ga4-recommended-events.json").read_text(encoding="utf-8-sig"))
        record = next(item for item in catalog if item["event"] == "add_payment_info")
        event["event_name"] = "add_payment_info"
        event["definition"] = record["description"]
        event["data_layer"]["push"]["event"] = "add_payment_info"
        event["official_source"] = {
            "url": "https://developers.google.com/analytics/devguides/collection/ga4/reference/events#add_payment_info",
            "section": "add_payment_info",
            "wording_origin": "exact",
            "official_text": record["description"],
            "checked_date": "2026-08-12",
        }
        codes = {item.code for item in validate_plan(plan)}
        self.assertIn("OFFICIAL_ANALYSIS_ANCHOR_MISSING", codes)

    def test_justified_official_to_custom_parameter_carry_through_is_order_invariant(self) -> None:
        official = {
            "name": "payment_type",
            "scope": "event",
            "type": "string",
            "destination": "ga4_event_parameter",
            "classification": "official",
            "definition": "The chosen method of payment.",
            "value_rule": "Use the normalized selected payment method.",
        }
        custom = {
            **official,
            "classification": "custom",
            "custom_decision": {
                "business_need": "Retain payment method on the purchase outcome.",
                "official_candidate": "payment_type on add_payment_info",
                "why_not_fit": "Purchase does not prescribe payment_type, but the same concept remains useful.",
            },
        }
        for parameters in ((official, custom), (custom, official)):
            issues = []
            check_plan_parameter_consistency_and_budgets(
                {
                    "events": [
                        {"parameters": [parameters[0]]},
                        {"parameters": [parameters[1]]},
                    ]
                },
                issues,
            )
            self.assertNotIn("PARAMETER_CLASSIFICATION_VARIATION", {item.code for item in issues})

    def test_datalayer_renderer_can_emit_an_html_script_without_changing_semantics(self) -> None:
        event = {"data_layer": {"push": {"event": "generate_lead", "event_data": {"form_name": "contact"}}}}
        rendered = datalayer_code(
            event,
            {"code_format": "html_script", "initialize_data_layer": True},
        )
        self.assertTrue(rendered.startswith("<script>\n    window.dataLayer = window.dataLayer || [];"))
        self.assertIn('window.dataLayer.push({', rendered)
        self.assertTrue(rendered.endswith("\n</script>"))


if __name__ == "__main__":
    unittest.main()
