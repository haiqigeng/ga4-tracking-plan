from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from migrate_tracking_plan import migrate_plan  # noqa: E402
from validate_tracking_plan import validate_plan_data  # noqa: E402


class ContractMigrationTests(unittest.TestCase):
    def test_removed_v1_fields_do_not_survive(self) -> None:
        plan = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))
        legacy = copy.deepcopy(plan)
        legacy.update({"schema_version": "1.1.0", "analytics_platforms": ["ga4"], "qa_cases": []})
        legacy.pop("screenshot_capture", None)
        legacy["events"][0].update({"primary_platform": "ga4", "platform_mappings": [], "qa": {}})
        migrated = migrate_plan(legacy)

        self.assertEqual(migrated["schema_version"], "2.4.0")
        self.assertNotIn("analytics_platforms", migrated)
        self.assertNotIn("qa_cases", migrated)
        self.assertNotIn("primary_platform", migrated["events"][0])
        self.assertNotIn("qa", migrated["events"][0])
        self.assertIn(migrated["events"][0]["access_context"], {"public", "authentication_flow", "authenticated_area"})
        self.assertIn("screenshot_coverage", migrated["events"][0])
        self.assertTrue(all("scenario_id" in row for row in migrated["screenshot_evidence"]))
        self.assertIn("screenshot_capture", migrated)
        self.assertEqual(migrated["screenshot_capture"]["playwright_mcp_attempt"]["status"], "not_recorded")
        self.assertIn("PLAYWRIGHT_MCP_ATTEMPT_MISSING", {issue.code for issue in validate_plan_data(migrated)})


if __name__ == "__main__":
    unittest.main()
