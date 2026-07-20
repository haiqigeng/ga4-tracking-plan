from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from export_tracking_plan_csv import export_rows  # noqa: E402
from generate_tracking_plan_workbook import binding_status, build_workbook  # noqa: E402


class WorkbookContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(
                encoding="utf-8"
            )
        )

    def test_screenshot_register_is_conditional(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["screenshot_capture"]["requirement"] = "not_requested"
        plan["screenshot_evidence"] = []
        for event in plan["events"]:
            event["screenshot_coverage"] = "not_needed"

        workbook = build_workbook(plan)

        self.assertEqual(
            workbook.sheetnames,
            [
                "00 Overview",
                "01 GTM Protocol",
                "02 Parameter Reference",
                "03 Event Matrix",
                "04 DataLayer Examples",
            ],
        )

    def test_renderer_does_not_mutate_validated_plan(self) -> None:
        plan = copy.deepcopy(self.fixture)
        before = json.dumps(plan, ensure_ascii=False, sort_keys=True)

        build_workbook(plan)

        self.assertEqual(json.dumps(plan, ensure_ascii=False, sort_keys=True), before)

    def test_event_matrix_uses_paired_binding_columns(self) -> None:
        workbook = build_workbook(copy.deepcopy(self.fixture))
        matrix = workbook["03 Event Matrix"]

        self.assertEqual(matrix.max_column, 10)
        self.assertEqual(matrix["C5"].value, "Expected value / rule")
        self.assertEqual(matrix["D5"].value, "Requirement / availability")
        self.assertEqual(matrix.page_setup.orientation, matrix.ORIENTATION_LANDSCAPE)
        self.assertEqual(str(matrix.page_setup.paperSize), matrix.PAPERSIZE_A3)
        self.assertEqual(matrix.page_setup.fitToWidth, 1)
        self.assertEqual(matrix.page_setup.fitToHeight, 0)
        self.assertEqual(matrix.sheet_view.zoomScale, 90)
        self.assertEqual(matrix.print_title_rows, "$1:$5")

        protocol = workbook["01 GTM Protocol"]
        connected_user_row = next(
            row for row in range(1, protocol.max_row + 1)
            if protocol.cell(row, 1).value == "Connected user context"
        )
        self.assertGreaterEqual(protocol.row_dimensions[connected_user_row].height, 90)
        official_reference_rows = [
            row for row in range(1, protocol.max_row + 1)
            if str(protocol.cell(row, 3).value or "").startswith("https://developers.google.com/")
        ]
        self.assertEqual(len(official_reference_rows), 7)
        self.assertEqual(protocol.print_title_rows, "$1:$3")
        self.assertEqual(protocol.page_setup.fitToHeight, 1)
        self.assertEqual(workbook["04 DataLayer Examples"].page_setup.fitToHeight, 1)
        self.assertEqual(workbook["05 Screenshot Register"].page_setup.fitToHeight, 0)

    def test_event_specific_parameter_governance_is_visible_in_exports(self) -> None:
        plan = copy.deepcopy(self.fixture)
        event = next(item for item in plan["events"] if item["event_name"] == "view_promotion")
        binding = {
            "parameter_name": "search_term",
            "classification": "custom_event_parameter",
            "requirement": "optional",
            "inclusion_reason": "Connect promotion exposure with the originating on-site search.",
            "availability": "confirmed_available",
            "data_owner": "Analytics",
            "official_gap": "The view_promotion table has no field for the originating search query.",
            "source_path": "search.query",
            "persistence_rule": "Capture with the promotion context, retain until selection, and clear when the list context changes.",
        }
        event["parameter_bindings"].append(binding)

        status = binding_status(plan, binding)
        self.assertIn("custom_event_parameter", status)
        self.assertIn("Official gap:", status)
        self.assertIn("Source: search.query", status)
        self.assertIn("Persistence:", status)

        row = next(
            item
            for item in export_rows(plan)
            if item["event_name"] == "view_promotion" and item["parameter_name"] == "search_term"
        )
        self.assertEqual(row["classification_or_source"], "custom_event_parameter")
        self.assertEqual(row["binding_official_gap"], binding["official_gap"])
        self.assertEqual(row["source_path"], "search.query")
        self.assertEqual(row["persistence_rule"], binding["persistence_rule"])

    def test_reusable_event_is_rendered_once_with_all_journeys(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["measurement_brief"].append(
            {
                "journey_id": "shared_navigation",
                "journey_name": "Shared navigation",
                "page_type": "Shared navigation surfaces",
                "scope": "Header and footer",
                "urls_or_patterns": ["https://www.example.com/*"],
                "expected_actions": ["Navigate to another section"],
                "business_questions": ["Which navigation surfaces support discovery?"],
                "analysis_needs": ["Compare navigation usage by surface."],
                "success_signals": ["page_view"],
            }
        )
        plan["events"][0]["journey_ids"].append("shared_navigation")

        matrix = build_workbook(plan)["03 Event Matrix"]
        page_view_blocks = [
            row
            for row in range(1, matrix.max_row + 1)
            if str(matrix.cell(row, 1).value or "").startswith("J-")
            and matrix.cell(row, 3).value == "page_view"
        ]

        self.assertEqual(len(page_view_blocks), 1)
        block_row = page_view_blocks[0]
        journey_row = next(
            row
            for row in range(block_row + 1, matrix.max_row + 1)
            if matrix.cell(row, 1).value == "journeys"
        )
        self.assertEqual(
            matrix.cell(journey_row, 3).value,
            "Homepage discovery | Shared navigation",
        )


if __name__ == "__main__":
    unittest.main()
