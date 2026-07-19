from __future__ import annotations

from typing import Any

from tracking_plan_contract import event_parameter_names
from tracking_plan_validation_catalogs import MANUAL_COLLECTION_SOURCES
from tracking_plan_validation_model import Issue, add_issue

DATALAYER_WRAPPERS = ("page", "event_data", "ecommerce", "user")
DATALAYER_ROOT_KEYS = {"event", *DATALAYER_WRAPPERS}


def _check_push_shape(
    event: dict[str, Any],
    push: dict[str, Any],
    base: str,
    issues: list[Issue],
) -> None:
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    collection_source = str(event.get("collection_strategy", {}).get("collection_source", ""))
    manually_collected = classification not in {"automatic", "enhanced_measurement"} or collection_source in MANUAL_COLLECTION_SOURCES
    if manually_collected and push.get("event") != event_name:
        add_issue(issues, "error", "DATALAYER_TRIGGER_MISMATCH", f"{base}.data_layer.push.event", "A manual GTM dataLayer event must use the final GA4 event name as its top-level event string.")
    if not manually_collected and "event" in push:
        add_issue(issues, "error", "NATIVE_EVENT_MANUAL_PUSH", f"{base}.data_layer.push.event", "Do not add a Custom Event push for native automatic or enhanced-measurement collection. Push reusable context without event, or document a controlled manual collection strategy.")
    loose_keys = sorted(set(push).difference(DATALAYER_ROOT_KEYS))
    if loose_keys:
        add_issue(issues, "error", "DATALAYER_ROOT_FIELD_UNWRAPPED", f"{base}.data_layer.push", f"Place data under page, event_data, ecommerce, or user instead of loose root field(s): {', '.join(loose_keys)}.")
    for wrapper in DATALAYER_WRAPPERS:
        if wrapper in push and not isinstance(push.get(wrapper), dict):
            add_issue(issues, "error", "DATALAYER_WRAPPER_INVALID", f"{base}.data_layer.push.{wrapper}", f"The {wrapper} wrapper must be an object in the event push.")


def _selected_parameter_names(event: dict[str, Any]) -> set[str]:
    return set(event_parameter_names(event))


def _wrapped_parameter_locations(push: dict[str, Any]) -> dict[str, list[str]]:
    locations: dict[str, list[str]] = {}
    for wrapper in DATALAYER_WRAPPERS:
        wrapped = push.get(wrapper)
        if not isinstance(wrapped, dict):
            continue
        for name in wrapped:
            locations.setdefault(str(name), []).append(wrapper)
    return locations


def _check_parameter_mapping(
    event: dict[str, Any],
    push: dict[str, Any],
    base: str,
    issues: list[Issue],
) -> None:
    locations = _wrapped_parameter_locations(push)
    for name in sorted(_selected_parameter_names(event)):
        lookup_name = "items" if name.startswith("items[].") else name
        wrappers = locations.get(lookup_name, [])
        if not wrappers:
            add_issue(issues, "error", "DATALAYER_PARAMETER_MAPPING_MISSING", f"{base}.data_layer.push", f"Use the final GA4 name '{name}' inside its project wrapper so GTM can map it without renaming.")
        elif len(wrappers) > 1:
            add_issue(issues, "error", "DATALAYER_PARAMETER_DUPLICATED", f"{base}.data_layer.push", f"Parameter '{name}' appears in multiple wrappers: {', '.join(wrappers)}.")


def _check_ecommerce_wrapper(
    event: dict[str, Any],
    data_layer: dict[str, Any],
    push: dict[str, Any],
    base: str,
    issues: list[Issue],
) -> None:
    classification = str(event.get("classification", ""))
    ecommerce = push.get("ecommerce")
    if classification != "recommended_ecommerce":
        if isinstance(ecommerce, dict) and ecommerce:
            add_issue(issues, "error", "NON_ECOMMERCE_WRAPPER_USED", f"{base}.data_layer.push.ecommerce", "Use ecommerce only for official GA4 ecommerce event data.")
        return
    if not isinstance(ecommerce, dict):
        add_issue(issues, "error", "GTM_ECOMMERCE_WRAPPER_MISSING", f"{base}.data_layer.push.ecommerce", "Use Google's GTM ecommerce format: event plus a nested ecommerce object and items array.")
    elif "items" in _selected_parameter_names(event) and not isinstance(ecommerce.get("items"), list):
        add_issue(issues, "error", "GTM_ECOMMERCE_ITEMS_MISSING", f"{base}.data_layer.push.ecommerce.items", "The selected items parameter needs ecommerce.items as an array.")
    if "ecommerce" not in set(data_layer.get("flush_keys", [])):
        add_issue(issues, "error", "GTM_ECOMMERCE_RESET_MISSING", f"{base}.data_layer.flush_keys", "Clear the previous ecommerce object before the event push.")
    if isinstance(push.get("event_data"), dict) and push.get("event_data"):
        add_issue(issues, "error", "ECOMMERCE_DATA_OUTSIDE_WRAPPER", f"{base}.data_layer.push.event_data", "Keep ecommerce event parameters inside ecommerce instead of event_data.")


def check_developer_examples(plan: dict[str, Any], issues: list[Issue]) -> None:
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    for index, event in enumerate(events):
        base = f"$.events[{index}]"
        classification = str(event.get("classification", ""))
        data_layer = event.get("data_layer")
        if classification in {"automatic", "enhanced_measurement"} and not data_layer:
            continue
        if not isinstance(data_layer, dict) or not isinstance(data_layer.get("push"), dict) or not data_layer.get("push"):
            add_issue(issues, "error", "DATALAYER_EXAMPLE_MISSING", f"{base}.data_layer", "Every manually collected event needs a complete dataLayer.push example for developers.")
            continue
        push = data_layer["push"]
        _check_push_shape(event, push, base, issues)
        _check_parameter_mapping(event, push, base, issues)
        _check_ecommerce_wrapper(event, data_layer, push, base, issues)
