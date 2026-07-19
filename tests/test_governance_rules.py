from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from generate_tracking_plan_workbook import build_workbook  # noqa: E402
from official_source_receipt import finalize_receipt, tracking_plan_sha256  # noqa: E402
from validate_tracking_plan import validate_plan_data  # noqa: E402


class GovernanceRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))

    def codes(self, plan: dict) -> set[str]:
        return {issue.code for issue in validate_plan_data(plan)}

    def french_plan(self) -> dict:
        plan = copy.deepcopy(self.fixture)
        plan["language_policy"] = {
            "site_language_scope": "single_language",
            "site_languages": ["fr"],
            "workbook_language": "fr",
            "controlled_value_language": "fr",
            "technical_name_language": "en",
            "controlled_value_format": "lowercase_ascii_snake_case",
            "decision_basis": "Le site et le modèle client utilisent uniquement la langue française.",
        }
        for event in plan["events"]:
            verification = event.get("official_verification", {})
            if verification.get("status") == "verified":
                verification["translation_status"] = "analyst_translation"
        for parameter in plan["parameters"]:
            verification = parameter.get("official_verification", {})
            if verification.get("status") == "verified":
                verification["translation_status"] = "analyst_translation"
        translations = {
            "page_template": ["accueil", "liste_produits", "fiche_produit", "panier", "commande", "page_contenu"],
            "nav_language": ["fr"],
            "nav_environment": ["production", "preproduction", "developpement"],
            "content_type": ["navigation_categorie", "module_editorial", "lien_service"],
            "cta_location": ["entete", "banniere_principale", "contenu", "pied_de_page", "menu"],
            "login_status": ["connecte", "deconnecte"],
            "customer_status": ["nouveau", "existant", "inconnu"],
        }
        for parameter in plan["parameters"]:
            if parameter["parameter_name"] in translations:
                values = translations[parameter["parameter_name"]]
                parameter["value_domain"]["entries"] = [
                    {
                        "raw_label": value,
                        "normalized_value": value,
                        "language": "fr",
                        "source_ref": "",
                        "mapping_method": "normalization_only",
                    }
                    for value in values
                ]
        plan["events"][0]["event_summary"] = "Cet événement indique qu'un utilisateur a consulté une page du site."
        plan["parameters"][0]["description"] = "URL complète de la page consultée par l'utilisateur sur le site."
        receipt = copy.deepcopy(plan["official_source_check"])
        receipt["resolved_plan_sha256"] = tracking_plan_sha256(plan)
        plan["official_source_check"] = finalize_receipt(receipt)
        return plan

    def test_multilingual_plan_requires_english(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["language_policy"].update(
            {
                "site_language_scope": "multilingual",
                "site_languages": ["en", "fr"],
                "workbook_language": "fr",
                "controlled_value_language": "fr",
            }
        )
        self.assertIn("MULTILINGUAL_LANGUAGE_POLICY_INVALID", self.codes(plan))

    def test_french_localized_wording_retains_canonical_official_truth(self) -> None:
        self.assertEqual(validate_plan_data(self.french_plan()), [])

    def test_french_custom_values_cannot_keep_english_semantics(self) -> None:
        plan = self.french_plan()
        parameter = next(item for item in plan["parameters"] if item["parameter_name"] == "login_status")
        for entry in parameter["value_domain"]["entries"]:
            entry["language"] = "en"
            entry["mapping_method"] = "normalization_only"
        self.assertIn("CONTROLLED_VALUE_TRANSLATION_UNDECLARED", self.codes(plan))

        untranslated = self.french_plan()
        untranslated_parameter = next(item for item in untranslated["parameters"] if item["parameter_name"] == "login_status")
        untranslated_parameter["value_domain"]["entries"][0].update({
            "raw_label": "Connecté",
            "normalized_value": "logged_in",
            "language": "fr",
            "mapping_method": "normalization_only",
        })
        self.assertIn("FRENCH_CONTROLLED_VALUE_NOT_TRANSLATED", self.codes(untranslated))

    def test_official_canonical_wording_cannot_drift(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["official_verification"]["canonical_wording"] = "A generic page event."
        self.assertIn("OFFICIAL_CANONICAL_WORDING_MISMATCH", self.codes(plan))

    def test_official_canonical_trigger_wording_cannot_drift(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["official_verification"]["canonical_trigger_wording"] = "When relevant."
        self.assertIn("OFFICIAL_CANONICAL_TRIGGER_MISMATCH", self.codes(plan))

    def test_official_trigger_needs_precise_source_locator(self) -> None:
        plan = copy.deepcopy(self.fixture)
        del plan["events"][0]["official_verification"]["trigger_source_locator"]
        self.assertIn("OFFICIAL_TRIGGER_SOURCE_LOCATOR_MISSING", self.codes(plan))

        unrelated = copy.deepcopy(self.fixture)
        unrelated["events"][1]["official_verification"]["trigger_source_section"] = "Implementation > Unrelated section"
        unrelated["events"][1]["official_verification"]["trigger_source_locator"] = "some text"
        codes = self.codes(unrelated)
        self.assertIn("OFFICIAL_TRIGGER_SOURCE_SECTION_MISMATCH", codes)
        self.assertIn("OFFICIAL_TRIGGER_SOURCE_LOCATOR_MISMATCH", codes)

    def test_observed_exhaustive_values_need_browser_evidence(self) -> None:
        plan = copy.deepcopy(self.fixture)
        parameter = next(item for item in plan["parameters"] if item["parameter_name"] == "page_template")
        parameter["value_domain"].update({
            "mode": "observed_exhaustive",
            "source_refs": [],
            "notes": "All visible page templates were inspected in the browser.",
        })
        self.assertIn("FINITE_VALUE_EVIDENCE_MISSING", self.codes(plan))

    def test_observed_exhaustive_values_must_link_recorded_browser_source(self) -> None:
        plan = copy.deepcopy(self.fixture)
        parameter = next(item for item in plan["parameters"] if item["parameter_name"] == "page_template")
        parameter["value_domain"].update({
            "mode": "observed_exhaustive",
            "source_refs": ["Unlinked analyst note"],
            "notes": "All visible page templates were inspected in the browser.",
        })
        self.assertIn("OBSERVED_VALUE_BROWSER_EVIDENCE_MISSING", self.codes(plan))

        source_ref = "Playwright value discovery run 2026-07-17"
        parameter["value_domain"]["source_refs"] = [source_ref]
        for entry in parameter["value_domain"]["entries"]:
            entry["source_ref"] = source_ref
        plan["website_coverage_map"]["sources_checked"].append(
            {
                "source_type": "playwright_crawl",
                "source_ref": source_ref,
                "used_for": "Exhaust page-template values from rendered routes.",
                "confidence": "high",
            }
        )
        self.assertNotIn("OBSERVED_VALUE_BROWSER_EVIDENCE_MISSING", self.codes(plan))

    def test_dynamic_item_ids_use_rules_not_allowed_value_lists(self) -> None:
        plan = copy.deepcopy(self.fixture)
        parameter = next(item for item in plan["parameters"] if item["parameter_name"] == "items[].item_id")
        parameter["value_domain"]["entries"] = [{
            "raw_label": "sku_123",
            "normalized_value": "sku_123",
            "language": "zxx",
            "source_ref": "",
            "mapping_method": "official_or_technical_value",
        }]
        parameter["value_domain"]["mode"] = "governed_rule"
        self.assertIn("NONFINITE_VALUE_LIST_PRESENT", self.codes(plan))

    def test_whole_site_plan_requires_live_browser_research(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["website_coverage_map"]["site_scope"] = "whole_site"
        self.assertIn("WHOLE_SITE_BROWSER_EXPLORATION_NOT_REQUIRED", self.codes(plan))

    def test_required_browser_research_needs_actual_playwright_attempt(self) -> None:
        plan = copy.deepcopy(self.fixture)
        research = plan["website_coverage_map"]["browser_exploration"]
        research["requirement"] = "required"
        research["playwright_mcp_attempt"] = {"status": "not_recorded", "detail": "Playwright has not been attempted."}
        self.assertIn("PLAYWRIGHT_EXPLORATION_ATTEMPT_MISSING", self.codes(plan))

    def test_non_page_event_must_follow_cmp_readiness(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][1]["data_layer"]["consent_timing"] = "core_context_before_cmp_ready"
        self.assertIn("EVENT_CMP_TIMING_INVALID", self.codes(plan))

    def test_page_context_requires_navigation_and_environment_fields(self) -> None:
        plan = copy.deepcopy(self.fixture)
        del plan["events"][0]["data_layer"]["push"]["page"]["nav_language"]
        self.assertIn("CORE_PAGE_CONTEXT_INCOMPLETE", self.codes(plan))

    def test_french_workbook_localizes_human_labels_only(self) -> None:
        workbook = build_workbook(self.french_plan())
        self.assertEqual(workbook["01 GTM Protocol"]["A3"].value, "Sujet")
        self.assertEqual(workbook["02 Parameter Reference"]["A3"].value, "Nom de la variable")
        self.assertEqual(workbook["03 Event Matrix"]["A5"].value, "Champ / chemin du paramètre")
        self.assertEqual(workbook["02 Parameter Reference"]["A4"].value, "page_location")
        french_protocol = "\n".join(
            str(cell.value)
            for row in workbook["01 GTM Protocol"].iter_rows()
            for cell in row
            if cell.value is not None
        )
        self.assertIn('login_status: "connecte"', french_protocol)
        self.assertIn('customer_status: "existant"', french_protocol)
        self.assertIn("pret_a_porter_femme", french_protocol)
        self.assertIn("Statut du plan : prévu", french_protocol)
        self.assertNotIn('login_status: "logged_in"', french_protocol)

        english_workbook = build_workbook(copy.deepcopy(self.fixture))
        english_protocol = "\n".join(
            str(cell.value)
            for row in english_workbook["01 GTM Protocol"].iter_rows()
            for cell in row
            if cell.value is not None
        )
        self.assertIn('login_status: "logged_in"', english_protocol)
        self.assertIn("women_ready_to_wear", english_protocol)
        self.assertNotIn("pret_a_porter_femme", english_protocol)


if __name__ == "__main__":
    unittest.main()
