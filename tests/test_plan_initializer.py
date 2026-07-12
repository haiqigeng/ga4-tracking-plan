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

        self.assertEqual(validate_plan_data(plan), [])
        self.assertEqual(plan["schema_version"], "2.4.0")
        self.assertEqual([event["event_name"] for event in plan["events"]], ["page_view"])
        self.assertEqual(plan["measurement_brief"][0]["journey_id"], "product_discovery")
        self.assertEqual(plan["screenshot_evidence"][0]["status"], "not_needed")
        self.assertNotIn("user_id", {item["parameter_name"] for item in plan["parameters"]})

    def test_default_scaffold_keeps_playwright_gate_open(self) -> None:
        plan = initialize_plan("https://example.com/")
        codes = {issue.code for issue in validate_plan_data(plan)}

        self.assertIn("PLAYWRIGHT_MCP_ATTEMPT_MISSING", codes)
        self.assertEqual(plan["screenshot_capture"]["outcome"], "blocked")
        self.assertEqual(plan["screenshot_evidence"][0]["status"], "blocked")

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
