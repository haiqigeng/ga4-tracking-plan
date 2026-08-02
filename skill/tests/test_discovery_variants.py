from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_analysis_context_seed import build_analysis_context_seed
from discover_site_journeys_playwright import (
    build_auto_interaction_recipes,
    discovery_exit_code,
    finite_value_candidates,
    journey_coverage_ledger,
    measurement_opportunity_hints,
)
from validate_analysis_context import validate_analysis_context


def lead_page(url: str) -> dict:
    return {
        "url": url,
        "template": "lead_form",
        "forms": [
            {
                "selector": "#quote",
                "action": url,
                "fields": [
                    {
                        "selector": "input[name=email]",
                        "name": "email",
                        "type": "email",
                    }
                ],
                "submit_controls": [{"selector": "button", "label": "Send request"}],
            }
        ],
        "interactive_controls": [],
        "rendered_structure_sha256": "1" * 64,
    }


class DiscoveryVariantTests(unittest.TestCase):
    def test_partial_discovery_remains_usable_but_blocked_discovery_stops(self) -> None:
        self.assertEqual(discovery_exit_code("completed"), 0)
        self.assertEqual(discovery_exit_code("partial"), 0)
        self.assertEqual(discovery_exit_code("blocked"), 1)

    def test_each_material_funnel_variant_gets_its_own_recipe_and_outcome(self) -> None:
        pages = [
            lead_page("https://example.com/quote/standard"),
            lead_page("https://example.com/landing/quote"),
        ]
        recipes = build_auto_interaction_recipes(pages, limit=None)
        self.assertEqual(len(recipes), 2)
        self.assertEqual(len({recipe["variant_id"] for recipe in recipes}), 2)

        completed = {
            **recipes[0],
            "outcome": "completed",
            "actions": [{"step": 1, "status": "completed"}],
        }
        candidates = [
            {"url": page["url"], "text": "Quote", "source": "fixture"}
            for page in pages
        ]
        ledger = journey_coverage_ledger(
            pages,
            candidates,
            [],
            [],
            "https://example.com/",
            [completed],
        )
        lead = next(item for item in ledger if item["journey_id"] == "lead_generation")
        statuses = {variant["variant_id"]: variant["status"] for variant in lead["variant_coverage"]}
        self.assertEqual(statuses[recipes[0]["variant_id"]], "observed")
        self.assertEqual(statuses[recipes[1]["variant_id"]], "partial")
        self.assertEqual(lead["status"], "partial")

    def test_contextual_hints_are_not_deduplicated_across_journeys(self) -> None:
        pages = [
            {
                "url": "https://example.com/products",
                "template": "listing",
                "buttons": ["Filter"],
                "links": [],
                "interactive_controls": [],
                "rendered_structure_sha256": "1" * 64,
            },
            {
                "url": "https://example.com/request-catalogue",
                "template": "catalogue",
                "buttons": ["Filter catalogue"],
                "links": [],
                "interactive_controls": [],
                "rendered_structure_sha256": "2" * 64,
            },
        ]
        hints = measurement_opportunity_hints(pages)
        filter_hints = [item for item in hints if item["hint_key"] == "filter_and_sort_usage"]
        self.assertEqual(len(filter_hints), 2)
        self.assertEqual(
            {item["journey_id"] for item in filter_hints},
            {"product_listing", "catalogue_request"},
        )
        self.assertTrue(all(item["materiality"] == "candidate" for item in filter_hints))

    def test_finite_values_include_native_and_custom_choice_controls(self) -> None:
        page = {
            "url": "https://example.com/quote/standard",
            "template": "lead_form",
            "forms": [],
            "interactive_controls": [
                {
                    "name": "project_type",
                    "option_values": ["window", "door", "shutter"],
                    "option_labels": ["Window", "Door", "Shutter"],
                },
                {
                    "name": "large_choice",
                    "option_count": 51,
                    "option_values": [f"choice_{index}" for index in range(50)],
                    "option_labels": [f"Choice {index}" for index in range(50)],
                },
            ],
        }
        candidates = finite_value_candidates([page])
        project = next(item for item in candidates if item["source_label"] == "project_type")
        large = next(item for item in candidates if item["source_label"] == "large_choice")
        self.assertTrue(project["complete"])
        self.assertEqual([item["value"] for item in project["values"]], ["door", "shutter", "window"])
        self.assertFalse(large["complete"])
        self.assertEqual(large["observed_value_count"], 51)
        self.assertEqual(len(large["values"]), 50)

    def test_seed_preserves_language_precedence_target_state_and_hint_materiality(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        candidate = copy.deepcopy(report["measurement_opportunity_hints"][0])
        candidate.update(
            {
                "hint_id": "filter_candidate_fixture",
                "hint_key": "filter_and_sort_usage",
                "materiality": "candidate",
            }
        )
        report["measurement_opportunity_hints"].append(candidate)
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "discovery.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            context = build_analysis_context_seed(
                report,
                report_path,
                language="fr",
                language_basis="user",
            )
        self.assertEqual(context["target_state"], "as_is")
        self.assertEqual(context["language_decision"]["language"], "fr")
        self.assertEqual(context["language_decision"]["basis"], "user")
        self.assertIn("language_decision_context", context["language_decision"]["evidence_refs"])
        candidate_opportunity = next(
            item
            for item in context["measurement_opportunities"]
            if item["discovery_hint_ids"] == ["filter_candidate_fixture"]
        )
        self.assertFalse(candidate_opportunity["material"])

    def test_delivery_requires_an_exact_boundary_for_each_partial_material_variant(self) -> None:
        context = json.loads((ROOT / "references" / "example-analysis-context.json").read_text(encoding="utf-8"))
        coverage = context["journey_coverage"][0]
        coverage["status"] = "partial"
        coverage["variant_coverage"][0]["status"] = "partial"
        context["coverage_gaps"].append(
            {
                "gap_id": "generic_product_boundary",
                "journey_id": coverage["journey_id"],
                "material": True,
                "resolution": "confirmed_elsewhere",
                "description": "A journey-level boundary that does not identify the incomplete variant.",
                "evidence_refs": ["live_site"],
            }
        )
        codes = {item.code for item in validate_analysis_context(context, delivery=True)}
        self.assertIn("MATERIAL_VARIANT_BOUNDARY_MISSING", codes)

    def test_delivery_requires_a_material_decision_for_each_material_variant(self) -> None:
        context = json.loads((ROOT / "references" / "example-analysis-context.json").read_text(encoding="utf-8"))
        context["measurement_opportunities"][0].pop("variant_id")
        codes = {item.code for item in validate_analysis_context(context, delivery=True)}
        self.assertIn("MATERIAL_VARIANT_OPPORTUNITY_MISSING", codes)


if __name__ == "__main__":
    unittest.main()
