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

import browser_environment  # noqa: E402
import discover_site_journeys_playwright as rendered_discovery  # noqa: E402
from discover_site_journeys_playwright import collect_rendered_page, launch_browser  # noqa: E402


class BrowserEnvironmentTests(unittest.TestCase):
    def test_browser_names_are_normalized_to_playwright_channels(self) -> None:
        self.assertEqual(browser_environment.normalize_browser("MSEdgeHTM"), "msedge")
        self.assertEqual(browser_environment.normalize_browser("ChromeHTML"), "chrome")
        self.assertEqual(browser_environment.normalize_browser("FirefoxURL"), "firefox")

    def test_eligible_default_edge_is_preferred(self) -> None:
        with (
            patch.object(browser_environment, "detect_default_browser", return_value=("msedge", "test association")),
            patch.object(browser_environment, "playwright_status", return_value=(True, "1.61.0", "")),
            patch.object(browser_environment, "installed_branded_channels", return_value={"msedge": "edge.exe"}),
            patch.object(browser_environment, "bundled_channels", return_value=({"chromium": "chromium.exe"}, "")),
        ):
            result = browser_environment.inspect_browser_environment()
        self.assertTrue(result["default_browser_eligible"])
        self.assertEqual(result["recommended_channel"], "msedge")

    def test_installed_branded_browser_precedes_bundled_fallback(self) -> None:
        with (
            patch.object(browser_environment, "detect_default_browser", return_value=("unknown", "unavailable")),
            patch.object(browser_environment, "playwright_status", return_value=(True, "1.61.0", "")),
            patch.object(browser_environment, "installed_branded_channels", return_value={"msedge": "edge.exe"}),
            patch.object(browser_environment, "bundled_channels", return_value=({"chromium": "chromium.exe"}, "")),
        ):
            result = browser_environment.inspect_browser_environment()
        self.assertEqual(result["recommended_channel"], "msedge")

    def test_auto_requires_an_eligible_browser(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No eligible Playwright browser"):
            browser_environment.resolve_browser_channel("auto", {"recommended_channel": ""})

    def test_msedge_launch_uses_branded_channel(self) -> None:
        class Chromium:
            def launch(self, **kwargs):
                return kwargs

        class Playwright:
            chromium = Chromium()

        self.assertEqual(launch_browser(Playwright(), "msedge", True), {"channel": "msedge", "headless": True})

    def test_each_supported_engine_uses_the_matching_browser_type(self) -> None:
        class BrowserType:
            def __init__(self, name):
                self.name = name

            def launch(self, **kwargs):
                return self.name, kwargs

        class Playwright:
            chromium = BrowserType("chromium")
            firefox = BrowserType("firefox")
            webkit = BrowserType("webkit")

        playwright = Playwright()
        self.assertEqual(launch_browser(playwright, "chromium", False), ("chromium", {"headless": False}))
        self.assertEqual(launch_browser(playwright, "firefox", True), ("firefox", {"headless": True}))
        self.assertEqual(launch_browser(playwright, "webkit", True), ("webkit", {"headless": True}))

    def test_real_preflight_has_a_supported_shape(self) -> None:
        result = browser_environment.inspect_browser_environment()
        self.assertIn(
            result["readiness"],
            {"ready", "playwright_python_missing", "playwright_import_failed", "playwright_runtime_failed", "eligible_browser_missing"},
        )
        self.assertIn("installed_channels", result)
        if result["recommended_channel"]:
            self.assertIn(result["recommended_channel"], browser_environment.SUPPORTED_CHANNELS)

    def test_rendered_page_collection_normalizes_signals(self) -> None:
        class Page:
            def goto(self, *args, **kwargs):
                return None

            def wait_for_load_state(self, *args, **kwargs):
                return None

            def eval_on_selector_all(self, selector, _script):
                if selector == "a[href]":
                    return [{"url": "https://example.com/product?utm_source=test", "text": " Product "}]
                if selector == "form":
                    return [{"action": "https://example.com/login", "method": "post", "id": "login", "name": ""}]
                return ["Buy now"]

        result = collect_rendered_page(Page(), "https://example.com/", "https://example.com/", 1000)
        self.assertEqual(result["links"][0]["url"], "https://example.com/product")
        self.assertEqual(result["buttons"], ["Buy now"])

    def test_rendered_discovery_reports_partial_coverage(self) -> None:
        pages = [
            {"url": "https://example.com/", "links": []},
            {"url": "https://example.com/account", "fetch_error": "blocked"},
        ]
        errors = [rendered_discovery.SourceError("playwright_crawl", pages[1]["url"], "blocked")]

        outcome, usable, notice = rendered_discovery.discovery_outcome(pages, errors)

        self.assertEqual((outcome, usable), ("partial", 1))
        self.assertIn("partial", notice.lower())

    def test_missing_playwright_is_reported(self) -> None:
        with patch.object(browser_environment.importlib.util, "find_spec", return_value=None):
            self.assertEqual(browser_environment.playwright_status(), (False, "not installed", ""))
            self.assertEqual(browser_environment.bundled_channels(), ({}, "Playwright Python is not installed."))

    def test_broken_playwright_import_is_not_reported_ready(self) -> None:
        with (
            patch.object(browser_environment, "detect_default_browser", return_value=("msedge", "test association")),
            patch.object(browser_environment, "playwright_status", return_value=(False, "1.61.0", "ImportError: broken greenlet")),
            patch.object(browser_environment, "installed_branded_channels", return_value={"msedge": "edge.exe"}),
            patch.object(browser_environment, "bundled_channels", return_value=({}, "ImportError: broken greenlet")),
        ):
            result = browser_environment.inspect_browser_environment()
        self.assertEqual(result["readiness"], "playwright_import_failed")
        self.assertIn("broken greenlet", result["playwright_probe_error"])
        with self.assertRaisesRegex(RuntimeError, "installed but unusable"):
            browser_environment.resolve_browser_channel("auto", result)

    def test_playwright_runtime_probe_failure_is_not_reported_ready(self) -> None:
        with (
            patch.object(browser_environment, "detect_default_browser", return_value=("msedge", "test association")),
            patch.object(browser_environment, "playwright_status", return_value=(True, "1.61.0", "")),
            patch.object(browser_environment, "installed_branded_channels", return_value={"msedge": "edge.exe"}),
            patch.object(browser_environment, "bundled_channels", return_value=({}, "RuntimeError: driver failed")),
        ):
            result = browser_environment.inspect_browser_environment()
        self.assertEqual(result["readiness"], "playwright_runtime_failed")

    def test_require_playwright_reports_non_import_errors(self) -> None:
        with patch.object(rendered_discovery, "load_playwright_sync_api", side_effect=OSError("missing runtime")):
            with self.assertRaisesRegex(SystemExit, "missing runtime"):
                rendered_discovery.require_playwright()

    def test_linux_default_browser_uses_xdg_settings(self) -> None:
        with (
            patch.object(browser_environment.platform, "system", return_value="Linux"),
            patch.object(browser_environment, "_command_default_browser", return_value=("firefox", "xdg-settings: firefox.desktop")) as command,
        ):
            result = browser_environment.detect_default_browser()
        self.assertEqual(result[0], "firefox")
        command.assert_called_once_with(["xdg-settings", "get", "default-web-browser"], "xdg-settings")

    def test_macos_default_browser_uses_launch_services(self) -> None:
        with (
            patch.object(browser_environment.platform, "system", return_value="Darwin"),
            patch.object(browser_environment, "_command_default_browser", return_value=("webkit", "LaunchServices: Safari")) as command,
        ):
            result = browser_environment.detect_default_browser()
        self.assertEqual(result[0], "webkit")
        self.assertEqual(command.call_args.args[1], "LaunchServices")

    def test_command_default_browser_parses_stdout(self) -> None:
        completed = browser_environment.subprocess.CompletedProcess(["browser"], 0, stdout="microsoft-edge.desktop\n", stderr="")
        with patch.object(browser_environment.subprocess, "run", return_value=completed):
            browser, source = browser_environment._command_default_browser(["browser"], "test command")
        self.assertEqual(browser, "msedge")
        self.assertIn("microsoft-edge.desktop", source)

    def test_rendered_discovery_main_records_selected_browser(self) -> None:
        class Page:
            pass

        class Context:
            def new_page(self):
                return Page()

            def close(self):
                return None

        class Browser:
            def new_context(self):
                return Context()

            def close(self):
                return None

        class Chromium:
            def launch(self, **kwargs):
                return Browser()

        class Playwright:
            chromium = Chromium()

        class Manager:
            def __enter__(self):
                return Playwright()

            def __exit__(self, _exc_type, _exc, _traceback):
                return False

        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "discovery.json"
            with (
                patch.object(rendered_discovery, "require_playwright", return_value=Manager),
                patch.object(
                    rendered_discovery,
                    "inspect_browser_environment",
                    return_value={"recommended_channel": "msedge", "default_browser": "msedge", "default_browser_eligible": True},
                ),
                patch.object(rendered_discovery, "collect_rendered_page", return_value={"url": "https://example.com/", "template": "homepage", "links": [], "forms": [], "buttons": []}),
                patch.object(sys, "argv", ["discover", "https://example.com/", "--output", str(output), "--limit", "1"]),
            ):
                with redirect_stdout(StringIO()):
                    self.assertEqual(rendered_discovery.main(), 0)
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["browser"]["selected_channel"], "msedge")


if __name__ == "__main__":
    unittest.main()
