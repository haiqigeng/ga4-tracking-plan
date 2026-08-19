from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from access_profiles import _run_login_recipe, host_is_allowed, load_access_profiles
from discover_site_journeys_playwright import (
    journey_coverage_ledger,
    measurement_opportunity_hints,
    transition_measurement_opportunity_hints,
)
from discovery_contract import validate_discovery_report
from evidence_sanitization import sanitize_discovery_artifact
from interaction_probes import _frame_progression, build_probe_recipes, capability_families
from journey_evidence import positive_success_oracle, validate_interaction_run_evidence


class _EmptyLocator:
    def count(self) -> int:
        return 0


class _TextOnlyPage:
    url = "https://example.com/form"

    def locator(self, _selector: str) -> _EmptyLocator:
        return _EmptyLocator()


class _RedirectingLocator:
    def __init__(self, page: Any) -> None:
        self.page = page
        self.first = self

    def wait_for(self, **_kwargs: Any) -> None:
        return None

    def evaluate(self, _script: str) -> str:
        return "Continue"

    def click(self, **_kwargs: Any) -> None:
        self.page.url = "https://evil.example.test/phish"


class _RedirectingPage:
    def __init__(self) -> None:
        self.url = "https://portal.example.com/login"

    def locator(self, _selector: str) -> _RedirectingLocator:
        return _RedirectingLocator(self)

    def wait_for_timeout(self, _milliseconds: int) -> None:
        return None


class _Frame:
    def __init__(self, url: str) -> None:
        self.url = url


class _PageWithExternalFrame:
    def __init__(self) -> None:
        self.main_frame = _Frame("https://example.com/")
        self.frames = [self.main_frame, _Frame("https://third-party.example.test/form")]


class GatedJourneyEvidenceTests(unittest.TestCase):
    def test_generic_success_words_are_not_a_positive_oracle(self) -> None:
        page = _TextOnlyPage()
        self.assertIsNone(
            positive_success_oracle(
                page,
                before_url=page.url,
                form_action=page.url,
                responses=[],
            )
        )

    def test_completed_run_requires_a_recorded_positive_oracle(self) -> None:
        run = {
            "outcome": "completed",
            "evidence_state": "success_confirmed",
            "evidence_claims": [
                {
                    "claim": "success_confirmed",
                    "evidence_type": "positive_outcome_oracle",
                    "locator": "actions/0",
                    "evidence": {"oracle_type": "generic_body_text"},
                }
            ],
        }
        errors = validate_interaction_run_evidence(run)
        self.assertTrue(any("OBSERVED_WITHOUT_DIRECT_EVIDENCE" in error for error in errors))

    def test_discovery_1_4_rejects_false_completed_interaction_but_1_3_remains_compatible(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        run = {
            "recipe_id": "recipe_false_success",
            "journey_id": "lead_generation",
            "variant_id": "lead_false_success",
            "start_url": "https://example.com/form",
            "outcome": "completed",
            "actions": [{"status": "completed"}],
            "evidence_claims": [],
        }
        report["automatic_interaction_runs"] = [run]
        report["discovery_version"] = "1.4.0"
        report["run_id"] = "run_" + "a" * 32
        errors = validate_discovery_report(report)
        self.assertTrue(any("success_confirmed" in error or "OBSERVED_WITHOUT_DIRECT_EVIDENCE" in error for error in errors))

        report["discovery_version"] = "1.3.0"
        self.assertEqual(validate_discovery_report(report), [])

    def test_discovery_1_4_requires_rendered_artifacts_for_usable_pages(self) -> None:
        report = json.loads((ROOT / "references" / "example-discovery-report.json").read_text(encoding="utf-8"))
        report["discovery_version"] = "1.4.0"
        report["run_id"] = "run_" + "a" * 32
        report["interaction_probe_runs"] = []
        report["access_profile_runs"] = []
        report["side_effect_log"] = []
        report["pages_sampled"][0].pop("rendered_structure_sha256", None)
        errors = validate_discovery_report(report)
        self.assertTrue(any("rendered_structure_sha256" in error for error in errors))

    def test_plain_200_form_response_is_submission_evidence_not_success(self) -> None:
        page = _TextOnlyPage()
        self.assertIsNone(
            positive_success_oracle(
                page,
                before_url=page.url,
                form_action="https://example.com/submit",
                responses=[{"status": 200, "method": "POST", "path": "/submit"}],
            )
        )

    def test_access_profile_contract_rejects_inline_secrets_and_duplicate_roles(self) -> None:
        valid_profile = {
            "profile_id": "member",
            "role": "member",
            "entry_urls": ["https://portal.example.com/dashboard"],
            "allowed_hosts": ["portal.example.com", "*.sso.example.com"],
            "access_method": "login_recipe",
            "login_url": "https://portal.example.com/login",
            "login_recipe": [
                {
                    "action": "fill",
                    "selector": "#email",
                    "value_source": "environment",
                    "environment_name": "GA4_TEST_EMAIL",
                }
            ],
            "success_predicate": {"selector_visible": "[data-authenticated='true']"},
            "session_disposition": "discard_after_run",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "access.json"
            inline_secret = {"access_profiles_version": "1.0.0", "profiles": [{**valid_profile, "password": "secret"}]}
            path.write_text(json.dumps(inline_secret), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "password"):
                load_access_profiles(path)
            duplicated = {"access_profiles_version": "1.0.0", "profiles": [valid_profile, valid_profile]}
            path.write_text(json.dumps(duplicated), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate profile_id"):
                load_access_profiles(path)

    def test_allowed_host_wildcard_does_not_authorise_the_apex_or_lookalikes(self) -> None:
        allowed = ("*.sso.example.com",)
        self.assertTrue(host_is_allowed("login.sso.example.com", allowed))
        self.assertFalse(host_is_allowed("sso.example.com", allowed))
        self.assertFalse(host_is_allowed("login.sso.example.com.evil.test", allowed))

    def test_login_recipe_stops_after_an_unallowlisted_redirect(self) -> None:
        profile = {
            "allowed_hosts": ["portal.example.com"],
            "login_recipe": [{"action": "click", "selector": "#continue"}],
            "consequential_action_patterns": [],
        }
        trace = _run_login_recipe(_RedirectingPage(), profile, timeout_ms=1000)
        self.assertEqual(trace[-1]["status"], "blocked")
        self.assertIn("outside allowed_hosts", trace[-1]["error"])

    def test_probe_registry_is_bounded_by_family_and_state_not_control_count(self) -> None:
        page = {
            "url": "https://example.com/help",
            "template": "support_or_contact",
            "state_id": "entry",
            "interaction_capabilities": [
                {
                    "capability_id": "capability_faq_123",
                    "family": "faq_accordion",
                    "materiality": "candidate",
                    "evidence": ["accordions:12"],
                }
            ],
            "interactive_controls": [
                {"selector": f"#faq-{index}", "type": "button", "label": "FAQ question", "aria_expanded": "false"}
                for index in range(12)
            ],
        }
        recipes = build_probe_recipes([page])
        self.assertEqual(len(recipes), 1)
        self.assertIn("iframe_form", capability_families())
        self.assertIn("video_media", capability_families())

    def test_iframe_probe_refuses_an_unallowlisted_embedded_form(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside allowed_hosts"):
            _frame_progression(
                _PageWithExternalFrame(),
                {"frame_url": "https://third-party.example.test/form"},
                timeout_ms=1000,
                allowed_url=lambda value: value.startswith("https://example.com/"),
            )

    def test_candidate_probe_cannot_downgrade_an_observed_material_journey(self) -> None:
        url = "https://example.com/products"
        pages = [
            {
                "url": url,
                "template": "listing",
                "access_profile_id": "public",
                "role": "public",
                "state_id": "entry",
                "forms": [],
                "interactive_controls": [{"type": "select"}],
            }
        ]
        probe_runs = [
            {
                "probe_id": "probe_filter_fixture",
                "family": "filter_sort",
                "materiality": "candidate",
                "start_url": url,
                "template": "listing",
                "access_profile_id": "public",
                "role": "public",
                "state_id": "entry",
                "outcome": "partial",
                "evidence_state": "inventory_observed",
            }
        ]
        ledger = journey_coverage_ledger(
            pages,
            [],
            [],
            [],
            "https://example.com/",
            probe_runs=probe_runs,
        )
        listing = next(item for item in ledger if item["journey_id"] == "product_listing")
        self.assertEqual(listing["status"], "observed")
        self.assertTrue(listing["variant_coverage"][0]["material"])

    def test_candidate_probe_state_is_non_material_and_does_not_create_a_gap(self) -> None:
        url = "https://example.com/"
        pages = [
            {
                "url": url,
                "template": "homepage",
                "access_profile_id": "public",
                "role": "public",
                "state_id": "entry",
                "forms": [],
                "interactive_controls": [{"type": "link"}],
            }
        ]
        probe_runs = [
            {
                "probe_id": "probe_navigation_fixture",
                "family": "navigation_surface",
                "materiality": "candidate",
                "start_url": url,
                "template": "homepage",
                "access_profile_id": "public",
                "role": "public",
                "state_id": "entry",
                "state_id_after": "state_navigation_fixture",
                "outcome": "partial",
                "evidence_state": "inventory_observed",
            }
        ]
        ledger = journey_coverage_ledger(
            pages,
            [],
            [],
            [],
            url,
            probe_runs=probe_runs,
        )
        homepage = next(item for item in ledger if item["journey_id"] == "homepage_discovery")
        self.assertEqual(homepage["status"], "observed")
        self.assertEqual(
            sorted(item["material"] for item in homepage["variant_coverage"]),
            [False, True],
        )

    def test_saved_discovery_evidence_redacts_secrets_and_hashes_query_values(self) -> None:
        sanitized = sanitize_discovery_artifact(
            {
                "url": "https://portal.example.com/service?account=12345&tab=requests#private",
                "email": "real.person@example.com",
                "label": "Call +33 6 12 34 56 78",
                "cookies": [{"name": "session", "value": "secret"}],
                "rendered_structure_sha256": "a" * 64,
            }
        )
        self.assertNotIn("12345", sanitized["url"])
        self.assertIn("account=sha256_", sanitized["url"])
        self.assertNotIn("#private", sanitized["url"])
        self.assertEqual(sanitized["email"], "[redacted]")
        self.assertEqual(sanitized["label"], "Call [redacted_phone]")
        self.assertNotIn("cookies", sanitized)
        self.assertEqual(sanitized["rendered_structure_sha256"], "a" * 64)

    def test_a_new_family_revealed_after_a_state_change_becomes_an_analyst_decision(self) -> None:
        hints = transition_measurement_opportunity_hints(
            [
                {
                    "probe_id": "probe_modal_example",
                    "family": "modal_dialog",
                    "template": "support_or_contact",
                    "start_url": "https://example.com/support",
                    "access_profile_id": "public",
                    "role": "public",
                    "state_id_after": "state_modal_example",
                    "detected_families_before": ["modal_dialog"],
                    "rescan": {
                        "interaction_families": ["modal_dialog", "iframe_form"],
                        "rescan_sha256": "b" * 64,
                    },
                }
            ]
        )
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["hint_key"], "revealed_iframe_form")
        self.assertEqual(hints[0]["evidence_structure_hashes"], ["b" * 64])

    def test_every_registered_detected_family_creates_an_analyst_disposition_hint(self) -> None:
        pages = [
            {
                "url": f"https://example.com/{family}",
                "template": "content_or_other",
                "rendered_structure_sha256": f"{index + 1:064x}",
                "interaction_capabilities": [
                    {
                        "capability_id": f"capability_{family}_{index}",
                        "family": family,
                        "category": "interaction",
                        "materiality": "candidate",
                        "reason": "Fixture capability.",
                        "evidence": ["fixture"],
                    }
                ],
            }
            for index, family in enumerate(capability_families())
        ]
        hinted_capabilities = {
            capability_id
            for hint in measurement_opportunity_hints(pages)
            for capability_id in hint.get("capability_ids", [])
        }
        expected = {
            f"capability_{family}_{index}"
            for index, family in enumerate(capability_families())
        }
        self.assertEqual(hinted_capabilities, expected)


if __name__ == "__main__":
    unittest.main()
