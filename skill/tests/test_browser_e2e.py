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
GATED_FIXTURE = ROOT / "tests" / "fixtures" / "gated-site"
DISCOVERY = ROOT / "scripts" / "discover_site_journeys_playwright.py"

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from build_analysis_context_seed import build_analysis_context_seed
from validate_analysis_context import validate_analysis_context


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
                "--seed-url",
                f"{root_url}/contact/modal.html",
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
        coverage_by_journey = {
            item["journey_id"]: item["status"]
            for item in report["journey_coverage_ledger"]
        }
        self.assertEqual(coverage_by_journey["homepage_discovery"], "observed")
        self.assertEqual(coverage_by_journey["product_listing"], "observed")
        self.assertEqual(coverage_by_journey["support_contact"], "observed")
        finite_labels = {item["source_label"] for item in report["finite_value_candidates"]}
        self.assertIn("sort_type", finite_labels)
        self.assertIn("item_color", finite_labels)
        standard_page = next(
            page
            for page in report["pages_sampled"]
            if page["url"].endswith("/quote/standard.html")
        )
        fixture_push = next(
            push
            for push in standard_page["measurement_evidence"]["data_layer_pushes"]
            if isinstance(push, dict) and push.get("event") == "fixture_context"
        )
        self.assertEqual(fixture_push["event_data"]["email"], "[redacted]")
        self.assertEqual(fixture_push["event_data"]["billingEmail"], "[redacted]")
        self.assertEqual(fixture_push["event_data"]["token"], "[redacted]")
        self.assertEqual(fixture_push["event_data"]["userProfile"]["phoneNumber"], "[redacted]")
        self.assertEqual(fixture_push["event_data"]["project_type"], "window")
        modal_runs = [
            item
            for item in report["automatic_interaction_runs"]
            if item["start_url"].endswith("/contact/modal.html")
        ]
        self.assertEqual(len(modal_runs), 1)
        self.assertEqual(modal_runs[0]["outcome"], "completed")
        self.assertEqual(modal_runs[0]["actions"][0]["action_type"], "reveal_form")
        self.assertEqual(modal_runs[0]["actions"][0]["control_selector"], "#open-support")
        modal_page = next(
            page
            for page in report["pages_sampled"]
            if page["url"].endswith("/contact/modal.html")
        )
        support_form = next(form for form in modal_page["forms"] if form["id"] == "support-form")
        newsletter_form = next(form for form in modal_page["forms"] if form["id"] == "global-newsletter")
        self.assertEqual(support_form["reveal_control"]["selector"], "#open-support")
        self.assertIsNone(newsletter_form["reveal_control"])

    def test_access_profiles_trigger_isolated_role_aware_rediscovery(self) -> None:
        handler = partial(QuietHandler, directory=str(GATED_FIXTURE))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        root_url = f"http://127.0.0.1:{server.server_port}"
        profiles = {
            "access_profiles_version": "1.0.0",
            "profiles": [
                {
                    "profile_id": role,
                    "role": role,
                    "entry_urls": [f"{root_url}/dashboard.html"],
                    "allowed_hosts": ["127.0.0.1"],
                    "access_method": "login_recipe",
                    "login_url": f"{root_url}/login.html",
                    "login_recipe": [
                        {"action": "select", "selector": "#role", "select_value": role},
                        {
                            "action": "fill",
                            "selector": "#email",
                            "value_source": "synthetic",
                            "value_kind": "email",
                        },
                        {"action": "click", "selector": "#login"},
                    ],
                    "success_predicate": {"selector_visible": "[data-authenticated='true']"},
                    "consequential_action_patterns": ["logout"],
                    "session_disposition": "discard_after_run",
                }
                for role in ("member", "partner")
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            output = directory_path / "discovery.json"
            access_path = directory_path / "access-profiles.json"
            access_path.write_text(json.dumps(profiles), encoding="utf-8")
            command = [
                sys.executable,
                "-B",
                str(DISCOVERY),
                root_url,
                "--output",
                str(output),
                "--access-profiles",
                str(access_path),
                "--browser",
                "chromium",
                "--limit",
                "8",
                "--max-rounds",
                "2",
                "--sitemap-limit",
                "10",
                "--interaction-limit",
                "4",
                "--probe-limit",
                "10",
                "--delay-ms",
                "0",
                "--timeout-ms",
                "5000",
            ]
            try:
                process = subprocess.run(
                    command,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            if process.returncode not in {0, 1} and any(
                token in f"{process.stdout}\n{process.stderr}"
                for token in ("Executable doesn't exist", "browser build", "Playwright is required")
            ):
                if os.environ.get("GA4_REQUIRE_BROWSER_E2E") == "1":
                    self.fail(process.stderr or process.stdout)
                self.skipTest("Playwright Chromium is not installed in this local runtime.")
            self.assertIn(process.returncode, {0, 1}, process.stderr or process.stdout)
            self.assertTrue(output.exists(), process.stderr or process.stdout)
            report_text = output.read_text(encoding="utf-8")
            report = json.loads(report_text)
            context = build_analysis_context_seed(report, output)

        self.assertEqual(
            {item["status"] for item in report["access_profile_runs"]},
            {"authenticated_discovery_completed"},
        )
        profile_pages = [
            item for item in report["pages_sampled"] if item.get("access_profile_id") != "public"
        ]
        self.assertEqual({item["role"] for item in profile_pages}, {"member", "partner"})
        self.assertTrue(
            any(item["url"].endswith("/member-service.html") and item["role"] == "member" for item in profile_pages)
        )
        self.assertTrue(
            any(item["url"].endswith("/partner-service.html") and item["role"] == "partner" for item in profile_pages)
        )
        self.assertTrue(
            any(item["family"] == "iframe_form" for item in report["interaction_probe_runs"])
        )
        self.assertNotIn("ga4-synthetic-access@example.com", report_text)
        self.assertNotIn('"cookies":', report_text.casefold())
        self.assertNotIn('"origins":', report_text.casefold())
        self.assertEqual(context["context_version"], "1.2.0")
        self.assertEqual(validate_analysis_context(context), [])


if __name__ == "__main__":
    unittest.main()
