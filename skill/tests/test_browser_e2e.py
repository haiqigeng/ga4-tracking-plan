from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "discovery-site"
DISCOVERY = ROOT / "scripts" / "discover_site_journeys_playwright.py"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


class BrowserDiscoveryEndToEndTests(unittest.TestCase):
    def test_rendered_discovery_covers_two_funnel_variants_and_finite_values(self) -> None:
        handler = partial(QuietHandler, directory=str(FIXTURE))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        root_url = f"http://127.0.0.1:{server.server_port}"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "discovery.json"
            command = [
                sys.executable,
                "-B",
                str(DISCOVERY),
                root_url,
                "--output",
                str(output),
                "--browser",
                "chromium",
                "--limit",
                "10",
                "--max-rounds",
                "2",
                "--sitemap-limit",
                "20",
                "--interaction-limit",
                "10",
                "--delay-ms",
                "0",
                "--seed-url",
                f"{root_url}/quote/standard.html",
                "--seed-url",
                f"{root_url}/landing/quote.html",
                "--seed-url",
                f"{root_url}/category/windows.html",
            ]
            try:
                process = subprocess.run(
                    command,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            if process.returncode != 0 and any(
                token in f"{process.stdout}\n{process.stderr}"
                for token in ("Executable doesn't exist", "browser build", "Playwright is required")
            ):
                if os.environ.get("GA4_REQUIRE_BROWSER_E2E") == "1":
                    self.fail(process.stderr or process.stdout)
                self.skipTest("Playwright Chromium is not installed in this local runtime.")
            self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
            report = json.loads(output.read_text(encoding="utf-8"))

        lead_runs = [
            item
            for item in report["automatic_interaction_runs"]
            if item["journey_id"] == "lead_generation"
        ]
        self.assertEqual(len(lead_runs), 2)
        self.assertEqual(len({item["variant_id"] for item in lead_runs}), 2)
        self.assertTrue(all(item["outcome"] == "completed" for item in lead_runs))
        lead_coverage = next(
            item
            for item in report["journey_coverage_ledger"]
            if item["journey_id"] == "lead_generation"
        )
        self.assertEqual(len(lead_coverage["variant_coverage"]), 2)
        self.assertTrue(all(item["status"] == "observed" for item in lead_coverage["variant_coverage"]))
        finite_labels = {item["source_label"] for item in report["finite_value_candidates"]}
        self.assertIn("sort_type", finite_labels)
        self.assertIn("item_color", finite_labels)


if __name__ == "__main__":
    unittest.main()
