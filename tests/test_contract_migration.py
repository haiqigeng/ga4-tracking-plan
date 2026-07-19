from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "maintenance" / "scripts"))
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from migrate_tracking_plan import migrate_datalayer_wrappers, migrate_parameters, migrate_plan  # noqa: E402
from validate_tracking_plan import validate_plan_data  # noqa: E402


class ContractMigrationTests(unittest.TestCase):
    def test_removed_v1_fields_do_not_survive(self) -> None:
        plan = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))
        legacy = copy.deepcopy(plan)
        legacy.update({"schema_version": "1.1.0", "analytics_platforms": ["ga4"], "qa_cases": []})
        legacy.pop("screenshot_capture", None)
        legacy["events"][0].update(
            {
                "primary_platform": "ga4",
                "platform_mappings": [],
                "qa": {},
                "ga4_payload": {"event_name": "page_view"},
                "parameter_profile": {"profile_id": "platform_native_profile"},
            }
        )
        migrated = migrate_plan(legacy)

        self.assertEqual(migrated["schema_version"], "3.0.0")
        self.assertNotIn("analytics_platforms", migrated)
        self.assertNotIn("qa_cases", migrated)
        self.assertNotIn("primary_platform", migrated["events"][0])
        self.assertNotIn("qa", migrated["events"][0])
        self.assertNotIn("ga4_payload", migrated["events"][0])
        self.assertNotIn("parameter_profile", migrated["events"][0])
        self.assertIn(migrated["events"][0]["access_context"], {"public", "authentication_flow", "authenticated_area"})
        self.assertIn("screenshot_coverage", migrated["events"][0])
        self.assertTrue(all("scenario_id" in row for row in migrated["screenshot_evidence"]))
        self.assertIn("screenshot_capture", migrated)
        self.assertEqual(migrated["screenshot_capture"]["playwright_mcp_attempt"]["status"], "not_recorded")
        self.assertIn("PLAYWRIGHT_MCP_ATTEMPT_MISSING", {issue.code for issue in validate_plan_data(migrated)})
        self.assertIn("page", migrated["events"][0]["data_layer"]["push"])
        self.assertNotIn("page_data", migrated["events"][0]["data_layer"]["push"])
        self.assertEqual(migrated["user_context"]["data_layer_object"], "user")
        self.assertIn("parameter_bindings", migrated["events"][0])
        self.assertNotIn("parameters", migrated["events"][0])
        self.assertIn("value_domain", migrated["parameters"][0])
        self.assertNotIn("allowed_values", migrated["parameters"][0])

        parameter_plan = {
            "language_policy": {"controlled_value_language": "fr"},
            "parameters": [
                {"parameter_name": "observed", "allowed_values": ["rouge"], "availability": "observed"},
                {"parameter_name": "confirmed", "allowed_values": ["standard"], "availability": "confirmed_available"},
                {"parameter_name": "proposed", "allowed_values": ["autre"], "availability": "to_confirm"},
                {"parameter_name": "rule", "allowed_values": [], "availability": "to_confirm"},
            ],
        }
        migrate_parameters(parameter_plan)
        self.assertEqual(
            [parameter["value_domain"]["mode"] for parameter in parameter_plan["parameters"]],
            ["observed_exhaustive", "client_confirmed", "proposed_taxonomy", "governed_rule"],
        )
        self.assertEqual(parameter_plan["parameters"][0]["value_domain"]["entries"][0]["language"], "fr")

        wrapper_plan = {
            "events": [
                {
                    "event_name": "page_view",
                    "parameter_bindings": [{"parameter_name": "page_data.template"}],
                    "data_layer": {
                        "push": {
                            "event": "page_view",
                            "page_data": {"template": "product", "site_language": "fr"},
                            "user_context": {"login_status": "connecte"},
                            "search_term": "robe",
                        },
                        "flush_keys": ["page_data", "user_context"],
                        "mapping_notes": "page_data and user_context",
                    },
                }
            ],
            "parameters": [
                {
                    "parameter_name": "page_data.template",
                    "official_verification": {},
                }
            ],
            "user_context": {
                "data_layer_object": "user_context",
                "ga4_user_id": {"source_path": "user_context.user_id"},
                "user_properties": [{"source_path": "user_context.login_status"}],
            },
        }
        migrate_datalayer_wrappers(wrapper_plan)
        migrated_push = wrapper_plan["events"][0]["data_layer"]["push"]
        self.assertEqual(migrated_push["page"], {"page_template": "product", "nav_language": "fr"})
        self.assertEqual(migrated_push["user"], {"login_status": "connecte"})
        self.assertEqual(migrated_push["event_data"], {"search_term": "robe"})
        self.assertEqual(wrapper_plan["events"][0]["data_layer"]["consent_timing"], "core_context_before_cmp_ready")
        self.assertEqual(wrapper_plan["events"][0]["parameter_bindings"][0]["parameter_name"], "page_template")
        self.assertEqual(wrapper_plan["parameters"][0]["parameter_name"], "page_template")
        self.assertEqual(wrapper_plan["user_context"]["ga4_user_id"]["source_path"], "user.user_id")


if __name__ == "__main__":
    unittest.main()
