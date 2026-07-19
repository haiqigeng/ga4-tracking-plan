from __future__ import annotations

import re
from typing import Any

from tracking_plan_contract import event_ga4_payload, event_parameter_names
from tracking_plan_validation_catalogs import (
    CUSTOM_CLASSIFICATIONS,
    GA4_CLASSIFICATIONS,
    GA4_EVENT_NAME_RE,
    GA4_PARAMETER_NAME_RE,
    GA4_RESERVED_EVENT_NAMES,
    GA4_RESERVED_PREFIXES,
    LEGACY_UA_FIELD_NAMES,
    LOW_SIGNAL_CUSTOM_EVENT_NAMES,
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
            f"'{raw}' is Universal Analytics legacy data. Use it only as migration context and redesign the field through the current GA4 model.",
        )


def is_ga4_event(event: dict[str, Any]) -> bool:
    if event.get("classification") in GA4_CLASSIFICATIONS:
        return True
    if event.get("data_layer"):
        return True
    return False


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


def _check_event_names(
    names: list[str],
    classification: str,
    base: str,
    issues: list[Issue],
) -> None:
    for name in sorted(set(names)):
        check_ga4_name(name, f"{base}.event_name", "event", issues)
        if name in GA4_RESERVED_EVENT_NAMES and classification == "custom":
            add_issue(
                issues,
                "error",
                "GA4_RESERVED_EVENT_NAME",
                f"{base}.event_name",
                f"'{name}' is reserved by GA4 and must not be used as a custom event.",
            )


def _check_event_classification(
    event_name: str,
    classification: str,
    ga4_catalog: dict[str, Any],
    base: str,
    issues: list[Issue],
) -> None:
    if classification == "recommended" and event_name not in ga4_catalog["recommended"]:
        code = "GA4_RECOMMENDED_ECOMMERCE_MISCLASSIFIED" if event_name in ga4_catalog["ecommerce"] else "GA4_RECOMMENDED_EVENT_UNKNOWN"
        message = (
            f"'{event_name}' is a GA4 ecommerce event; classify it as recommended_ecommerce."
            if code == "GA4_RECOMMENDED_ECOMMERCE_MISCLASSIFIED"
            else f"'{event_name}' is classified as recommended but is not in the bundled official GA4 recommended-event catalog."
        )
        path = f"{base}.classification" if code == "GA4_RECOMMENDED_ECOMMERCE_MISCLASSIFIED" else f"{base}.event_name"
        add_issue(issues, "error", code, path, message)
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


def _check_required_recommended_parameters(
    event: dict[str, Any],
    event_name: str,
    classification: str,
    payload_parameters: dict[str, Any],
    ga4_catalog: dict[str, Any],
    base: str,
    issues: list[Issue],
) -> None:
    if classification != "recommended" or event_name not in ga4_catalog["recommended"]:
        return
    required = ga4_catalog.get("recommended_required_parameters", {}).get(event_name, set())
    missing = sorted(
        (required - set(event_parameter_names(event)))
        | (required - set(payload_parameters))
    )
    if missing:
        add_issue(
            issues,
            "error",
            "GA4_RECOMMENDED_PARAMETER_MISSING",
            f"{base}.data_layer.push",
            f"Recommended GA4 event '{event_name}' is missing required official parameter(s): {', '.join(missing)}.",
        )


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
    payload = event_ga4_payload(event)
    payload_name = str(payload.get("event_name", "")) if isinstance(payload, dict) else ""
    ga4_names = [name for name in [event_name, payload_name] if name]
    _check_event_names(ga4_names, classification, base, issues)
    _check_event_classification(event_name, classification, ga4_catalog, base, issues)

    payload_parameters = payload.get("parameters", {}) if isinstance(payload, dict) and isinstance(payload.get("parameters"), dict) else {}
    for name in payload_parameters:
        check_ga4_name(str(name), f"{base}.data_layer.push.{name}", "parameter", issues)

    _check_required_recommended_parameters(
        event,
        event_name,
        classification,
        payload_parameters,
        ga4_catalog,
        base,
        issues,
    )


def check_custom_event_rationale(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    classification = str(event.get("classification", ""))
    if classification not in CUSTOM_CLASSIFICATIONS:
        return

    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    if event_name in LOW_SIGNAL_CUSTOM_EVENT_NAMES:
        add_issue(
            issues,
            "error",
            "LOW_SIGNAL_CUSTOM_EVENT_NAME",
            f"{base}.event_name",
            f"Custom event '{event_name}' is a generic click name. Prefer an official event or a semantic business-intent name.",
        )
