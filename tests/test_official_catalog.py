from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from check_official_catalog import main as catalog_main  # noqa: E402
from check_official_catalog import validate_metadata  # noqa: E402
from official_ga4_catalog import (  # noqa: E402
    STANDARD_EVENT_OFFICIAL_SEMANTICS,
    catalog_semantic_signature,
    catalog_signature,
    enrich_plan_official_semantics,
    parse_catalog_html,
    resolve_event_semantics,
    resolve_parameter_semantics,
)
from official_source_receipt import tracking_plan_sha256  # noqa: E402


class OfficialCatalogTests(unittest.TestCase):
    def test_offline_receipt_is_bound_to_the_supplied_draft(self) -> None:
        fixture = ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json"
        plan = json.loads(fixture.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as raw:
            receipt_path = Path(raw) / "receipt.json"
            argv = [
                "check_official_catalog.py",
                "--offline",
                "--plan",
                str(fixture),
                "--receipt",
                str(receipt_path),
            ]
            with patch.object(sys, "argv", argv), redirect_stdout(StringIO()):
                self.assertEqual(catalog_main(), 0)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(receipt["mode"], "offline")
        self.assertEqual(receipt["draft_plan_sha256"], tracking_plan_sha256(plan))
        self.assertEqual(receipt["resolved_plan_sha256"], "")

    def test_official_html_parsing(self) -> None:
        page = """
        <h2 id="general">General</h2>
        <h3 id="login"><code>login</code></h3>
        <p>Log in.</p>
        <table><tr><th>Name</th><th>Type</th><th>Required</th><th>Example</th><th>Description</th></tr>
        <tr><td>method</td><td>string</td><td>No</td><td>Google</td><td>Login method.</td></tr></table>
        <h3 id="purchase"><code>purchase</code></h3>
        <p>Purchase.</p>
        <table><tr><th>Name</th><th>Type</th><th>Required</th><th>Example</th><th>Description</th></tr>
        <tr><td>transaction_id</td><td>string</td><td>Yes</td><td>T123</td><td>Transaction identifier.</td></tr></table>
        <h4>Item parameters</h4>
        <table><tr><th>Name</th><th>Type</th><th>Required</th><th>Example</th><th>Description</th></tr>
        <tr><td>item_id</td><td>string</td><td>One of item_id or item_name is required.</td><td>SKU1</td><td>Item identifier.</td></tr></table>
        Last updated 2026-06-26 UTC
        """
        catalog, updated = parse_catalog_html(page)
        self.assertEqual(updated, "2026-06-26")
        self.assertEqual(set(catalog_signature(catalog)), {"login", "purchase"})
        self.assertEqual(
            catalog_signature(catalog)["purchase"],
            (("transaction_id", "event", "string", "Yes"), ("item_id", "item", "string", "One of item_id or item_name is required.")),
        )

    def test_parameter_signature_detects_documentation_drift(self) -> None:
        local = [{"event": "login", "parameters": [{"name": "method", "scope": "event", "type": "string", "required": "No"}]}]
        official = [{"event": "login", "parameters": [{"name": "method", "scope": "event", "type": "string", "required": "Yes"}]}]
        self.assertNotEqual(catalog_signature(local), catalog_signature(official))

    def test_semantic_signature_detects_wording_drift(self) -> None:
        local = [{"event": "login", "description": "A user logged in.", "parameters": []}]
        official = [{"event": "login", "description": "A user logged into an account.", "parameters": []}]
        self.assertEqual(catalog_signature(local), catalog_signature(official))
        self.assertNotEqual(catalog_semantic_signature(local), catalog_semantic_signature(official))

    def test_official_resolver_pinpoints_event_and_parameter_zones(self) -> None:
        rules = ROOT / "skill" / "references" / "03-rules"
        catalog = json.loads((rules / "library-ga4-recommended-events.json").read_text(encoding="utf-8"))
        scenarios = json.loads((rules / "library-ga4-event-scenarios.json").read_text(encoding="utf-8"))
        parameters = json.loads((rules / "library-parameters.json").read_text(encoding="utf-8"))

        event = resolve_event_semantics("add_payment_info", "recommended_ecommerce", catalog, scenarios)
        self.assertEqual(event["definition"], "This event signifies a user has submitted their payment information in an ecommerce checkout process.")
        self.assertEqual(event["source_locator"], "add_payment_info")
        self.assertIn("Initiate the checkout process", event["trigger_source_section"])
        self.assertEqual(event["trigger_guidance"], "Send the add_payment_info event when a user submits their payment information.")
        self.assertNotEqual(event["trigger_guidance"], event["definition"])
        self.assertIn("implementation example", event["trigger_source_locator"])

        currency = resolve_parameter_semantics(
            "currency",
            "ga4_ecommerce_parameter",
            ["add_payment_info"],
            catalog,
            parameters,
        )[0]
        self.assertEqual(currency["source_locator"], "currency")
        self.assertIn("3-letter ISO 4217", currency["description"])
        self.assertIn("currency is required", currency["description"])

        page_view = resolve_event_semantics("page_view", "automatic", catalog, scenarios)
        self.assertEqual(page_view["definition"], STANDARD_EVENT_OFFICIAL_SEMANTICS["page_view"]["definition"])
        self.assertEqual(page_view["trigger_guidance"], STANDARD_EVENT_OFFICIAL_SEMANTICS["page_view"]["trigger"])
        self.assertEqual(page_view["source_url"], STANDARD_EVENT_OFFICIAL_SEMANTICS["page_view"]["source_url"])
        self.assertEqual(page_view["source_section"], STANDARD_EVENT_OFFICIAL_SEMANTICS["page_view"]["source_section"])
        for standard_event in scenarios["standard_events"]:
            expected = STANDARD_EVENT_OFFICIAL_SEMANTICS[standard_event["event"]]
            self.assertEqual(standard_event["official_trigger"], expected["official_trigger"])
            self.assertEqual(
                tuple(part.strip() for part in standard_event["parameters"].split(",")),
                expected["parameters"],
            )
        self.assertEqual(validate_metadata(scenarios), [])
        drifted_scenarios = json.loads(json.dumps(scenarios))
        drifted_scenarios["standard_events"][0]["trigger"] = "A page changed."
        self.assertTrue(any("page_view" in error and "trigger" in error for error in validate_metadata(drifted_scenarios)))

    def test_enrichment_replaces_lazy_official_wording(self) -> None:
        rules = ROOT / "skill" / "references" / "03-rules"
        catalog = json.loads((rules / "library-ga4-recommended-events.json").read_text(encoding="utf-8"))
        scenarios = json.loads((rules / "library-ga4-event-scenarios.json").read_text(encoding="utf-8"))
        parameters = json.loads((rules / "library-parameters.json").read_text(encoding="utf-8"))
        plan = {
            "events": [
                {
                    "event_name": "add_payment_info",
                    "classification": "recommended_ecommerce",
                    "event_summary": "Official GA4 event.",
                    "parameter_bindings": [{"parameter_name": "currency"}],
                    "official_verification": {},
                }
            ],
            "parameters": [
                {
                    "parameter_name": "currency",
                    "classification": "ga4_ecommerce_parameter",
                    "description": "Reusable currency value.",
                    "official_verification": {},
                }
            ],
        }
        enriched = enrich_plan_official_semantics(plan, catalog, scenarios, parameters)
        self.assertNotIn("Official GA4", enriched["events"][0]["event_summary"])
        self.assertIn("Currency of the items", enriched["parameters"][0]["description"])
        self.assertIn("trigger_source_section", enriched["events"][0]["official_verification"])


if __name__ == "__main__":
    unittest.main()
