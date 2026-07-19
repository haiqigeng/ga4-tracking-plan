from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from init_tracking_plan import initialize_plan  # noqa: E402
from init_tracking_plan import main as initialize_main  # noqa: E402
from validate_tracking_plan import validate_plan_data  # noqa: E402


class PlanInitializerTests(unittest.TestCase):
    def test_not_requested_scaffold_is_valid_and_focused(self) -> None:
        plan = initialize_plan(
            "https://example.com/start",
            title="Example GA4 plan",
            journey_name="Product discovery",
            screenshots="not_requested",
        )

        self.assertEqual(
            {issue.code for issue in validate_plan_data(plan)},
            {"OFFICIAL_SOURCE_RECEIPT_INVALID", "PLAYWRIGHT_EXPLORATION_ATTEMPT_MISSING"},
        )
        self.assertEqual(plan["schema_version"], "3.0.0")
        self.assertEqual([event["event_name"] for event in plan["events"]], ["page_view"])
        self.assertEqual(plan["measurement_brief"][0]["journey_id"], "product_discovery")
        self.assertEqual(plan["screenshot_evidence"], [])
        self.assertNotIn("user_id", {item["parameter_name"] for item in plan["parameters"]})
        self.assertIn("page", plan["events"][0]["data_layer"]["push"])
        self.assertNotIn("event", plan["events"][0]["data_layer"]["push"])
        self.assertNotIn("page_data", plan["events"][0]["data_layer"]["push"])
        self.assertEqual(plan["user_context"]["data_layer_object"], "user")
        self.assertEqual(plan["language_policy"]["site_languages"], [])
        self.assertEqual(plan["language_policy"]["controlled_value_language"], "en")
        self.assertEqual(plan["events"][0]["data_layer"]["push"]["page"]["page_template"], "%page_template_to_resolve%")

    def test_default_scaffold_keeps_playwright_gate_open(self) -> None:
        plan = initialize_plan("https://example.com/")
        codes = {issue.code for issue in validate_plan_data(plan)}

        self.assertIn("PLAYWRIGHT_MCP_ATTEMPT_MISSING", codes)
        self.assertEqual(plan["screenshot_capture"]["outcome"], "blocked")
        self.assertEqual(plan["screenshot_evidence"][0]["status"], "blocked")

    def test_french_scaffold_is_valid_and_localizes_human_copy(self) -> None:
        plan = initialize_plan(
            "https://example.fr/",
            workbook_language="fr",
            site_languages=["fr"],
            screenshots="not_requested",
        )

        self.assertEqual(
            {issue.code for issue in validate_plan_data(plan)},
            {"OFFICIAL_SOURCE_RECEIPT_INVALID", "PLAYWRIGHT_EXPLORATION_ATTEMPT_MISSING"},
        )
        self.assertEqual(plan["language_policy"]["workbook_language"], "fr")
        self.assertEqual(plan["events"][0]["official_verification"]["translation_status"], "analyst_translation")
        self.assertIn("page a été chargée", plan["events"][0]["event_summary"])
        self.assertEqual(plan["parameters"][0]["display_name"], "URL de la page")

    def test_invalid_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            initialize_plan("example.com")

    def test_cli_writes_a_not_requested_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "plan.json"
            with patch.object(
                sys,
                "argv",
                [
                    "init_tracking_plan.py",
                    "https://example.com/start",
                    "--output",
                    str(output),
                    "--journey-name",
                    "Service discovery",
                    "--screenshots",
                    "not_requested",
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(initialize_main(), 0)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(plan["measurement_brief"][0]["journey_id"], "service_discovery")


if __name__ == "__main__":
    unittest.main()
