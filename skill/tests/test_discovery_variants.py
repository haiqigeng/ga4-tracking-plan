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

from build_analysis_context_seed import (
    build_analysis_context_seed,
    build_analysis_context_seed_from_reports,
)
from contract_utils import sha256_file
from discover_site_journeys_playwright import (
    build_auto_interaction_recipes,
    discovery_exit_code,
    finite_value_candidates,
    interaction_coverage_gaps,
    journey_coverage_ledger,
    measurement_opportunity_hints,
)
from discovery_contract import validate_discovery_bindings
from discovery_quality import merge_discovery_reports
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
        self.assertEqual(statuses[recipes[1]["variant_id"]], "not_tested")
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
        self.assertEqual(project["capture_status"], "complete")
        self.assertEqual(large["capture_status"], "over_50")
        self.assertEqual(large["observed_value_count"], 51)
        self.assertEqual(len(large["values"]), 50)

    def test_finite_values_do_not_claim_completeness_when_instances_disagree(self) -> None:
        pages = [
            {
                "url": "https://example.com/products/a",
                "template": "product_detail",
                "forms": [],
                "interactive_controls": [
                    {
                        "name": "item_color",
                        "option_count": 2,
                        "option_values": ["red", "blue"],
                        "option_labels": ["Red", "Blue"],
                    }
                ],
            },
            {
                "url": "https://example.com/products/b",
                "template": "product_detail",
                "forms": [],
                "interactive_controls": [
                    {
                        "name": "item_color",
                        "option_count": 2,
                        "option_values": ["red"],
                        "option_labels": ["Red"],
                    }
                ],
            },
        ]
        candidate = finite_value_candidates(pages)[0]
        self.assertEqual(candidate["capture_status"], "incomplete")
        self.assertFalse(candidate["complete"])

    def test_finite_value_union_above_fifty_retains_a_schema_safe_sample(self) -> None:
        pages = [
            {
                "url": f"https://example.com/products/{page_index}",
                "template": "product_detail",
                "forms": [],
                "interactive_controls": [
                    {
                        "name": "item_color",
                        "option_count": 30,
                        "option_values": [
                            f"color_{page_index}_{value_index}"
                            for value_index in range(30)
                        ],
                        "option_labels": [
                            f"Color {page_index} {value_index}"
                            for value_index in range(30)
                        ],
                    }
                ],
            }
            for page_index in range(2)
        ]
        candidate = finite_value_candidates(pages)[0]
        self.assertEqual(candidate["capture_status"], "over_50")
        self.assertEqual(candidate["observed_value_count"], 60)
        self.assertEqual(candidate["captured_value_count"], 50)
        self.assertEqual(len(candidate["values"]), 50)

    def test_all_relevant_forms_in_one_variant_receive_distinct_recipes(self) -> None:
        page = lead_page("https://example.com/contact")
        page["template"] = "support_or_contact"
        page["forms"] = [
            {
                "selector": "#contact-card",
                "visible": True,
                "inside_main": True,
                "name": "contact_card",
                "fields": [{"selector": "#message-card", "name": "message", "type": "text"}],
                "submit_controls": [{"selector": "#send-card", "label": "Send contact card request"}],
            },
            {
                "selector": "#contact-topup",
                "visible": False,
                "inside_main": True,
                "name": "contact_topup",
                "fields": [{"selector": "#message-topup", "name": "message", "type": "text"}],
                "submit_controls": [{"selector": "#send-topup", "label": "Send contact topup request"}],
            },
            {
                "selector": "#contact-help",
                "visible": False,
                "inside_main": True,
                "name": "contact_help",
                "fields": [{"selector": "#message-help", "name": "message", "type": "text"}],
                "submit_controls": [{"selector": "#send-help", "label": "Send contact help request"}],
            },
            {
                "selector": "#contact-merchant",
                "visible": False,
                "inside_main": True,
                "name": "contact_merchant",
                "fields": [{"selector": "#message-merchant", "name": "message", "type": "text"}],
                "submit_controls": [{"selector": "#send-merchant", "label": "Send contact merchant request"}],
            },
        ]
        recipes = build_auto_interaction_recipes([page], limit=None)
        self.assertEqual(len(recipes), 4)
        self.assertEqual(len({recipe["recipe_id"] for recipe in recipes}), 4)

    def test_sibling_form_boundaries_receive_distinct_coverage_gap_ids(self) -> None:
        page = lead_page("https://example.com/contact")
        page["forms"] = [
            {**page["forms"][0], "selector": "#sales", "form_context": "sales"},
            {**page["forms"][0], "selector": "#support", "form_context": "support"},
        ]
        recipes = build_auto_interaction_recipes([page], limit=None)
        gaps = interaction_coverage_gaps(recipes, [])
        self.assertEqual(len(gaps), 2)
        self.assertEqual(len({gap["gap_id"] for gap in gaps}), 2)
        self.assertEqual({gap["variant_id"] for gap in gaps}, {recipes[0]["variant_id"]})

        incomplete_runs = [{**recipe, "outcome": "partial"} for recipe in recipes]
        incomplete_gaps = interaction_coverage_gaps([], incomplete_runs)
        self.assertEqual(len(incomplete_gaps), 2)
        self.assertEqual(len({gap["gap_id"] for gap in incomplete_gaps}), 2)

    def test_completed_sibling_form_does_not_close_an_unexecuted_recipe(self) -> None:
        page = lead_page("https://example.com/contact")
        page["forms"] = [
            {**page["forms"][0], "selector": "#sales", "id": "sales"},
            {**page["forms"][0], "selector": "#support", "id": "support"},
        ]
        recipes = build_auto_interaction_recipes([page], limit=None)
        completed = {**recipes[0], "outcome": "completed", "actions": [{"step": 1}]}
        remaining_gap = interaction_coverage_gaps([recipes[1]], [])
        variant_id = recipes[0]["variant_id"]
        generated_ledger = journey_coverage_ledger(
            [page],
            [{"url": page["url"], "text": "Contact", "source": "fixture"}],
            [],
            [],
            "https://example.com/",
            [completed],
            recipes,
        )
        generated_variant = generated_ledger[0]["variant_coverage"][0]
        self.assertEqual(generated_variant["status"], "partial")
        report = {
            "report_id": "discovery_example_com_sibling_forms",
            "generated_at": "2026-08-13T10:00:00+00:00",
            "root_url": "https://example.com/",
            "outcome": "partial",
            "language_summary": {"primary_language": "en", "observed_languages": ["en"]},
            "measurement_opportunity_hints": [],
            "journey_coverage_ledger": [
                {
                    "journey_id": "lead_generation",
                    "material": True,
                    "status": "observed",
                    "entry_points": [page["url"]],
                    "states_covered": ["entry", "progression", "success"],
                    "variants": ["contact"],
                    "evidence_urls": [page["url"]],
                    "unvisited_material_candidates": [],
                    "variant_coverage": [
                        {
                            "variant_id": variant_id,
                            "material": True,
                            "status": "observed",
                            "entry_points": [page["url"]],
                            "states_covered": ["entry", "progression", "success"],
                            "evidence_urls": [page["url"]],
                            "unvisited_material_candidates": [],
                        }
                    ],
                }
            ],
            "coverage_gaps": remaining_gap,
            "automatic_interaction_runs": [completed],
        }
        merged = merge_discovery_reports([report])
        self.assertEqual(len(merged["coverage_gaps"]), 1)
        self.assertEqual(merged["coverage_gaps"][0]["recipe_id"], recipes[1]["recipe_id"])

    def test_recipe_retry_replaces_its_previous_state_and_completion_closes_it(self) -> None:
        recipe = build_auto_interaction_recipes(
            [lead_page("https://example.com/quote/retry")],
            limit=None,
        )[0]

        def report(report_id: str, gap: list[dict], runs: list[dict], status: str) -> dict:
            return {
                "report_id": report_id,
                "generated_at": "2026-08-13T10:00:00+00:00",
                "root_url": "https://example.com/",
                "outcome": "partial" if gap else "completed",
                "language_summary": {"primary_language": "en", "observed_languages": ["en"]},
                "measurement_opportunity_hints": [],
                "journey_coverage_ledger": [
                    {
                        "journey_id": recipe["journey_id"],
                        "material": True,
                        "status": status,
                        "entry_points": [recipe["start_url"]],
                        "states_covered": ["entry"],
                        "variants": ["quote_retry"],
                        "evidence_urls": [recipe["start_url"]],
                        "unvisited_material_candidates": [],
                        "variant_coverage": [
                            {
                                "variant_id": recipe["variant_id"],
                                "material": True,
                                "status": status,
                                "entry_points": [recipe["start_url"]],
                                "states_covered": ["entry"],
                                "evidence_urls": [recipe["start_url"]],
                                "unvisited_material_candidates": [],
                            }
                        ],
                    }
                ],
                "coverage_gaps": gap,
                "automatic_interaction_runs": runs,
            }

        not_tested = report(
            "discovery_example_com_retry_one",
            interaction_coverage_gaps([recipe], []),
            [],
            "not_tested",
        )
        partial_run = {**recipe, "outcome": "partial", "actions": []}
        partial = report(
            "discovery_example_com_retry_two",
            interaction_coverage_gaps([], [partial_run]),
            [partial_run],
            "partial",
        )
        merged_partial = merge_discovery_reports([not_tested, partial])
        self.assertEqual(len(merged_partial["coverage_gaps"]), 1)
        self.assertEqual(merged_partial["coverage_gaps"][0]["evidence_state"], "partial")

        completed_run = {**recipe, "outcome": "completed", "actions": [{"step": 1}]}
        completed = report(
            "discovery_example_com_retry_three",
            [],
            [completed_run],
            "observed",
        )
        merged_completed = merge_discovery_reports([not_tested, partial, completed])
        self.assertEqual(merged_completed["coverage_gaps"], [])

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

    def test_context_and_discovery_report_share_one_run_identifier(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        report.update({"discovery_version": "1.3.0", "run_id": "run_" + "a" * 32})
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "discovery.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            context = build_analysis_context_seed(report, report_path)
            self.assertEqual(context["run_id"], report["run_id"])
            self.assertEqual(context["discovery_reports"][0]["run_id"], report["run_id"])
            context["discovery_reports"][0]["run_id"] = "run_" + "b" * 32
            errors = validate_discovery_bindings(context, [report_path], require_live_report=True)
        self.assertTrue(any("does not belong to context run" in error for error in errors))

    def test_legacy_discovery_does_not_gain_fabricated_run_provenance(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        report["discovery_version"] = "1.2.0"
        report.pop("run_id")
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "legacy.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            context = build_analysis_context_seed(report, report_path)
        self.assertNotIn("run_id", context)
        self.assertNotIn("context_version", context)
        self.assertNotIn("run_id", context["discovery_reports"][0])

    def test_multiple_discovery_reports_require_explicit_shared_run_provenance(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        report["discovery_version"] = "1.2.0"
        report.pop("run_id")
        second = copy.deepcopy(report)
        second["report_id"] = "discovery_example_com_legacy_second"
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.json"
            second_path = Path(directory) / "second.json"
            with self.assertRaisesRegex(ValueError, "shared run_id"):
                build_analysis_context_seed_from_reports(
                    [(report, first_path), (second, second_path)]
                )

    def test_multiple_reports_merge_independently_of_input_order(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        report.update({"discovery_version": "1.3.0", "run_id": "run_" + "a" * 32})
        second = copy.deepcopy(report)
        second["report_id"] = "discovery_example_com_fixture_second"
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.json"
            second_path = Path(directory) / "second.json"
            first_path.write_text(json.dumps(report), encoding="utf-8")
            second_path.write_text(json.dumps(second), encoding="utf-8")
            context = build_analysis_context_seed(report, first_path)
            second_record = copy.deepcopy(context["discovery_reports"][0])
            second_record.update(
                {
                    "report_id": second["report_id"],
                    "reference": str(second_path),
                    "sha256": sha256_file(second_path),
                }
            )
            context["discovery_reports"].append(second_record)
            forward = validate_discovery_bindings(
                context,
                [first_path, second_path],
                require_live_report=True,
            )
            reversed_context = copy.deepcopy(context)
            reversed_context["discovery_reports"].reverse()
            backward = validate_discovery_bindings(
                reversed_context,
                [second_path, first_path],
                require_live_report=True,
            )
            seeded_forward = build_analysis_context_seed_from_reports(
                [(report, first_path), (second, second_path)]
            )
            seeded_backward = build_analysis_context_seed_from_reports(
                [(second, second_path), (report, first_path)]
            )
        self.assertEqual(forward, [])
        self.assertEqual(backward, [])
        self.assertEqual(validate_analysis_context(context), [])
        for seeded in (seeded_forward, seeded_backward):
            seeded.pop("created_at")
        self.assertEqual(seeded_forward, seeded_backward)

    def test_targeted_report_can_close_an_earlier_not_tested_variant(self) -> None:
        first = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        first.update({"discovery_version": "1.3.0", "run_id": "run_" + "a" * 32})
        journey = first["journey_coverage_ledger"][0]
        journey["status"] = "not_tested"
        journey["variant_coverage"][0]["status"] = "not_tested"
        first["coverage_gaps"] = [
            {
                "gap_id": "product_detail_not_tested",
                "journey_id": journey["journey_id"],
                "variant_id": journey["variant_coverage"][0]["variant_id"],
                "material": True,
                "evidence_state": "not_tested",
                "description": "The product detail variant was not tested.",
                "candidate_urls": journey["entry_points"],
            }
        ]
        second = copy.deepcopy(first)
        second["report_id"] = "discovery_example_com_targeted_closure"
        second["journey_coverage_ledger"][0]["status"] = "observed"
        second["journey_coverage_ledger"][0]["variant_coverage"][0]["status"] = "observed"
        second["coverage_gaps"] = []
        merged = merge_discovery_reports([first, second])
        self.assertEqual(merged["journey_coverage_ledger"][0]["status"], "observed")
        self.assertEqual(
            merged["journey_coverage_ledger"][0]["variant_coverage"][0]["status"],
            "observed",
        )
        self.assertEqual(merged["coverage_gaps"], [])

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
