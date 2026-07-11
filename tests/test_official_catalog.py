from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from official_ga4_catalog import catalog_signature, parse_catalog_html  # noqa: E402


class OfficialCatalogTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
