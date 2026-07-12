from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from ecommerce_matrix import (  # noqa: E402
    ECOMMERCE_GROUP_ORDER,
    compact_json,
    ecommerce_group,
    ecommerce_parameter_applicability,
    event_family,
    event_level_value,
    event_order_key,
    is_ecommerce_event,
    item_values,
    join_values,
    nested_value,
    ordered_parameters_for_events,
    parameter_availability,
    parameter_matrix_value,
    parameter_scope,
    parameter_type,
    scope_rule,
)


def event(
    name: str = "view_item",
    *,
    classification: str = "recommended_ecommerce",
    parameters: list[str] | None = None,
    ga4_parameters: dict | None = None,
    items: list[dict] | None = None,
    push: dict | None = None,
    profile: str | None = None,
) -> dict:
    value = {
        "event_name": name,
        "classification": classification,
        "parameters": parameters or [],
        "ga4_payload": {"parameters": ga4_parameters or {}, "items": items or []},
        "data_layer": {"event_key": name, "push": push or {}},
    }
    if profile:
        value["parameter_profile"] = {"profile_id": profile}
    return value


class EcommerceMatrixTests(unittest.TestCase):
    def test_basic_value_and_family_helpers(self) -> None:
        self.assertEqual(compact_json(None), "")
        self.assertEqual(compact_json("value"), "value")
        self.assertEqual(compact_json({"a": 1}), '{"a":1}')
        self.assertEqual(join_values(None), "")
        self.assertEqual(join_values(["one", "two"]), "one | two")
        self.assertEqual(ecommerce_group("purchase"), "Ecommerce transactions")
        self.assertEqual(ecommerce_group("unknown"), "Ecommerce other")
        self.assertEqual(event_family(event()), "Ecommerce product detail")
        self.assertEqual(event_family(event(classification="custom")), "Interactions")
        self.assertTrue(is_ecommerce_event(event()))
        self.assertFalse(is_ecommerce_event(event(classification="custom")))

    def test_parameter_metadata_helpers_cover_official_and_custom_paths(self) -> None:
        self.assertEqual(parameter_type("value"), "number")
        self.assertEqual(parameter_type("items[].custom_flag"), "string")
        self.assertEqual(parameter_type("custom_flag"), "string")
        self.assertEqual(parameter_scope("items[].item_id"), "item")
        self.assertEqual(parameter_scope("items"), "event")
        self.assertEqual(parameter_scope("currency"), "event")

        expected_fragments = {
            "item_list_id": "homogeneous product lists",
            "promotion_id": "all promoted items",
            "items[].item_list_id": "item-level values override",
            "coupon": "independent",
            "currency": "Required when value",
            "value": "price * quantity",
            "items[].affiliation": "Item-scoped only",
            "items[].quantity": "defaults quantity to 1",
            "items[].item_brand": "Official item-scoped",
            "items[].custom_flag": "Custom item-scoped",
        }
        for parameter, fragment in expected_fragments.items():
            with self.subTest(parameter=parameter):
                self.assertIn(fragment, scope_rule(parameter))
        self.assertEqual(scope_rule("custom_event_parameter"), "")

    def test_ordering_uses_profiles_groups_and_appended_custom_parameters(self) -> None:
        profiled = event(parameters=["custom_stock_status"], profile="item_detail_profile")
        ordered = ordered_parameters_for_events([profiled])
        self.assertEqual(ordered[0], "currency")
        self.assertIn("items[].item_id", ordered)
        self.assertEqual(ordered[-1], "custom_stock_status")

        cart_events = [event("add_to_cart"), event("view_cart", parameters=["entry_point"])]
        grouped = ordered_parameters_for_events(cart_events)
        self.assertIn("items", grouped)
        self.assertEqual(grouped[-1], "entry_point")

        interaction = event("header_click", classification="custom", parameters=["link_name", "link_url"])
        self.assertEqual(ordered_parameters_for_events([interaction]), ["link_name", "link_url"])
        self.assertLess(event_order_key(event("view_item"))[0], len(ECOMMERCE_GROUP_ORDER))
        self.assertEqual(event_order_key(interaction), (len(ECOMMERCE_GROUP_ORDER), "header_click"))

    def test_nested_event_and_item_values_use_payload_then_datalayer(self) -> None:
        self.assertEqual(nested_value({"a": {"b": 2}}, "a.b"), 2)
        self.assertIsNone(nested_value({"a": {}}, "a.b"))
        payload_event = event(ga4_parameters={"currency": "EUR"}, items=[{"item_id": "SKU_1"}, {"item_id": "SKU_2"}])
        self.assertEqual(event_level_value(payload_event, "currency"), "EUR")
        self.assertEqual(item_values(payload_event, "items[].item_id"), ["SKU_1", "SKU_2"])

        push_event = event(
            ga4_parameters={},
            push={"ecommerce": {"value": 10, "items": [{"item_name": "Product"}]}, "event_data": {"entry_point": "header"}},
        )
        self.assertEqual(event_level_value(push_event, "value"), 10)
        self.assertEqual(event_level_value(push_event, "entry_point"), "header")
        self.assertEqual(item_values(push_event, "items[].item_name"), ["Product"])
        self.assertEqual(item_values(event(), "items[].item_id"), [])

    def test_applicability_covers_event_item_fallback_and_custom_parameters(self) -> None:
        interaction = event("header_click", classification="custom", parameters=["link_name"])
        self.assertEqual(ecommerce_parameter_applicability(interaction, "link_name"), "send")
        self.assertEqual(ecommerce_parameter_applicability(interaction, "currency"), "not_applicable")

        item_detail = event(parameters=["custom_item_flag"], ga4_parameters={"item_list_id": "related"})
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "items[].item_list_id"), "event_level_used")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "items[].quantity"), "send")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "items[].promotion_id"), "not_applicable")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "items[].item_brand"), "send")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "items[].custom_item_flag"), "not_applicable")
        item_detail["parameters"].append("items[].custom_item_flag")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "items[].custom_item_flag"), "send")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "currency"), "send")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "custom_item_flag"), "send")
        self.assertEqual(ecommerce_parameter_applicability(item_detail, "payment_type"), "not_applicable")

    def test_matrix_values_and_availability_cover_all_rendering_states(self) -> None:
        item_detail = event(
            parameters=["custom_missing"],
            ga4_parameters={"currency": "EUR", "item_list_id": "related"},
            items=[{"item_id": "SKU_1", "price": 12.5}],
        )
        self.assertEqual(parameter_matrix_value(item_detail, "event"), "view_item")
        self.assertIn("SKU_1", parameter_matrix_value(item_detail, "items"))
        self.assertEqual(parameter_matrix_value(item_detail, "items[].item_id"), "SKU_1")
        self.assertEqual(parameter_matrix_value(item_detail, "items[].item_list_id"), "event-level item_list_id: related")
        self.assertEqual(parameter_matrix_value(item_detail, "items[].quantity"), "1")
        self.assertEqual(parameter_matrix_value(item_detail, "items[].promotion_id"), "not_applicable")
        self.assertEqual(parameter_matrix_value(item_detail, "items[].custom_missing"), "not_applicable")
        self.assertEqual(parameter_matrix_value(item_detail, "currency"), "EUR")
        self.assertEqual(parameter_matrix_value(item_detail, "payment_type"), "not_applicable")
        self.assertEqual(parameter_matrix_value(item_detail, "custom_missing"), "not_available")

        empty = event()
        self.assertEqual(parameter_matrix_value(empty, "items"), "Required when ecommerce context is sent")
        interaction = event("header_click", classification="custom", parameters=["link_name"])
        self.assertEqual(parameter_matrix_value(interaction, "link_name"), "-")

        self.assertEqual(parameter_availability(item_detail, "items[].promotion_id"), "not_applicable")
        self.assertEqual(parameter_availability(item_detail, "custom_missing"), "not_available")
        self.assertEqual(parameter_availability(item_detail, "items[].item_list_id"), "event_level_used")
        self.assertEqual(parameter_availability(item_detail, "items[].quantity"), "send_default_quantity")
        self.assertEqual(parameter_availability(item_detail, "currency"), "send")


if __name__ == "__main__":
    unittest.main()
