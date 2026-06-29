from __future__ import annotations

import re
from typing import Any

from tracking_plan_validation_catalogs import (
    CUSTOM_CLASSIFICATIONS,
    CUSTOM_RATIONALE_RE,
    GA4_CLASSIFICATIONS,
    GA4_EVENT_NAME_RE,
    GA4_PARAMETER_NAME_RE,
    GA4_RESERVED_EVENT_NAMES,
    GA4_RESERVED_PREFIXES,
    LEGACY_UA_FIELD_NAMES,
    LOW_SIGNAL_CUSTOM_EVENT_NAMES,
    PIANO_CLASSIFICATIONS,
    PIANO_OFFICIAL_CLASSIFICATIONS,
    PII_NAME_RE,
    SAFE_NAME_EXCEPTIONS,
    UA_LEGACY_INDEXED_FIELD_RE,
    UA_PROPERTY_ID_RE,
)
from tracking_plan_validation_model import Issue, add_issue

def check_pii_name(name: str, path: str, issues: list[Issue]) -> None:
    if name in SAFE_NAME_EXCEPTIONS:
        return
    if PII_NAME_RE.search(name):
        add_issue(issues, "error", "PII_FIELD_NAME", path, f"Field '{name}' looks like direct or contact-derived PII.")


def legacy_ua_token(name: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(name)).strip("_").lower()
    return token.replace("_", "")


def check_legacy_ua_field(name: str, path: str, issues: list[Issue]) -> None:
    if not name:
        return
    raw = str(name).strip()
    lowered = raw.lower()
    underscored = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").lower()
    compact = legacy_ua_token(raw)
    if (
        lowered in LEGACY_UA_FIELD_NAMES
        or underscored in LEGACY_UA_FIELD_NAMES
        or compact in LEGACY_UA_FIELD_NAMES
        or UA_LEGACY_INDEXED_FIELD_RE.fullmatch(raw)
        or UA_PROPERTY_ID_RE.search(raw)
    ):
        add_issue(
            issues,
            "error",
            "LEGACY_UA_FIELD",
            path,
            f"'{raw}' is Universal Analytics legacy data. Use it only as migration context and redesign the field through current GA4 or Piano official models.",
        )


def check_platform_mapping(
    event: dict[str, Any],
    event_index: int,
    mapping: dict[str, Any],
    mapping_index: int,
    piano_catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{event_index}].platform_mappings[{mapping_index}]"
    platform = str(mapping.get("platform", ""))
    event_name = str(mapping.get("event_name", ""))
    classification = str(mapping.get("classification", ""))
    props = mapping.get("parameters_or_properties", {})
    if not isinstance(props, dict):
        props = {}

    check_legacy_ua_field(event_name, f"{base}.event_name", issues)

    for key in props:
        check_pii_name(str(key), f"{base}.parameters_or_properties.{key}", issues)
        check_legacy_ua_field(str(key), f"{base}.parameters_or_properties.{key}", issues)
    for item_index, item in enumerate(mapping.get("items_or_products", []) if isinstance(mapping.get("items_or_products"), list) else []):
        if not isinstance(item, dict):
            continue
        for key in item:
            check_pii_name(str(key), f"{base}.items_or_products[{item_index}].{key}", issues)
            check_legacy_ua_field(str(key), f"{base}.items_or_products[{item_index}].{key}", issues)

    if platform == "ga4":
        if event_name and event_name != event.get("event_name") and classification in {"automatic", "enhanced_measurement", "recommended", "recommended_ecommerce", "custom"}:
            add_issue(
                issues,
                "warning",
                "GA4_MAPPING_EVENT_DIFFERS",
                f"{base}.event_name",
                f"GA4 platform mapping event '{event_name}' differs from canonical event_name '{event.get('event_name')}'. Keep this only for deliberate cross-platform business-event inventories.",
            )
        return

    if platform != "piano_analytics":
        return

    catalog_entry = piano_catalog.get(event_name)
    if classification in PIANO_OFFICIAL_CLASSIFICATIONS and not catalog_entry:
        add_issue(
            issues,
            "error",
            "PIANO_OFFICIAL_EVENT_UNKNOWN",
            f"{base}.event_name",
            f"'{event_name}' is marked {classification} but is not in platform-piano-official-events.json.",
        )
        return
    if catalog_entry and classification == "piano_custom":
        add_issue(
            issues,
            "error",
            "PIANO_NATIVE_EVENT_MARKED_CUSTOM",
            f"{base}.classification",
            f"'{event_name}' exists in the Piano official-event catalog; use the official Piano classification instead of piano_custom.",
        )
    if catalog_entry and classification in PIANO_OFFICIAL_CLASSIFICATIONS:
        expected_classification = catalog_entry.get("classification")
        if expected_classification and classification != expected_classification:
            add_issue(
                issues,
                "warning",
                "PIANO_CLASSIFICATION_MISMATCH",
                f"{base}.classification",
                f"'{event_name}' is cataloged as {expected_classification}, not {classification}.",
            )
        missing = sorted(set(catalog_entry.get("mandatory_properties", set())) - set(props))
        if missing:
            add_issue(
                issues,
                "error",
                "PIANO_MANDATORY_PROPERTY_MISSING",
                f"{base}.parameters_or_properties",
                f"'{event_name}' is missing mandatory Piano properties: {', '.join(missing)}.",
            )
        notes = " ".join(
            str(value)
            for value in [
                mapping.get("implementation_notes", ""),
                mapping.get("official_match", ""),
            ]
        ).lower()
        if "server" in notes:
            missing_server = sorted(set(catalog_entry.get("server_side_extra_mandatory_properties", set())) - set(props))
            if missing_server:
                add_issue(
                    issues,
                    "error",
                    "PIANO_SERVER_SIDE_PROPERTY_MISSING",
                    f"{base}.parameters_or_properties",
                    f"Server-side '{event_name}' mapping is missing Piano properties: {', '.join(missing_server)}.",
                )


def implementation_payload_properties(event: dict[str, Any], platform: str, event_name: str | None = None) -> set[str]:
    properties: set[str] = set()
    for payload in event.get("implementation_payloads", []):
        if not isinstance(payload, dict) or payload.get("platform") != platform:
            continue
        if event_name and payload.get("event_name") != event_name:
            continue
        payload_data = payload.get("payload", {})
        if isinstance(payload_data, dict):
            properties.update(str(key) for key in payload_data)
    return properties


def check_piano_event_shape(
    event: dict[str, Any],
    index: int,
    piano_catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    if classification not in PIANO_CLASSIFICATIONS and event.get("primary_platform") != "piano_analytics":
        return

    piano_mappings = [
        mapping
        for mapping in event.get("platform_mappings", [])
        if isinstance(mapping, dict) and mapping.get("platform") == "piano_analytics"
    ]
    piano_payloads = [
        payload
        for payload in event.get("implementation_payloads", [])
        if isinstance(payload, dict) and payload.get("platform") == "piano_analytics"
    ]
    if not piano_mappings and not piano_payloads and event_name not in piano_catalog:
        add_issue(
            issues,
            "error",
            "PIANO_EVENT_MAPPING_MISSING",
            base,
            "Piano events need a Piano platform mapping, a Piano implementation payload, or a canonical Piano official event name.",
        )

    if classification in PIANO_OFFICIAL_CLASSIFICATIONS:
        catalog_entry = piano_catalog.get(event_name)
        mapped_names = {str(mapping.get("event_name", "")) for mapping in piano_mappings}
        payload_names = {str(payload.get("event_name", "")) for payload in piano_payloads}
        candidate_names = {event_name, *mapped_names, *payload_names}
        known_names = candidate_names & set(piano_catalog)
        if not known_names:
            add_issue(
                issues,
                "error",
                "PIANO_OFFICIAL_EVENT_UNKNOWN",
                f"{base}.event_name",
                f"No Piano official event catalog match found for {sorted(candidate_names)}.",
            )
            return
        if catalog_entry:
            expected_classification = catalog_entry.get("classification")
            if expected_classification and classification != expected_classification:
                add_issue(
                    issues,
                    "warning",
                    "PIANO_CLASSIFICATION_MISMATCH",
                    f"{base}.classification",
                    f"'{event_name}' is cataloged as {expected_classification}, not {classification}.",
                )
        for name in known_names:
            mandatory = set(piano_catalog[name].get("mandatory_properties", set()))
            if not mandatory:
                continue
            available = set(event.get("parameters", []))
            available |= implementation_payload_properties(event, "piano_analytics", name)
            for mapping in piano_mappings:
                if mapping.get("event_name") == name and isinstance(mapping.get("parameters_or_properties"), dict):
                    available |= set(mapping["parameters_or_properties"])
            missing = sorted(mandatory - available)
            if missing:
                add_issue(
                    issues,
                    "error",
                    "PIANO_MANDATORY_PROPERTY_MISSING",
                    base,
                    f"'{name}' is missing mandatory Piano properties: {', '.join(missing)}.",
                )
    elif classification == "piano_custom" and event_name in piano_catalog:
        add_issue(
            issues,
            "error",
            "PIANO_NATIVE_EVENT_MARKED_CUSTOM",
            f"{base}.classification",
            f"'{event_name}' exists in the Piano official-event catalog; use the official Piano classification instead of piano_custom.",
        )


def is_ga4_event(event: dict[str, Any]) -> bool:
    if event.get("primary_platform") == "ga4":
        return True
    if event.get("classification") in GA4_CLASSIFICATIONS:
        return True
    if event.get("ga4_payload") or event.get("data_layer") or event.get("official_ga4_match"):
        return True
    return any(
        isinstance(mapping, dict) and mapping.get("platform") == "ga4"
        for mapping in event.get("platform_mappings", [])
    )


def check_ga4_name(name: str, path: str, kind: str, issues: list[Issue]) -> None:
    if not name:
        return
    pattern = GA4_EVENT_NAME_RE if kind == "event" else GA4_PARAMETER_NAME_RE
    if not pattern.fullmatch(name):
        add_issue(
            issues,
            "error",
            "GA4_NAME_FORMAT",
            path,
            f"GA4 {kind} name '{name}' must start with a letter, use only letters/numbers/underscores, and be at most 40 characters.",
        )
    lowered = name.lower()
    for prefix in GA4_RESERVED_PREFIXES:
        if lowered.startswith(prefix):
            add_issue(
                issues,
                "error",
                "GA4_RESERVED_PREFIX",
                path,
                f"GA4 {kind} name '{name}' uses reserved prefix '{prefix}'.",
            )


def is_ga4_parameter_reference(param: dict[str, Any]) -> bool:
    classification = str(param.get("classification", ""))
    if classification in {
        "ga4_auto_collected_parameter",
        "ga4_native_parameter",
        "ga4_recommended_parameter",
        "ga4_ecommerce_parameter",
        "custom_event_parameter",
        "custom_item_parameter",
        "custom_user_property",
    }:
        return True
    return False


def should_lint_ga4_parameter_name(name: str, param: dict[str, Any]) -> bool:
    if not name or name.startswith("items[]."):
        return False
    if "." in name:
        return False
    if param.get("scope") == "implementation":
        return False
    return is_ga4_parameter_reference(param)


def check_ga4_event_shape(
    event: dict[str, Any],
    index: int,
    ga4_catalog: dict[str, Any],
    issues: list[Issue],
) -> None:
    if not is_ga4_event(event):
        return

    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    payload = event.get("ga4_payload", {})
    payload_name = str(payload.get("event_name", "")) if isinstance(payload, dict) else ""
    ga4_names = [name for name in [event_name, payload_name] if name]
    for mapping in event.get("platform_mappings", []):
        if isinstance(mapping, dict) and mapping.get("platform") == "ga4" and mapping.get("event_name"):
            ga4_names.append(str(mapping["event_name"]))

    for name in sorted(set(ga4_names)):
        check_ga4_name(name, f"{base}.event_name", "event", issues)
        if name in GA4_RESERVED_EVENT_NAMES and classification == "custom":
            add_issue(
                issues,
                "error",
                "GA4_RESERVED_EVENT_NAME",
                f"{base}.event_name",
                f"'{name}' is reserved by GA4 and must not be used as a custom event.",
            )

    if classification == "recommended" and event_name not in ga4_catalog["recommended"]:
        if event_name in ga4_catalog["ecommerce"]:
            add_issue(
                issues,
                "error",
                "GA4_RECOMMENDED_ECOMMERCE_MISCLASSIFIED",
                f"{base}.classification",
                f"'{event_name}' is a GA4 ecommerce event; classify it as recommended_ecommerce.",
            )
        else:
            add_issue(
                issues,
                "error",
                "GA4_RECOMMENDED_EVENT_UNKNOWN",
                f"{base}.event_name",
                f"'{event_name}' is classified as recommended but is not in the bundled official GA4 recommended-event catalog.",
            )
    if classification == "recommended_ecommerce" and event_name not in ga4_catalog["ecommerce"]:
        add_issue(
            issues,
            "error",
            "GA4_RECOMMENDED_ECOMMERCE_UNKNOWN",
            f"{base}.event_name",
            f"'{event_name}' is classified as recommended_ecommerce but is not in the GA4 ecommerce event set.",
        )
    if classification == "automatic" and event_name not in ga4_catalog["automatic"]:
        add_issue(
            issues,
            "warning",
            "GA4_AUTOMATIC_EVENT_UNKNOWN",
            f"{base}.event_name",
            f"'{event_name}' is classified as automatic but is not in the bundled automatic-event lookup.",
        )
    if classification == "enhanced_measurement" and event_name not in ga4_catalog["enhanced"]:
        add_issue(
            issues,
            "warning",
            "GA4_ENHANCED_EVENT_UNKNOWN",
            f"{base}.event_name",
            f"'{event_name}' is classified as enhanced_measurement but is not in the bundled enhanced-measurement lookup.",
        )
    if classification == "custom" and event_name in ga4_catalog["all_official"]:
        add_issue(
            issues,
            "error",
            "GA4_OFFICIAL_EVENT_MARKED_CUSTOM",
            f"{base}.classification",
            f"'{event_name}' matches an official GA4 event; use the official classification instead of custom.",
        )

    payload_parameters = payload.get("parameters", {}) if isinstance(payload, dict) and isinstance(payload.get("parameters"), dict) else {}
    for name in payload_parameters:
        check_ga4_name(str(name), f"{base}.ga4_payload.parameters.{name}", "parameter", issues)

    if classification == "recommended" and event_name in ga4_catalog["recommended"]:
        required_parameters = ga4_catalog.get("recommended_required_parameters", {}).get(event_name, set())
        if required_parameters:
            event_parameters = {
                str(parameter)
                for parameter in event.get("parameters", [])
                if isinstance(parameter, str)
            }
            missing_from_event = sorted(required_parameters - event_parameters)
            missing_from_payload = sorted(required_parameters - set(payload_parameters))
            if missing_from_event or missing_from_payload:
                missing = sorted(set(missing_from_event) | set(missing_from_payload))
                add_issue(
                    issues,
                    "error",
                    "GA4_RECOMMENDED_PARAMETER_MISSING",
                    f"{base}.ga4_payload.parameters",
                    f"Recommended GA4 event '{event_name}' is missing required official parameter(s): {', '.join(missing)}.",
                )


def check_custom_event_rationale(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    classification = str(event.get("classification", ""))
    if classification not in CUSTOM_CLASSIFICATIONS:
        return

    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    rationale_text = " ".join(
        str(event.get(key, ""))
        for key in ["official_match", "official_ga4_match", "business_question", "trigger", "implementation_notes"]
    )
    if not CUSTOM_RATIONALE_RE.search(rationale_text):
        add_issue(
            issues,
            "error",
            "CUSTOM_EVENT_RATIONALE_MISSING",
            f"{base}.official_match",
            "Custom events must state why native, recommended, ecommerce, or platform-standard events are not sufficient and what business/diagnostic need they answer.",
        )
    if event_name in LOW_SIGNAL_CUSTOM_EVENT_NAMES:
        add_issue(
            issues,
            "error",
            "LOW_SIGNAL_CUSTOM_EVENT_NAME",
            f"{base}.event_name",
            f"Custom event '{event_name}' is a generic click name. Prefer an official event or a semantic business-intent name.",
        )

