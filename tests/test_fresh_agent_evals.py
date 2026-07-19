from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_fresh_agent_evals import DEFAULT_MANIFEST, score_results, validate_manifest  # noqa: E402


class FreshAgentEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    def complete_results(self) -> dict:
        return {
            "case_results": [
                {
                    "case_id": case["case_id"],
                    "required_outcomes": {item["criterion_id"]: "pass" for item in case["required_outcomes"]},
                    "prohibited_outcomes": {item["criterion_id"]: "absent" for item in case["prohibited_outcomes"]},
                    "notes": "Reviewed generic evaluation evidence.",
                }
                for case in self.manifest["cases"]
            ]
        }

    def test_manifest_is_generic_and_complete(self) -> None:
        self.assertEqual(validate_manifest(self.manifest), [])

        malformed = copy.deepcopy(self.manifest)
        malformed["cases"][1]["case_id"] = malformed["cases"][0]["case_id"]
        malformed["cases"][1]["prompt"] = "Inspect https://client.example.net now."
        malformed["cases"][1]["required_outcomes"][0]["criterion_id"] = malformed["cases"][1]["prohibited_outcomes"][0]["criterion_id"]
        errors = validate_manifest(malformed)
        self.assertTrue(any("Duplicate case_id" in error for error in errors))
        self.assertTrue(any("non-generic domain" in error for error in errors))
        self.assertTrue(any("duplicate criterion_id" in error for error in errors))
        self.assertTrue(any("does not match" in error for error in errors))

    def test_complete_passing_results_are_accepted(self) -> None:
        self.assertEqual(score_results(self.manifest, self.complete_results()), [])

    def test_blocking_failure_is_rejected(self) -> None:
        results = copy.deepcopy(self.complete_results())
        results["case_results"][0]["required_outcomes"]["journey_coherence"] = "fail"
        errors = score_results(self.manifest, results)
        self.assertTrue(any("Blocking criterion failed" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
