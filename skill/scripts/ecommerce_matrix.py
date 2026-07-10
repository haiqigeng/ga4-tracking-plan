from __future__ import annotations

import json
from typing import Any

ECOMMERCE_GROUP_BY_EVENT = {
    "view_promotion": "Ecommerce promotions",
    "select_promotion": "Ecommerce promotions",
    "view_item_list": "Ecommerce product lists",
    "select_item": "Ecommerce product lists",
    "view_item": "Ecommerce product detail",
    "add_to_cart": "Ecommerce cart",
    "remove_from_cart": "Ecommerce cart",
    "view_cart": "Ecommerce cart",
    "begin_checkout": "Ecommerce checkout",
    "add_shipping_info": "Ecommerce checkout",
    "add_payment_info": "Ecommerce checkout",
    "purchase": "Ecommerce transactions",
    "refund": "Ecommerce transactions",
}

ECOMMERCE_GROUP_ORDER = [
    "Ecommerce promotions",
    "Ecommerce product lists",
    "Ecommerce product detail",
    "Ecommerce cart",
    "Ecommerce checkout",
    "Ecommerce transactions",
    "Ecommerce other",
]

COMMON_ITEM_PARAMETERS = [
    "items[].item_id",
    "items[].item_name",
    "items[].affiliation",
    "items[].coupon",
    "items[].discount",
    "items[].index",
    "items[].item_brand",
    "items[].item_category",
    "items[].item_category2",
    "items[].item_category3",
    "items[].item_category4",
    "items[].item_category5",
    "items[].item_list_id",
    "items[].item_list_name",
    "items[].item_variant",
    "items[].location_id",
    "items[].price",
    "items[].quantity",
]

PROMOTION_ITEM_PARAMETERS = [
    "items[].creative_name",
    "items[].creative_slot",
    "items[].promotion_id",
    "items[].promotion_name",
]

OFFICIAL_ITEM_PARAMETERS = set(COMMON_ITEM_PARAMETERS) | set(PROMOTION_ITEM_PARAMETERS)

ECOMMERCE_PARAMETERS_BY_GROUP = {
    "Ecommerce promotions": [
        "currency",
        "promotion_id",
        "promotion_name",
        "creative_name",
        "creative_slot",
        "items",
        *COMMON_ITEM_PARAMETERS,
        *PROMOTION_ITEM_PARAMETERS,
    ],
    "Ecommerce product lists": [
        "currency",
        "item_list_id",
        "item_list_name",
        "items",
        *COMMON_ITEM_PARAMETERS,
    ],
    "Ecommerce product detail": [
        "currency",
        "value",
        "items",
        *COMMON_ITEM_PARAMETERS,
    ],
    "Ecommerce cart": [
        "currency",
        "value",
        "items",
        *COMMON_ITEM_PARAMETERS,
    ],
    "Ecommerce checkout": [
        "currency",
        "value",
        "coupon",
        "shipping_tier",
        "payment_type",
        "items",
        *COMMON_ITEM_PARAMETERS,
    ],
    "Ecommerce transactions": [
        "transaction_id",
        "currency",
        "value",
        "coupon",
        "shipping",
        "tax",
        "items",
        *COMMON_ITEM_PARAMETERS,
    ],
    "Ecommerce other": [
        "currency",
        "value",
        "items",
        *COMMON_ITEM_PARAMETERS,
    ],
}

ECOMMERCE_PROFILE_BY_EVENT = {
    "view_promotion": "promotion_profile",
    "select_promotion": "promotion_profile",
    "view_item_list": "list_profile",
    "select_item": "list_profile",
    "view_item": "item_detail_profile",
    "add_to_cart": "cart_profile",
    "remove_from_cart": "cart_profile",
    "view_cart": "cart_profile",
    "begin_checkout": "checkout_profile",
    "add_shipping_info": "checkout_profile",
    "add_payment_info": "checkout_profile",
    "purchase": "transaction_profile",
    "refund": "refund_profile",
}

ECOMMERCE_PARAMETERS_BY_PROFILE = {
    "promotion_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce promotions"],
    "list_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce product lists"],
    "item_detail_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce product detail"],
    "cart_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce cart"],
    "checkout_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce checkout"],
    "transaction_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce transactions"],
    "refund_profile": ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce transactions"],
}

EVENT_PARAMETERS_BY_EVENT = {
    "view_promotion": {"currency", "promotion_id", "promotion_name", "creative_name", "creative_slot", "items"},
    "select_promotion": {"currency", "promotion_id", "promotion_name", "creative_name", "creative_slot", "items"},
    "view_item_list": {"currency", "item_list_id", "item_list_name", "items"},
    "select_item": {"currency", "item_list_id", "item_list_name", "items"},
    "view_item": {"currency", "value", "items"},
    "add_to_cart": {"currency", "value", "items"},
    "remove_from_cart": {"currency", "value", "items"},
    "view_cart": {"currency", "value", "items"},
    "begin_checkout": {"currency", "value", "coupon", "items"},
    "add_shipping_info": {"currency", "value", "coupon", "shipping_tier", "items"},
    "add_payment_info": {"currency", "value", "coupon", "payment_type", "items"},
    "purchase": {"transaction_id", "currency", "value", "coupon", "shipping", "tax", "items"},
    "refund": {"transaction_id", "currency", "value", "coupon", "shipping", "tax", "items"},
}

OFFICIAL_EVENT_PARAMETERS = {
    parameter
    for parameters in EVENT_PARAMETERS_BY_EVENT.values()
    for parameter in parameters
}

PARAMETER_TYPES = {
    "currency": "string",
    "value": "number",
    "transaction_id": "string",
    "coupon": "string",
    "shipping": "number",
    "tax": "number",
    "customer_type": "string",
    "payment_type": "string",
    "shipping_tier": "string",
    "promotion_id": "string",
    "promotion_name": "string",
    "creative_name": "string",
    "creative_slot": "string",
    "item_list_id": "string",
    "item_list_name": "string",
    "items": "array",
    "entry_point": "string",
    "items[].item_id": "string",
    "items[].item_name": "string",
    "items[].affiliation": "string",
    "items[].coupon": "string",
    "items[].discount": "number",
    "items[].index": "integer",
    "items[].item_brand": "string",
    "items[].item_category": "string",
    "items[].item_category2": "string",
    "items[].item_category3": "string",
    "items[].item_category4": "string",
    "items[].item_category5": "string",
    "items[].item_list_id": "string",
    "items[].item_list_name": "string",
    "items[].item_variant": "string",
    "items[].location_id": "string",
    "items[].price": "number",
    "items[].quantity": "number",
    "items[].creative_name": "string",
    "items[].creative_slot": "string",
    "items[].promotion_id": "string",
    "items[].promotion_name": "string",
}

ITEM_FALLBACK_TO_EVENT_LEVEL = {
    "items[].item_list_id": "item_list_id",
    "items[].item_list_name": "item_list_name",
    "items[].creative_name": "creative_name",
    "items[].creative_slot": "creative_slot",
    "items[].promotion_id": "promotion_id",
    "items[].promotion_name": "promotion_name",
}

EVENT_ITEM_FALLBACK_NOTE = (
    "Use event-level when every item shares the same value; item-level values override event-level values."
)


def compact_json(value: Any) -> str:
    if value in (None, "", []):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def join_values(values: list[Any] | None) -> str:
    if not values:
        return ""
    return " | ".join(str(value) for value in values)


def ecommerce_group(event_name: str) -> str:
    return ECOMMERCE_GROUP_BY_EVENT.get(event_name, "Ecommerce other")


def event_family(event: dict[str, Any]) -> str:
    if event.get("classification") == "recommended_ecommerce":
        return ecommerce_group(str(event.get("event_name", "")))
    return "Interactions"


def is_ecommerce_event(event: dict[str, Any]) -> bool:
    return event.get("classification") == "recommended_ecommerce"


def parameter_type(parameter: str) -> str:
    if parameter in PARAMETER_TYPES:
        return PARAMETER_TYPES[parameter]
    if parameter.startswith("items[]."):
        return "string"
    return "string"


def parameter_scope(parameter: str) -> str:
    if parameter.startswith("items[]."):
        return "item"
    if parameter == "items":
        return "event"
    return "event"


def scope_rule(parameter: str) -> str:
    if parameter in {"item_list_id", "item_list_name"}:
        return "Prefer event-level for homogeneous product lists; item-level list values override event-level values."
    if parameter in {"promotion_id", "promotion_name", "creative_name", "creative_slot"}:
        return "Prefer event-level when all promoted items share the same promotion; item-level promotion values override event-level values."
    if parameter in ITEM_FALLBACK_TO_EVENT_LEVEL:
        return EVENT_ITEM_FALLBACK_NOTE
    if parameter in {"coupon", "items[].coupon"}:
        return "Event-level coupon and item-level coupon are independent; use item-level coupon for item-specific discounts."
    if parameter == "currency":
        return "Event-scoped. Required when value is sent."
    if parameter == "value":
        return "Event-scoped monetary value; set to sum of price * quantity for relevant items, excluding shipping and tax."
    if parameter in {"items[].affiliation", "items[].location_id"}:
        return "Item-scoped only."
    if parameter == "items[].quantity":
        return "Item-scoped. GA4 defaults quantity to 1 if omitted, but tracking plans should show the intended quantity."
    if parameter.startswith("items[]."):
        if parameter in OFFICIAL_ITEM_PARAMETERS:
            return "Official item-scoped ecommerce parameter."
        return "Custom item-scoped parameter. Not an official GA4 ecommerce item parameter; register an item-scoped custom dimension if it is needed in GA4 reports."
    return ""


def ordered_parameters_for_events(events: list[dict[str, Any]]) -> list[str]:
    if events and all(is_ecommerce_event(event) for event in events):
        profile = None
        if len(events) == 1:
            event_profile = events[0].get("parameter_profile", {})
            if isinstance(event_profile, dict):
                profile = event_profile.get("profile_id")
        if profile in ECOMMERCE_PARAMETERS_BY_PROFILE:
            ordered = list(ECOMMERCE_PARAMETERS_BY_PROFILE[profile])
        else:
            group = ecommerce_group(str(events[0].get("event_name", "")))
            ordered = list(ECOMMERCE_PARAMETERS_BY_GROUP.get(group, ECOMMERCE_PARAMETERS_BY_GROUP["Ecommerce other"]))
    else:
        ordered = []

    for event in events:
        for parameter in event.get("parameters", []):
            if parameter not in ordered:
                ordered.append(parameter)
    return ordered


def event_order_key(event: dict[str, Any]) -> tuple[int, str]:
    family = event_family(event)
    family_rank = ECOMMERCE_GROUP_ORDER.index(family) if family in ECOMMERCE_GROUP_ORDER else len(ECOMMERCE_GROUP_ORDER)
    return family_rank, str(event.get("event_name", ""))


def nested_value(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def event_level_value(event: dict[str, Any], parameter: str) -> Any:
    payload = event.get("ga4_payload", {})
    params = payload.get("parameters", {}) if isinstance(payload.get("parameters"), dict) else {}
    if parameter in params:
        return params[parameter]
    push = event.get("data_layer", {}).get("push", {})
    return nested_value(push, f"ecommerce.{parameter}") or nested_value(push, f"event_data.{parameter}")


def item_values(event: dict[str, Any], parameter: str) -> list[Any]:
    key = parameter.split(".", 1)[1]
    payload_items = event.get("ga4_payload", {}).get("items", [])
    values = [item.get(key) for item in payload_items if isinstance(item, dict) and item.get(key) not in (None, "")]
    if values:
        return values

    push_items = nested_value(event.get("data_layer", {}).get("push", {}), "ecommerce.items")
    if isinstance(push_items, list):
        return [item.get(key) for item in push_items if isinstance(item, dict) and item.get(key) not in (None, "")]
    return []


def ecommerce_parameter_applicability(event: dict[str, Any], parameter: str) -> str:
    event_name = str(event.get("event_name", ""))
    if not is_ecommerce_event(event):
        return "send" if parameter in event.get("parameters", []) else "not_applicable"
    if parameter.startswith("items[]."):
        if parameter in ITEM_FALLBACK_TO_EVENT_LEVEL:
            counterpart = ITEM_FALLBACK_TO_EVENT_LEVEL[parameter]
            if event_level_value(event, counterpart) not in (None, ""):
                return "event_level_used"
        if parameter == "items[].quantity":
            return "send"
        if parameter in PROMOTION_ITEM_PARAMETERS and event_name not in {"view_promotion", "select_promotion"}:
            return "not_applicable"
        if parameter in COMMON_ITEM_PARAMETERS or parameter in PROMOTION_ITEM_PARAMETERS:
            return "send"
        return "send" if parameter in event.get("parameters", []) else "not_applicable"

    if parameter in EVENT_PARAMETERS_BY_EVENT.get(event_name, set()):
        return "send"
    if parameter in event.get("parameters", []):
        return "send"
    return "not_applicable"


def parameter_matrix_value(event: dict[str, Any], parameter: str) -> str:
    if parameter == "event":
        return str(event.get("data_layer", {}).get("event_key") or event.get("event_name") or "")

    if parameter == "items":
        items = event.get("ga4_payload", {}).get("items", [])
        return compact_json(items) if items else "Required when ecommerce context is sent"

    if parameter.startswith("items[]."):
        values = item_values(event, parameter)
        if values:
            return join_values(values)
        if parameter in ITEM_FALLBACK_TO_EVENT_LEVEL:
            counterpart = ITEM_FALLBACK_TO_EVENT_LEVEL[parameter]
            fallback = event_level_value(event, counterpart)
            if fallback not in (None, ""):
                return f"event-level {counterpart}: {compact_json(fallback)}"
        if parameter == "items[].quantity" and is_ecommerce_event(event):
            return "1"
        applicability = ecommerce_parameter_applicability(event, parameter)
        return "not_applicable" if applicability == "not_applicable" else "not_available"

    value = event_level_value(event, parameter)
    if value not in (None, ""):
        return compact_json(value)

    if is_ecommerce_event(event):
        applicability = ecommerce_parameter_applicability(event, parameter)
        return "not_applicable" if applicability == "not_applicable" else "not_available"
    return "-"


def parameter_availability(event: dict[str, Any], parameter: str) -> str:
    value = parameter_matrix_value(event, parameter)
    if value == "not_applicable":
        return "not_applicable"
    if value == "not_available":
        return "not_available"
    if value.startswith("event-level "):
        return "event_level_used"
    if parameter == "items[].quantity" and value == "1" and not item_values(event, parameter):
        return "send_default_quantity"
    return "send"
