from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from official_ga4_catalog import catalog_receipt_signature  # noqa: E402
from official_source_receipt import finalize_receipt, receipt_validation_errors, tracking_plan_sha256  # noqa: E402
from resolve_tracking_plan import RECOMMENDED_CATALOG, resolve_plan  # noqa: E402
from resolve_tracking_plan import main as resolve_main  # noqa: E402


class OfficialSourceReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(
                encoding="utf-8"
            )
        )

    def test_fixture_receipt_is_bound_to_plan_sources_and_catalog(self) -> None:
        plan = copy.deepcopy(self.fixture)
        expected_urls = {
            source["url"].split("#", 1)[0].rstrip("/")
            for source in plan["documentation_sources_checked"]
            if source["source_type"] == "official"
        }
        errors = receipt_validation_errors(
            plan["official_source_check"],
            date.fromisoformat(plan["document"]["publish_date"]),
            expected_urls,
            catalog_receipt_signature(RECOMMENDED_CATALOG),
        )
        self.assertEqual(errors, [])

    def test_catalog_signature_cannot_be_forged_by_rehashing(self) -> None:
        plan = copy.deepcopy(self.fixture)
        receipt = copy.deepcopy(plan["official_source_check"])
        receipt["catalog_signature_sha256"] = "0" * 64
        receipt = finalize_receipt(receipt)

        with self.assertRaisesRegex(ValueError, "different bundled GA4 catalog"):
            resolve_plan(plan, receipt)

    def test_resolved_plan_change_invalidates_receipt(self) -> None:
        plan = copy.deepcopy(self.fixture)
        plan["events"][0]["trigger"] = "Changed after resolution."
        errors = receipt_validation_errors(
            plan["official_source_check"],
            publish_date=date.fromisoformat(plan["document"]["publish_date"]),
            expected_catalog_signature=catalog_receipt_signature(RECOMMENDED_CATALOG),
            expected_resolved_plan_sha256=tracking_plan_sha256(plan),
        )

        self.assertIn("Resolved plan content changed after official-source resolution.", errors)

    def test_resolution_binds_receipt_and_source_check_date(self) -> None:
        plan = copy.deepcopy(self.fixture)
        resolved = resolve_plan(plan, copy.deepcopy(plan["official_source_check"]))

        self.assertEqual(
            resolved["official_source_check"]["draft_plan_sha256"],
            plan["official_source_check"]["draft_plan_sha256"],
        )
        self.assertEqual(
            resolved["official_source_check"]["resolved_plan_sha256"],
            tracking_plan_sha256(resolved),
        )
        official_dates = {
            source["checked_date"]
            for source in resolved["documentation_sources_checked"]
            if source["source_type"] == "official"
        }
        self.assertEqual(official_dates, {plan["document"]["publish_date"]})

    def test_resolver_cli_writes_only_a_valid_resolved_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            draft = folder / "draft.json"
            receipt = folder / "receipt.json"
            output = folder / "resolved.json"
            draft.write_text(json.dumps(self.fixture), encoding="utf-8")
            receipt.write_text(json.dumps(self.fixture["official_source_check"]), encoding="utf-8")
            argv = [
                "resolve_tracking_plan.py",
                str(draft),
                "--receipt",
                str(receipt),
                "--output",
                str(output),
            ]

            with patch.object(sys, "argv", argv), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(resolve_main(), 0)

            self.assertTrue(output.exists())

    def test_resolver_cli_does_not_write_an_invalid_artifact(self) -> None:
        plan = copy.deepcopy(self.fixture)
        custom_event = next(event for event in plan["events"] if event["classification"] == "custom")
        custom_event["event_summary"] = "Reusable event."
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            draft = folder / "draft.json"
            receipt = folder / "receipt.json"
            output = folder / "resolved.json"
            draft.write_text(json.dumps(plan), encoding="utf-8")
            receipt.write_text(json.dumps(plan["official_source_check"]), encoding="utf-8")
            argv = [
                "resolve_tracking_plan.py",
                str(draft),
                "--receipt",
                str(receipt),
                "--output",
                str(output),
            ]

            with patch.object(sys, "argv", argv), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(resolve_main(), 1)

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
