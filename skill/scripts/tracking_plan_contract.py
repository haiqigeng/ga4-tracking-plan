from __future__ import annotations

from typing import Any


def event_journey_ids(event: dict[str, Any]) -> list[str]:
    values = event.get("journey_ids")
    return [str(value) for value in values if str(value).strip()] if isinstance(values, list) else []


def primary_journey_id(event: dict[str, Any]) -> str:
    values = event_journey_ids(event)
    return values[0] if values else ""


def event_parameter_bindings(event: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = event.get("parameter_bindings")
    return [binding for binding in bindings if isinstance(binding, dict)] if isinstance(bindings, list) else []


def event_parameter_names(event: dict[str, Any]) -> list[str]:
    return [
        str(binding.get("parameter_name", ""))
        for binding in event_parameter_bindings(event)
        if str(binding.get("parameter_name", "")).strip()
    ]


def event_ga4_payload(event: dict[str, Any]) -> dict[str, Any]:
    data_layer = event.get("data_layer")
    push = data_layer.get("push") if isinstance(data_layer, dict) else None
    if isinstance(push, dict) and push:
        parameters: dict[str, Any] = {}
        for wrapper in ("page", "event_data"):
            wrapped = push.get(wrapper)
            if isinstance(wrapped, dict):
                parameters.update(wrapped)
        ecommerce = push.get("ecommerce")
        items: list[Any] = []
        if isinstance(ecommerce, dict):
            parameters.update({key: value for key, value in ecommerce.items() if key != "items"})
            if isinstance(ecommerce.get("items"), list):
                items = ecommerce["items"]
        return {
            "event_name": str(push.get("event") or event.get("event_name", "")),
            "parameters": parameters,
            "items": items,
        }
    return {"event_name": str(event.get("event_name", "")), "parameters": {}, "items": []}


def parameter_value_domain(parameter: dict[str, Any]) -> dict[str, Any]:
    domain = parameter.get("value_domain")
    return domain if isinstance(domain, dict) else {}


def parameter_allowed_values(parameter: dict[str, Any]) -> list[str]:
    return [
        str(entry.get("normalized_value", ""))
        for entry in parameter_value_domain(parameter).get("entries", [])
        if isinstance(entry, dict) and str(entry.get("normalized_value", "")).strip()
    ]


def source_registry(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for source in plan.get("documentation_sources_checked", []):
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id", "")).strip()
        if source_id:
            result[source_id] = source
    return result
