from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from diff_tracking_plans import compare  # noqa: E402


class TrackingPlanDiffTests(unittest.TestCase):
    def test_event_parameter_and_evidence_changes_are_reported(self) -> None:
        plan = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))
        updated = copy.deepcopy(plan)
        updated["events"][0]["trigger"] = "Updated trigger"
        updated["parameters"] = updated["parameters"][1:]
        updated["screenshot_evidence"][0]["notes"] = "Updated evidence note"
        diff = compare(plan, updated)
        self.assertIn(plan["events"][0]["event_id"], diff["events"]["changed"])
        self.assertIn(plan["parameters"][0]["parameter_name"], diff["parameters"]["removed"])
        self.assertIn(plan["screenshot_evidence"][0]["evidence_id"], diff["screenshot_evidence"]["changed"])


if __name__ == "__main__":
    unittest.main()
