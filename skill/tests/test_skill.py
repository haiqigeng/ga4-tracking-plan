from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from adapt_tracking_plan_workbook import adapt
from diff_tracking_plans import compare
from generate_tracking_plan_workbook import build_workbook
from import_tracking_plan_workbook import import_workbook
from inspect_tracking_plan_template import inspect
from official_ga4_catalog import parse_catalog_html
from tracking_plan_model import load_json
from validate_tracking_plan import validate_plan

EXAMPLE = ROOT / "references" / "example-tracking-plan.json"
ASSET = ROOT / "assets" / "default-tracking-plan.xlsx"


class TrackingPlanSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = load_json(EXAMPLE)

    def error_codes(self, plan: dict) -> set[str]:
        return {
            issue.code
            for issue in validate_plan(plan)
            if issue.severity == "error"
        }

    def test_example_is_strictly_valid(self) -> None:
        self.assertEqual(validate_plan(self.plan), [])

    def test_official_catalog_parser_preserves_event_and_item_scope(self) -> None:
        html = """
        <h2 id="sales">Sales</h2>
        <h3 id="sample_event"><code>sample_event</code></h3>
        <p>Official event wording.</p>
        <table><tr><th>Name</th><th>Type</th><th>Required</th><th>Example</th><th>Description</th></tr>
        <tr><td>value</td><td>number</td><td>No</td><td>1</td><td>The value.</td></tr></table>
        <h4>Item parameters</h4>
        <table><tr><th>Name</th><th>Type</th><th>Required</th><th>Example</th><th>Description</th></tr>
        <tr><td>item_id</td><td>string</td><td>Yes*</td><td>SKU</td><td>The item ID.</td></tr></table>
        """
        records = parse_catalog_html(html)
        self.assertEqual(records[0]["description"], "Official event wording.")
        self.assertEqual(
            [(item["name"], item["scope"]) for item in records[0]["parameters"]],
            [("value", "event"), ("item_id", "item")],
        )

    def test_manual_only_schema_rejects_enhanced_measurement_classification(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["events"][0]["classification"] = "enhanced_measurement"
        self.assertIn("SCHEMA", self.error_codes(plan))

    def test_finite_value_domains_stop_at_fifty(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["events"][0]["parameters"][0]["allowed_values"] = [
            f"value_{index}" for index in range(51)
        ]
        self.assertIn("SCHEMA", self.error_codes(plan))

    def test_custom_event_cannot_relabel_an_official_event(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["events"][1]["classification"] = "custom"
        plan["events"][1]["custom_decision"] = {
            "business_need": "Measure product detail views.",
            "official_candidate": "view_item",
            "why_not_fit": "The official event would fit.",
        }
        self.assertIn("CUSTOM_EVENT_IS_OFFICIAL", self.error_codes(plan))

    def test_every_pushed_field_requires_an_event_binding(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["events"][2]["data_layer"]["push"]["event_data"]["unbound_field"] = "x"
        self.assertIn("UNBOUND_DATALAYER_FIELDS", self.error_codes(plan))

    def test_workbook_is_lean_quoted_and_maintenance_ready(self) -> None:
        workbook = build_workbook(self.plan)
        visible = [
            sheet.title
            for sheet in workbook.worksheets
            if sheet.sheet_state == "visible"
        ]
        self.assertEqual(
            visible,
            [
                "Guide",
                "Event Matrix",
                "Parameter Reference",
                "core_data",
                "view_item",
                "begin_quote",
            ],
        )
        self.assertEqual(
            workbook["__tracking_plan_model"].sheet_state,
            "veryHidden",
        )
        matrix_headers = {
            str(workbook["Event Matrix"].cell(4, column).value or "")
            for column in range(1, 8)
        }
        parameter_headers = {
            str(workbook["Parameter Reference"].cell(4, column).value or "")
            for column in range(1, 8)
        }
        forbidden = {
            "Availability",
            "Data owner",
            "Registered in GA4",
            "Privacy",
            "Display name",
            "Agent reasoning",
        }
        self.assertTrue(matrix_headers.isdisjoint(forbidden))
        self.assertTrue(parameter_headers.isdisjoint(forbidden))
        guide_headers = {
            str(workbook["Guide"].cell(15, column).value or "")
            for column in range(1, 5)
        }
        self.assertNotIn("Status", guide_headers)
        self.assertIn("page_template (mandatory)", workbook["Event Matrix"]["G5"].value)
        self.assertNotIn("page_template", workbook["Event Matrix"]["G6"].value)
        code = str(workbook["view_item"]["A21"].value)
        self.assertIn('"event": "view_item"', code)
        self.assertIn('"item_color": "white"', code)

    def test_french_workbook_localizes_human_labels_and_requirements(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["document"]["language"] = "fr"
        plan["document"]["value_language"] = "fr"
        workbook = build_workbook(plan)
        self.assertIn("Valeurs des variables", workbook.sheetnames)
        self.assertIn("obligatoire", str(workbook["Event Matrix"]["G5"].value))
        self.assertEqual(workbook["view_item"]["D14"].value, "obligatoire")
        self.assertEqual(workbook["view_item"]["D12"].value, "conditionnel")

    def test_generated_workbook_round_trips_losslessly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.xlsx"
            build_workbook(self.plan).save(path)
            imported = import_workbook(path)
        self.assertEqual(imported, self.plan)

    def test_semantic_diff_reports_trigger_and_values(self) -> None:
        updated = copy.deepcopy(self.plan)
        updated["document"]["version"] = "1.1"
        updated["events"][2]["trigger"] += " Fire only once per form instance."
        updated["events"][2]["parameters"][1]["allowed_values"].append("solar")
        result = compare(self.plan, updated)
        entities = {(item["entity"], item["key"]) for item in result["changes"]}
        self.assertIn(("trigger", "begin_quote:trigger"), entities)
        self.assertIn(
            (
                "value_domain",
                "begin_quote:project_type|event|event_data.project_type",
            ),
            entities,
        )

    def test_default_asset_has_semantic_regions(self) -> None:
        result = inspect(ASSET)
        self.assertTrue(result["regions"]["event_matrix"])
        self.assertTrue(result["regions"]["parameter_reference"])
        self.assertTrue(result["regions"]["event_tabs"])

    def test_supplied_template_adaptation_uses_semantic_regions(self) -> None:
        updated = copy.deepcopy(self.plan)
        updated["events"][2]["trigger"] += " Fire only once per form instance."
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.xlsx"
            output = Path(directory) / "adapted.xlsx"
            build_workbook(self.plan).save(source)
            mapping = inspect(source)
            workbook = adapt(updated, source, mapping)
            workbook.save(output)
            reopened = load_workbook(output, data_only=False)
            imported = import_workbook(output)
        self.assertIn(
            "Fire only once per form instance.",
            str(reopened["begin_quote"]["B7"].value),
        )
        self.assertIn(
            '"event": "begin_quote"',
            str(reopened["begin_quote"]["A16"].value),
        )
        self.assertEqual(imported, updated)

    def test_skill_has_one_adaptive_workflow_not_scope_tiers(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Use one adaptive workflow and one quality standard.", text)
        self.assertNotIn("## Scope Tiers", text)
        self.assertNotIn('Tier 1 — "Quick Plan"', text)
        self.assertNotIn("event-count-based execution mode", text)


if __name__ == "__main__":
    unittest.main()
