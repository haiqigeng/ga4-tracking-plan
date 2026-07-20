from __future__ import annotations

from typing import Any

from ecommerce_matrix import (
    EVENT_PARAMETERS_BY_EVENT,
    OFFICIAL_ITEM_PARAMETERS,
)
from tracking_plan_contract import (
    event_ga4_payload,
    event_parameter_bindings,
    event_parameter_names,
)
from tracking_plan_validation_catalogs import (
    ECOMMERCE_EVENTS,
    GA4_CLASSIFICATIONS,
    LEGACY_WRAPPER_EVENT_KEYS,
    LEGACY_WRAPPER_PARAMETERS,
    MANUAL_COLLECTION_SOURCES,
    NON_CONVERSION_MEASUREMENT_ROLES,
    OFFICIAL_ECOMMERCE_PARAMETER_CLASSES,
    OFFICIAL_VERIFICATION_CLASSES,
    POTENTIAL_DUPLICATE_EVENTS,
    TRANSACTION_EVENTS,
    VALUE_EVENTS_REQUIRE_CURRENCY,
    WEAK_COMPONENT_CONTEXTS,
    WEAK_DATA_DEPENDENCY_VALUES,
)
from tracking_plan_validation_common import check_business_question, check_official_verification, walk_keys
from tracking_plan_validation_events import (
    check_custom_event_rationale,
    check_ga4_event_shape,
    check_legacy_ua_field,
    check_pii_name,
)
from tracking_plan_validation_model import Issue, add_issue


def check_collection_strategy(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    strategy = event.get("collection_strategy", {})
    if not isinstance(strategy, dict):
        return
    source = str(strategy.get("collection_source", ""))
    duplicate = strategy.get("duplicate_risk", {})
    if classification == "automatic" and source not in {"ga4_automatic", *MANUAL_COLLECTION_SOURCES}:
        add_issue(issues, "warning", "AUTOMATIC_COLLECTION_SOURCE_MISMATCH", f"{base}.collection_strategy.collection_source", "GA4 automatic events should normally use collection_source='ga4_automatic'.")
    if classification == "enhanced_measurement" and source not in {"ga4_enhanced_measurement", *MANUAL_COLLECTION_SOURCES}:
        add_issue(issues, "warning", "ENHANCED_COLLECTION_SOURCE_MISMATCH", f"{base}.collection_strategy.collection_source", "GA4 enhanced-measurement events should normally use collection_source='ga4_enhanced_measurement'.")
    if event_name not in POTENTIAL_DUPLICATE_EVENTS or source not in MANUAL_COLLECTION_SOURCES:
        return
    if not isinstance(duplicate, dict) or duplicate.get("level") == "low":
        add_issue(issues, "warning", "ENHANCED_MEASUREMENT_DUPLICATE_RISK_UNDERSTATED", f"{base}.collection_strategy.duplicate_risk.level", f"Manual collection of '{event_name}' needs a medium/high duplicate-risk decision unless native collection is explicitly disabled or insufficient.")
    if not str(duplicate.get("reason", "")).strip() or not str(duplicate.get("dedupe_rule", "")).strip():
        add_issue(issues, "error", "DUPLICATE_RISK_DECISION_WEAK", f"{base}.collection_strategy.duplicate_risk", "Manual collection of automatic/enhanced-measurement candidates needs a concrete duplicate-risk reason and dedupe rule.")


def check_event_context(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    check_legacy_ua_field(event_name, f"{base}.event_name", issues)
    check_official_verification(event.get("official_verification"), "ga4", f"{base}.official_verification", issues, required=classification in OFFICIAL_VERIFICATION_CLASSES)
    check_collection_strategy(event, index, issues)
    for legacy_field in ("ga4_payload", "parameter_profile"):
        if legacy_field in event:
            add_issue(
                issues,
                "error",
                "DUPLICATE_DERIVED_STATE",
                f"{base}.{legacy_field}",
                f"Remove deprecated {legacy_field}; parameter bindings and data_layer are the canonical source.",
            )

    component = str(event.get("page_or_component", "")).strip()
    if component.lower().rstrip(".") in WEAK_COMPONENT_CONTEXTS:
        add_issue(issues, "error", "EVENT_COMPONENT_CONTEXT_WEAK", f"{base}.page_or_component", "Event page_or_component must identify the concrete page area, module, form, list, or interaction target.")
    dependencies = event.get("data_dependencies", [])
    if isinstance(dependencies, list) and any(str(value).strip().lower().rstrip(".") in WEAK_DATA_DEPENDENCY_VALUES for value in dependencies):
        add_issue(issues, "error", "EVENT_DATA_DEPENDENCY_WEAK", f"{base}.data_dependencies", "Event data_dependencies must list concrete source values or systems, not generic placeholders.")

    role = str(event.get("measurement_role", ""))
    if role in NON_CONVERSION_MEASUREMENT_ROLES and event.get("key_event"):
        add_issue(issues, "error", "KEY_EVENT_ROLE_INVALID", f"{base}.measurement_role", f"Events with measurement_role '{role}' should not be marked as key events.")
    if role == "macro_conversion" and not event.get("key_event"):
        add_issue(issues, "warning", "MACRO_CONVERSION_NOT_KEY_EVENT", f"{base}.key_event", "Macro conversions should normally be marked as key events or explicitly justified in implementation_notes.")
    if role == "macro_conversion" and event.get("priority") != "must":
        add_issue(issues, "warning", "MACRO_CONVERSION_PRIORITY", f"{base}.priority", "Macro conversions should normally use priority='must'.")
    check_business_question(event.get("business_question"), f"{base}.business_question", issues)
    evidence = event.get("evidence_basis", {})
    if isinstance(evidence, dict) and not evidence.get("source_refs"):
        add_issue(issues, "error", "EVENT_EVIDENCE_SOURCE_MISSING", f"{base}.evidence_basis.source_refs", "Event evidence must identify the website, brief, client file, or analyst inference it is based on.")


def check_event_parameter_references(event: dict[str, Any], index: int, parameter_names: set[str], issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    for parameter in event_parameter_names(event):
        check_pii_name(str(parameter), f"{base}.parameter_bindings", issues)
        check_legacy_ua_field(str(parameter), f"{base}.parameter_bindings", issues)
        if parameter in LEGACY_WRAPPER_PARAMETERS:
            add_issue(issues, "warning", "LEGACY_WRAPPER_PARAMETER", f"{base}.parameter_bindings", f"Parameter '{parameter}' is a legacy wrapper pattern. Prefer direct GA4 event parameters.")
        if parameter.startswith("items[].") and parameter not in OFFICIAL_ITEM_PARAMETERS and parameter not in parameter_names:
            add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_NOT_DEFINED", f"{base}.parameter_bindings", f"Custom item parameter '{parameter}' must be defined in the parameter reference.")
        elif parameter not in parameter_names and not parameter.startswith("items[]."):
            add_issue(issues, "warning", "PARAMETER_NOT_DEFINED", f"{base}.parameter_bindings", f"Parameter '{parameter}' is not in the parameter reference.")


def check_data_layer_transport(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    data_layer = event.get("data_layer", {})
    event_key = data_layer.get("event_key") if isinstance(data_layer, dict) else None
    if event_name in LEGACY_WRAPPER_EVENT_KEYS or event_key in LEGACY_WRAPPER_EVENT_KEYS:
        add_issue(issues, "error", "LEGACY_WRAPPER_EVENT", f"{base}.data_layer.event_key", "Use the GA4 event name directly instead of a wrapper event such as gtm.custom_event.")
    push = data_layer.get("push", {}) if isinstance(data_layer, dict) else {}
    if isinstance(push, dict):
        if push.get("event") in LEGACY_WRAPPER_EVENT_KEYS:
            add_issue(issues, "error", "LEGACY_WRAPPER_PUSH", f"{base}.data_layer.push.event", "dataLayer push uses a wrapper event. Push the final GA4 event name directly.")
        for path, key in walk_keys(push, f"{base}.data_layer.push"):
            if not (key == "user_id" and path.endswith(".user.user_id")):
                check_pii_name(key, path, issues)
            check_legacy_ua_field(key, path, issues)


def check_event_transport(event: dict[str, Any], index: int, parameter_names: set[str], issues: list[Issue]) -> None:
    check_event_parameter_references(event, index, parameter_names, issues)
    check_data_layer_transport(event, index, issues)


def check_ecommerce_payload_parameters(event: dict[str, Any], index: int, parameter_lookup: dict[str, dict[str, Any]], issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    payload = event_ga4_payload(event)
    payload_parameters = payload.get("parameters", {}) if isinstance(payload, dict) and isinstance(payload.get("parameters"), dict) else {}
    official_parameters = EVENT_PARAMETERS_BY_EVENT.get(event_name, set())
    bindings = {
        str(binding.get("parameter_name", "")): binding
        for binding in event_parameter_bindings(event)
    }
    for name in payload_parameters:
        metadata = parameter_lookup.get(name)
        effective_classification = str(bindings.get(name, {}).get("classification") or (metadata or {}).get("classification") or "")
        if name not in official_parameters:
            if metadata is None:
                add_issue(issues, "warning", "CUSTOM_ECOMMERCE_PARAMETER_NOT_DEFINED", f"{base}.data_layer.push.ecommerce.{name}", f"Custom ecommerce event parameter '{name}' must be defined in the parameter reference.")
            elif effective_classification in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                add_issue(issues, "error", "CUSTOM_ECOMMERCE_PARAMETER_MISCLASSIFIED", f"{base}.data_layer.push.ecommerce.{name}", f"'{name}' is not an official parameter for {event_name}; classify it as custom_event_parameter or remove it.")


def check_ecommerce_items(event: dict[str, Any], index: int, parameter_lookup: dict[str, dict[str, Any]], issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    payload = event_ga4_payload(event)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    bindings = {
        str(binding.get("parameter_name", "")): binding
        for binding in event_parameter_bindings(event)
    }
    if "items" in set(event_parameter_names(event)) and (not isinstance(items, list) or not items):
        add_issue(issues, "error", "ECOMMERCE_ITEMS_MISSING", f"{base}.data_layer.push.ecommerce.items", "The selected items parameter needs a non-empty ecommerce.items example.")
    for item_index, item in enumerate(items if isinstance(items, list) else []):
        if not isinstance(item, dict):
            continue
        if "item_id" not in item and "item_name" not in item:
            add_issue(issues, "error", "ECOMMERCE_ITEM_ID_OR_NAME", f"{base}.data_layer.push.ecommerce.items[{item_index}]", "Each ecommerce item needs item_id or item_name.")
        if "currency" in item:
            add_issue(issues, "error", "ITEM_SCOPE_CURRENCY", f"{base}.data_layer.push.ecommerce.items[{item_index}].currency", "currency is event-scoped, not item-scoped.")
        for key in item:
            parameter_name = f"items[].{key}"
            metadata = parameter_lookup.get(parameter_name)
            effective_classification = str(bindings.get(parameter_name, {}).get("classification") or (metadata or {}).get("classification") or "")
            if parameter_name in OFFICIAL_ITEM_PARAMETERS:
                continue
            if metadata is None:
                add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_NOT_DEFINED", f"{base}.data_layer.push.ecommerce.items[{item_index}].{key}", f"Custom item parameter '{parameter_name}' must be defined in the parameter reference.")
            elif effective_classification in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", f"{base}.data_layer.push.ecommerce.items[{item_index}].{key}", f"'{parameter_name}' is not an official GA4 item parameter; classify it as custom_item_parameter or remove it.")
    if "ecommerce" not in set(event.get("data_layer", {}).get("flush_keys", [])):
        add_issue(issues, "warning", "ECOMMERCE_FLUSH_MISSING", f"{base}.data_layer.flush_keys", "Flush ecommerce before ecommerce pushes to prevent stale item data.")


def check_ecommerce_transaction(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    payload = event_ga4_payload(event)
    payload_parameters = payload.get("parameters", {}) if isinstance(payload, dict) and isinstance(payload.get("parameters"), dict) else {}
    if event_name in TRANSACTION_EVENTS and "transaction_id" not in payload_parameters:
        add_issue(issues, "error", "TRANSACTION_ID_MISSING", f"{base}.data_layer.push.ecommerce", f"{event_name} needs transaction_id for deduplication.")
    if event_name in VALUE_EVENTS_REQUIRE_CURRENCY and "value" in payload_parameters and "currency" not in payload_parameters:
        add_issue(issues, "error", "CURRENCY_MISSING", f"{base}.data_layer.push.ecommerce", "currency is required when value is sent.")


def check_ecommerce_event(event: dict[str, Any], index: int, parameter_lookup: dict[str, dict[str, Any]], issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    if event_name in ECOMMERCE_EVENTS and classification != "recommended_ecommerce":
        add_issue(issues, "warning", "ECOMMERCE_CLASSIFICATION", f"{base}.classification", f"Official ecommerce event '{event_name}' should usually be classified as recommended_ecommerce.")
    if classification != "recommended_ecommerce":
        return
    if event_name not in ECOMMERCE_EVENTS:
        add_issue(issues, "error", "INVALID_ECOMMERCE_EVENT", f"{base}.event_name", f"'{event_name}' is not an official GA4 ecommerce event.")
        return
    check_ecommerce_payload_parameters(event, index, parameter_lookup, issues)
    check_ecommerce_items(event, index, parameter_lookup, issues)
    check_ecommerce_transaction(event, index, issues)


def check_event_privacy_and_catalog(event: dict[str, Any], index: int, ga4_catalog: dict[str, Any], issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    classification = str(event.get("classification", ""))
    privacy = event.get("privacy", {})
    if privacy.get("pii_risk") == "high":
        add_issue(issues, "error", "HIGH_PII_RISK", f"{base}.privacy.pii_risk", "Direct high-risk PII cannot be part of a GA4 event payload.")
    cardinality_notes = f"{privacy.get('notes', '')} {event.get('implementation_notes', '')}".strip()
    if privacy.get("cardinality_risk") == "high" and not cardinality_notes:
        add_issue(issues, "warning", "HIGH_CARDINALITY_RISK", f"{base}.privacy.cardinality_risk", "High-cardinality fields should not be registered as reporting dimensions unless justified.")
    if classification in GA4_CLASSIFICATIONS and classification != "automatic" and not event.get("data_layer"):
        add_issue(issues, "warning", "GA4_TRANSPORT_EXAMPLE_MISSING", f"{base}.data_layer", "A manually collected GA4 event needs a dataLayer example.")
    check_ga4_event_shape(event, index, ga4_catalog, issues)
    check_custom_event_rationale(event, index, issues)


def check_event(
    event: dict[str, Any],
    index: int,
    parameter_lookup: dict[str, dict[str, Any]],
    ga4_catalog: dict[str, Any],
    issues: list[Issue],
) -> None:
    check_event_context(event, index, issues)
    check_event_transport(event, index, set(parameter_lookup), issues)
    check_ecommerce_event(event, index, parameter_lookup, issues)
    check_event_privacy_and_catalog(event, index, ga4_catalog, issues)
