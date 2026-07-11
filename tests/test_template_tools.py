from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import PatternFill

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from adapt_tracking_plan_workbook import adapt_workbook, load_mapping  # noqa: E402
from inspect_tracking_plan_template import inspect_workbook  # noqa: E402


class TemplateToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(
            (ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8")
        )

    def test_inspector_reports_structure_without_cell_content_dump(self) -> None:
        inventory = inspect_workbook(ROOT / "skill" / "assets" / "ga4_tracking_plan_template.xlsx")
        self.assertEqual(inventory["sheet_count"], 6)
        self.assertEqual(inventory["sheets"][0]["sheet_name"], "00 Overview")
        self.assertIn("freeze_panes", inventory["sheets"][0])
        self.assertNotIn("cells", inventory["sheets"][0])

    def test_adapter_preserves_unmapped_sheet_and_client_surface_style(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            template = Path(raw) / "client.xlsx"
            workbook = Workbook()
            overview = workbook.active
            overview.title = "Client Overview"
            overview["A1"] = "Old content"
            overview["A1"].fill = PatternFill("solid", fgColor="00FF00")
            overview.column_dimensions["A"].width = 42
            overview.freeze_panes = "B4"
            notes = workbook.create_sheet("Client Notes")
            notes["A1"] = "Keep this client-owned sheet"
            workbook.save(template)

            adapted = adapt_workbook(self.plan, template, {"00 Overview": "Client Overview"})

            self.assertEqual(adapted["Client Notes"]["A1"].value, "Keep this client-owned sheet")
            self.assertEqual(adapted["Client Overview"]["A1"].value, self.plan["document"]["title"])
            self.assertEqual(adapted["Client Overview"]["A1"].fill.fgColor.rgb, "0000FF00")
            self.assertEqual(adapted["Client Overview"].column_dimensions["A"].width, 42)
            self.assertEqual(adapted["Client Overview"].freeze_panes, "B4")
            self.assertIn("03 Event Matrix", adapted.sheetnames)

    def test_mapping_must_be_a_string_dictionary(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "mapping.json"
            path.write_text('["not", "a", "mapping"]', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_mapping(path)


if __name__ == "__main__":
    unittest.main()
