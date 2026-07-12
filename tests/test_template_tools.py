from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from adapt_tracking_plan_workbook import adapt_workbook, load_mapping  # noqa: E402
from adapt_tracking_plan_workbook import main as adapt_main  # noqa: E402
from inspect_tracking_plan_template import inspect_workbook  # noqa: E402
from inspect_tracking_plan_template import main as inspect_main  # noqa: E402


class TemplateToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = json.loads(
            (ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8")
        )

    def test_inspector_reports_structure_without_cell_content_dump(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "client.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Client Overview"
            sheet.append(["Name", "Value"])
            sheet.append(["Total", "=1+1"])
            sheet["A2"].comment = Comment("Keep this analyst note", "Analyst")
            sheet.protection.sheet = True
            table = Table(displayName="ClientTable", ref="A1:B2")
            sheet.add_table(table)
            validation = DataValidation(type="list", formula1='"ok,ko"')
            sheet.add_data_validation(validation)
            validation.add("B2")
            workbook.save(path)

            inventory = inspect_workbook(path)

        self.assertEqual(inventory["sheet_count"], 1)
        inspected = inventory["sheets"][0]
        self.assertEqual(inspected["sheet_name"], "Client Overview")
        self.assertEqual(inspected["formula_count"], 1)
        self.assertTrue(inspected["sheet_protected"])
        self.assertEqual(inspected["table_count"], 1)
        self.assertEqual(inspected["data_validation_count"], 1)
        self.assertEqual(inspected["comment_count"], 1)
        self.assertIn("formula cells", inspected["destructive_overwrite_hazards"])
        self.assertNotIn("cells", inspected)

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
            notes["B1"] = "=1+1"
            workbook.save(template)

            adapted = adapt_workbook(self.plan, template, {"00 Overview": "Client Overview"})

            self.assertEqual(adapted["Client Notes"]["A1"].value, "Keep this client-owned sheet")
            self.assertEqual(adapted["Client Notes"]["B1"].value, "=1+1")
            self.assertEqual(adapted["Client Overview"]["A1"].value, self.plan["document"]["title"])
            self.assertEqual(adapted["Client Overview"]["A1"].fill.fgColor.rgb, "0000FF00")
            self.assertEqual(adapted["Client Overview"].column_dimensions["A"].width, 42)
            self.assertEqual(adapted["Client Overview"].freeze_panes, "B4")
            self.assertIn("03 Event Matrix", adapted.sheetnames)

    def test_adapter_blocks_formula_sheet_without_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            template = Path(raw) / "client.xlsx"
            workbook = Workbook()
            overview = workbook.active
            overview.title = "Client Overview"
            overview.append(["Name", "Value"])
            overview.append(["Total", "=1+1"])
            overview["B2"] = "=1+1"
            overview["A2"].comment = Comment("Client note", "Analyst")
            overview.merge_cells("C3:D3")
            overview["C3"] = "Merged client heading"
            overview.add_table(Table(displayName="MappedTable", ref="A1:B2"))
            validation = DataValidation(type="list", formula1='"ok,ko"')
            overview.add_data_validation(validation)
            validation.add("B2")
            workbook.save(template)

            with self.assertRaisesRegex(ValueError, "formula cells"):
                adapt_workbook(self.plan, template, {"00 Overview": "Client Overview"})

            adapted = adapt_workbook(
                self.plan,
                template,
                {"00 Overview": "Client Overview"},
                allow_destructive_template_overwrite=True,
            )
            self.assertEqual(adapted["Client Overview"]["A1"].value, self.plan["document"]["title"])
            self.assertNotEqual(adapted["Client Overview"]["B2"].value, "=1+1")
            adapted_path = Path(raw) / "adapted.xlsx"
            adapted.save(adapted_path)
            self.assertEqual(inspect_workbook(adapted_path)["sheet_count"], 6)

    def test_cli_tools_write_adapted_workbook_and_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            template = folder / "client.xlsx"
            output = folder / "adapted.xlsx"
            inventory = folder / "inventory.json"
            workbook = Workbook()
            workbook.active.title = "Client Notes"
            workbook.save(template)

            with patch.object(sys, "argv", ["inspect_tracking_plan_template.py", str(template), "--output", str(inventory)]):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(inspect_main(), 0)
            self.assertEqual(json.loads(inventory.read_text(encoding="utf-8"))["sheet_count"], 1)

            plan_path = ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json"
            with patch.object(
                sys,
                "argv",
                ["adapt_tracking_plan_workbook.py", str(plan_path), str(template), "--output", str(output)],
            ):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(adapt_main(), 0)
            self.assertTrue(output.exists())

    def test_mapping_must_be_a_string_dictionary(self) -> None:
        self.assertEqual(load_mapping(None), {})
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "mapping.json"
            path.write_text('["not", "a", "mapping"]', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_mapping(path)
            path.write_text('{"00 Overview": "Client Overview"}', encoding="utf-8")
            self.assertEqual(load_mapping(path), {"00 Overview": "Client Overview"})


if __name__ == "__main__":
    unittest.main()
