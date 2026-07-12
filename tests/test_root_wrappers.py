from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAPPERS = [
    "adapt_tracking_plan_workbook.py",
    "annotate_screenshot.py",
    "check_official_catalog.py",
    "discover_site_journeys.py",
    "discover_site_journeys_playwright.py",
    "diff_tracking_plans.py",
    "export_tracking_plan_csv.py",
    "generate_tracking_plan_workbook.py",
    "init_tracking_plan.py",
    "inspect_tracking_plan_template.py",
    "inspect_browser_environment.py",
    "migrate_tracking_plan.py",
    "validate_tracking_plan.py",
]


class RootWrapperTests(unittest.TestCase):
    def test_wrappers_delegate_to_shared_runner(self) -> None:
        for wrapper in WRAPPERS:
            text = (ROOT / "scripts" / wrapper).read_text(encoding="utf-8")
            with self.subTest(wrapper=wrapper):
                self.assertIn("from _run_skill_script import run", text)
                self.assertIn("run(__file__)", text)


if __name__ == "__main__":
    unittest.main()
