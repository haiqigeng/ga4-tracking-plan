from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ecommerce_matrix import EVENT_PARAMETERS_BY_EVENT, OFFICIAL_ITEM_PARAMETERS


ECOMMERCE_EVENTS = {
    "add_payment_info",
    "add_shipping_info",
    "add_to_cart",
    "add_to_wishlist",
    "begin_checkout",
    "purchase",
    "refund",
    "remove_from_cart",
    "select_item",
    "select_promotion",
    "view_cart",
    "view_item",
    "view_item_list",
    "view_promotion",
}

TRANSACTION_EVENTS = {"purchase", "refund"}
VALUE_EVENTS_REQUIRE_CURRENCY = ECOMMERCE_EVENTS | {
    "generate_lead",
    "qualify_lead",
    "disqualify_lead",
    "working_lead",
    "close_convert_lead",
    "close_unconvert_lead",
}

LEGACY_WRAPPER_EVENT_KEYS = {"gtm.custom_event", "custom_event"}
LEGACY_WRAPPER_PARAMETERS = {"event_name", "action", "label"}
LEGACY_UA_FIELD_NAMES = {
    "ua",
    "ga",
    "ga3",
    "gau",
    "universal_analytics",
    "ua_property",
    "ua_property_id",
    "ua_tracking_id",
    "tracking_id",
    "hit_type",
    "hittype",
    "event_category",
    "eventcategory",
    "event_action",
    "eventaction",
    "event_label",
    "eventlabel",
    "event_value",
    "eventvalue",
    "non_interaction",
    "noninteraction",
    "enhanced_ecommerce",
    "enhancedecommerce",
    "product_action",
    "productaction",
    "product_list",
    "productlist",
    "checkout_step",
    "checkoutstep",
    "checkout_option",
    "checkoutoption",
}
UA_PROPERTY_ID_RE = re.compile(r"\bUA-\d+-\d+\b", re.IGNORECASE)
UA_LEGACY_INDEXED_FIELD_RE = re.compile(r"^(dimension|metric)\d+$", re.IGNORECASE)
AUTOMATIC_EVENTS = {"page_view", "first_visit", "session_start", "user_engagement"}
GA4_EVENT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
GA4_PARAMETER_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
GA4_RESERVED_PREFIXES = ("firebase_", "ga_", "google_")
GA4_RESERVED_EVENT_NAMES = {
    "ad_activeview",
    "ad_click",
    "ad_exposure",
    "ad_impression",
    "ad_query",
    "ad_reward",
    "adunit_exposure",
    "app_clear_data",
    "app_exception",
    "app_install",
    "app_remove",
    "app_store_refund",
    "app_store_subscription_cancel",
    "app_store_subscription_convert",
    "app_store_subscription_renew",
    "app_update",
    "error",
    "firebase_campaign",
    "firebase_in_app_message_action",
    "firebase_in_app_message_dismiss",
    "firebase_in_app_message_impression",
    "first_open",
    "first_visit",
    "in_app_purchase",
    "notification_dismiss",
    "notification_foreground",
    "notification_open",
    "notification_receive",
    "os_update",
    "screen_view",
    "session_start",
    "user_engagement",
}
GA4_RESERVED_PARAMETER_NAMES = {
    "currency",
    "debug_mode",
    "engagement_time_msec",
    "firebase_conversion",
    "gclid",
    "session_id",
    "session_number",
}
OFFICIAL_ECOMMERCE_PARAMETER_CLASSES = {"ga4_ecommerce_parameter", "ga4_ecommerce_item_parameter"}

PII_NAME_RE = re.compile(
    r"(^|_)(email|e_mail|mail|hashed_email|sha256_email|phone|telephone|tel|mobile|"
    r"first_name|last_name|full_name|address|postal|zip_code|zipcode|customer_id|"
    r"user_id|client_id|account_id|message|comment|free_text|question_text)($|_)",
    re.IGNORECASE,
)

SAFE_NAME_EXCEPTIONS = {
    "item_name",
    "item_list_name",
    "promotion_name",
    "creative_name",
    "page_title",
    "page_location",
    "page_referrer",
    "form_name",
    "method",
    "video_title",
    "search_term",
    "content_name",
    "file_name",
    "link_text",
    "link_url",
}

PIANO_OFFICIAL_CLASSIFICATIONS = {"piano_standard", "piano_sales_insights", "piano_av_insights"}
PIANO_CLASSIFICATIONS = PIANO_OFFICIAL_CLASSIFICATIONS | {"piano_custom"}
GA4_CLASSIFICATIONS = {"automatic", "enhanced_measurement", "recommended", "recommended_ecommerce", "custom"}
CUSTOM_CLASSIFICATIONS = {"custom", "piano_custom"}
CUSTOM_PARAMETER_CLASSIFICATIONS = {
    "custom_event_parameter",
    "custom_item_parameter",
    "custom_user_property",
    "piano_custom_property",
}
NON_CONVERSION_MEASUREMENT_ROLES = {"context", "diagnostic"}
OFFICIAL_SOURCE_DOMAINS = {
    "ga4": ("developers.google.com/analytics", "support.google.com/analytics"),
    "piano_analytics": ("developers.piano.io", "analytics-docs.piano.io"),
}
CUSTOM_RATIONALE_RE = re.compile(
    r"(custom|no official|no native|no recommended|no standard|not sufficient|insufficient|"
    r"does not fit|doesn't fit|does not cover|not covered|business[- ]specific|diagnostic|"
    r"intent|before login|before sign[_ -]?up|before conversion|pre[-_ ]conversion|funnel friction)",
    re.IGNORECASE,
)
WEAK_BUSINESS_QUESTION_RE = re.compile(
    r"^\s*(track|measure|capture|send|fire|record)\s+(a\s+|the\s+)?"
    r"(click|event|interaction|page\s*view|button|link|cta|tag)\b",
    re.IGNORECASE,
)
WEAK_BUSINESS_QUESTIONS = {
    "which link was clicked?",
    "which button was clicked?",
    "track clicks",
    "track click",
    "track event",
    "track page view",
}
WEAK_NOT_TRACKED_REASONS = {
    "n/a",
    "na",
    "none",
    "not needed",
    "not relevant",
    "not tracked",
    "out of scope",
    "todo",
    "tbd",
}
WEAK_REPORTING_PURPOSES = {
    "n/a",
    "na",
    "none",
    "not applicable",
    "reporting",
    "tbd",
    "todo",
    "track",
    "tracking",
}
WEAK_VALUE_RULES = {
    "n/a",
    "na",
    "none",
    "not applicable",
    "string",
    "text",
    "tbd",
    "todo",
    "use value",
}
WEAK_COMPONENT_CONTEXTS = {
    "button",
    "card",
    "component",
    "cta",
    "element",
    "interaction",
    "link",
    "module",
    "page",
    "section",
    "tbd",
    "todo",
}
WEAK_DATA_DEPENDENCY_VALUES = {
    "data",
    "event data",
    "implementation",
    "metadata",
    "n/a",
    "na",
    "none",
    "not applicable",
    "page data",
    "tbd",
    "to confirm",
    "todo",
    "unknown",
    "variable",
    "variables",
}
REPORTING_PURPOSE_RE = re.compile(
    r"(analysis|analy[sz]e|report|segment|compare|funnel|conversion|qa|debug|diagnostic|"
    r"merchandising|journey|audience|attribute|attribution|revenue|product|cart|lead|"
    r"content|search|navigation|performance|optimization|optimisation)",
    re.IGNORECASE,
)
LOW_SIGNAL_CUSTOM_EVENT_NAMES = {
    "button_click",
    "click_banner",
    "custom_event",
    "cta_click",
    "generic_click",
    "interaction",
    "link_click",
    "menu_click",
}
HIGH_CARDINALITY_GOVERNANCE_RE = re.compile(
    r"(do not register|not register|not registered|avoid registering|high[- ]cardinality|governance|"
    r"standard report|exploration only|raw value is required)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and lint a GA4 tracking-plan JSON file.")
    parser.add_argument("plan", type=Path, help="Path to the tracking-plan JSON file.")
    parser.add_argument("--schema", type=Path, default=None, help="Optional JSON schema path. Defaults to references/tracking_plan_schema.json.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument("--warnings-as-errors", action="store_true", help="Exit non-zero when warnings are present.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "tracking_plan_schema.json"


def references_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "references"


def default_piano_catalog_path() -> Path:
    return references_dir() / "piano_official_events.json"


def default_ga4_recommended_events_path() -> Path:
    return references_dir() / "official_ga4_recommended_events.json"


def default_ga4_scenario_library_path() -> Path:
    return references_dir() / "ga4_event_scenario_library.json"


def is_clearly_required_ga4_parameter(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "required"}


def load_ga4_catalog() -> dict[str, Any]:
    recommended: set[str] = set()
    recommended_required_parameters: dict[str, set[str]] = {}
    standard: set[str] = set()
    enhanced: set[str] = set()

    recommended_path = default_ga4_recommended_events_path()
    if recommended_path.exists():
        for event in load_json(recommended_path):
            if isinstance(event, dict) and event.get("event"):
                event_name = str(event["event"])
                recommended.add(event_name)
                required_parameters = {
                    str(parameter.get("name"))
                    for parameter in event.get("parameters", [])
                    if isinstance(parameter, dict)
                    and parameter.get("name")
                    and is_clearly_required_ga4_parameter(parameter.get("required"))
                }
                if required_parameters:
                    recommended_required_parameters[event_name] = required_parameters

    library_path = default_ga4_scenario_library_path()
    if library_path.exists():
        library = load_json(library_path)
        for event in library.get("standard_events", []):
            if not isinstance(event, dict) or not event.get("event"):
                continue
            name = str(event["event"])
            standard.add(name)
            group = str(event.get("group", "")).lower()
            if "enhanced" in group:
                enhanced.add(name)

    automatic = AUTOMATIC_EVENTS | (standard - enhanced)
    return {
        "recommended": recommended - ECOMMERCE_EVENTS,
        "recommended_all": recommended,
        "ecommerce": set(ECOMMERCE_EVENTS),
        "automatic": automatic,
        "enhanced": enhanced,
        "all_official": recommended | standard | set(ECOMMERCE_EVENTS),
        "recommended_required_parameters": recommended_required_parameters,
    }


def load_piano_event_catalog() -> dict[str, dict[str, Any]]:
    path = default_piano_catalog_path()
    if not path.exists():
        return {}
    catalog = load_json(path)
    events: dict[str, dict[str, Any]] = {}
    for family in catalog.get("event_families", []):
        if not isinstance(family, dict):
            continue
        family_classification = str(family.get("classification", ""))
        for event in family.get("events", []):
            if not isinstance(event, dict) or not event.get("event"):
                continue
            events[str(event["event"])] = {
                "family": family.get("family", ""),
                "classification": family_classification,
                "mandatory_properties": set(event.get("mandatory_properties", [])),
                "server_side_extra_mandatory_properties": set(event.get("server_side_extra_mandatory_properties", [])),
            }
    return events


def add_issue(issues: list[Issue], severity: str, code: str, path: str, message: str) -> None:
    issues.append(Issue(severity=severity, code=code, path=path, message=message))


def validate_schema(plan: dict[str, Any], schema_path: Path, issues: list[Issue]) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        add_issue(
            issues,
            "warning",
            "SCHEMA_VALIDATOR_MISSING",
            "dependencies",
            "Install requirements.txt to enable JSON Schema validation.",
        )
        return

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.path)):
        path = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path)
        add_issue(issues, "error", "SCHEMA_VALIDATION", path, error.message)


def values_at_keys(value: Any, target_keys: set[str], prefix: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in target_keys:
                yield path, child
            yield from values_at_keys(child, target_keys, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from values_at_keys(child, target_keys, f"{prefix}[{index}]")


def walk_keys(value: Any, prefix: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            yield path, key
            yield from walk_keys(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_keys(child, f"{prefix}[{index}]")


def check_duplicates(values: list[str], label: str, path: str, issues: list[Issue]) -> None:
    for value, count in Counter(values).items():
        if value and count > 1:
            add_issue(issues, "error", "DUPLICATE_ID", path, f"{label} '{value}' appears {count} times.")


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
            f"'{event_name}' is marked {classification} but is not in piano_official_events.json.",
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


def expected_network_mentions_event(expected_network: Any, event_name: str) -> bool:
    if not event_name or not isinstance(expected_network, list):
        return False
    text = " ".join(str(entry) for entry in expected_network)
    return event_name in text


def check_business_question(value: Any, path: str, issues: list[Issue]) -> None:
    question = str(value or "").strip()
    if not question:
        return
    normalized = question.lower().rstrip(".")
    if normalized in WEAK_BUSINESS_QUESTIONS or WEAK_BUSINESS_QUESTION_RE.search(question):
        add_issue(
            issues,
            "error",
            "EVENT_BUSINESS_QUESTION_WEAK",
            path,
            "Business question must express the analysis need or decision supported by the event, not just the implementation action to track.",
        )


def check_measurement_alignment(plan: dict[str, Any], issues: list[Issue]) -> None:
    briefs = [brief for brief in plan.get("measurement_brief", []) if isinstance(brief, dict)]
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    journey_ids = {str(brief.get("journey_id", "")) for brief in briefs if brief.get("journey_id")}
    events_by_journey: dict[str, list[dict[str, Any]]] = defaultdict(list)
    event_names_by_journey: dict[str, set[str]] = defaultdict(set)
    event_ids_by_journey: dict[str, set[str]] = defaultdict(set)

    for event_index, event in enumerate(events):
        journey_id = str(event.get("journey_id", ""))
        if journey_id:
            events_by_journey[journey_id].append(event)
            event_names_by_journey[journey_id].add(str(event.get("event_name", "")))
            event_ids_by_journey[journey_id].add(str(event.get("event_id", "")))
            if journey_id not in journey_ids:
                add_issue(
                    issues,
                    "error",
                    "EVENT_JOURNEY_UNKNOWN",
                    f"$.events[{event_index}].journey_id",
                    f"Event references unknown journey_id '{journey_id}'. Add the journey to measurement_brief or correct the event.",
                )

    for brief_index, brief in enumerate(briefs):
        journey_id = str(brief.get("journey_id", ""))
        if not journey_id:
            continue
        if not events_by_journey.get(journey_id):
            add_issue(
                issues,
                "error",
                "JOURNEY_HAS_NO_EVENTS",
                f"$.measurement_brief[{brief_index}].journey_id",
                f"Journey '{journey_id}' has no event definitions.",
            )
        covered_signals = event_names_by_journey.get(journey_id, set()) | event_ids_by_journey.get(journey_id, set())
        for signal_index, signal in enumerate(brief.get("success_signals", [])):
            signal_name = str(signal)
            if signal_name and signal_name not in covered_signals:
                add_issue(
                    issues,
                    "error",
                    "SUCCESS_SIGNAL_NOT_COVERED",
                    f"$.measurement_brief[{brief_index}].success_signals[{signal_index}]",
                    f"Success signal '{signal_name}' is not covered by an event_name or event_id in journey '{journey_id}'.",
                )


def check_measurement_strategy(plan: dict[str, Any], issues: list[Issue]) -> None:
    strategy = plan.get("measurement_strategy", {})
    if not isinstance(strategy, dict):
        return

    platforms = set(plan.get("analytics_platforms", []) if isinstance(plan.get("analytics_platforms", []), list) else [])
    journey_ids = {
        str(brief.get("journey_id", ""))
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict) and brief.get("journey_id")
    }
    selected_families = strategy.get("selected_event_families", [])
    family_ids = {
        str(family.get("family_id", ""))
        for family in selected_families
        if isinstance(family, dict) and family.get("family_id")
    }
    custom_acceptance_names = {
        str(item.get("event_name", ""))
        for item in strategy.get("custom_event_acceptance", [])
        if isinstance(item, dict) and item.get("event_name")
    }

    for index, page_role in enumerate(strategy.get("page_roles", []) if isinstance(strategy.get("page_roles", []), list) else []):
        if not isinstance(page_role, dict):
            continue
        journey_id = str(page_role.get("journey_id", ""))
        if journey_id and journey_id not in journey_ids:
            add_issue(
                issues,
                "error",
                "STRATEGY_JOURNEY_UNKNOWN",
                f"$.measurement_strategy.page_roles[{index}].journey_id",
                f"Measurement strategy references unknown journey_id '{journey_id}'.",
            )

    for index, family in enumerate(selected_families if isinstance(selected_families, list) else []):
        if not isinstance(family, dict):
            continue
        platform = str(family.get("analytics_platform", ""))
        if platforms and platform not in platforms and platform != "other":
            add_issue(
                issues,
                "error",
                "STRATEGY_PLATFORM_OUT_OF_SCOPE",
                f"$.measurement_strategy.selected_event_families[{index}].analytics_platform",
                f"Selected event family platform '{platform}' is not listed in analytics_platforms.",
            )
        reason = str(family.get("reason", "")).strip()
        if len(reason.split()) < 6:
            add_issue(
                issues,
                "error",
                "STRATEGY_EVENT_FAMILY_REASON_WEAK",
                f"$.measurement_strategy.selected_event_families[{index}].reason",
                "Selected event families need a concrete business or platform rationale.",
            )

    for index, event in enumerate(plan.get("events", []) if isinstance(plan.get("events", []), list) else []):
        if not isinstance(event, dict):
            continue
        family_id = str(event.get("business_event_family", ""))
        if family_id and family_id not in family_ids:
            add_issue(
                issues,
                "error",
                "EVENT_FAMILY_UNKNOWN",
                f"$.events[{index}].business_event_family",
                f"Event references business_event_family '{family_id}' but it is not listed in measurement_strategy.selected_event_families.",
            )
        if event.get("classification") in CUSTOM_CLASSIFICATIONS and str(event.get("event_name", "")) not in custom_acceptance_names:
            add_issue(
                issues,
                "error",
                "CUSTOM_EVENT_ACCEPTANCE_MISSING",
                f"$.measurement_strategy.custom_event_acceptance",
                f"Custom event '{event.get('event_name')}' needs a custom_event_acceptance entry with official alternatives and business rationale.",
            )

    for index, item in enumerate(strategy.get("custom_event_acceptance", []) if isinstance(strategy.get("custom_event_acceptance", []), list) else []):
        if not isinstance(item, dict):
            continue
        reason = str(item.get("business_reason", "")).strip()
        alternatives = item.get("official_alternatives_considered", [])
        if len(reason.split()) < 8 or not alternatives:
            add_issue(
                issues,
                "error",
                "CUSTOM_EVENT_ACCEPTANCE_WEAK",
                f"$.measurement_strategy.custom_event_acceptance[{index}]",
                "Custom-event acceptance entries must state a concrete business reason and official alternatives considered.",
            )


def check_not_tracked_decisions(plan: dict[str, Any], issues: list[Issue]) -> None:
    not_tracked = plan.get("not_tracked", [])
    if isinstance(not_tracked, list) and not not_tracked:
        add_issue(
            issues,
            "warning",
            "NOT_TRACKED_EMPTY",
            "$.not_tracked",
            "Reusable plans should list meaningful interactions intentionally excluded from tracking.",
        )
    for index, decision in enumerate(not_tracked if isinstance(not_tracked, list) else []):
        if not isinstance(decision, dict):
            continue
        reason = str(decision.get("reason", "")).strip()
        if reason.lower().rstrip(".") in WEAK_NOT_TRACKED_REASONS or len(reason.split()) < 5:
            add_issue(
                issues,
                "error",
                "NOT_TRACKED_REASON_WEAK",
                f"$.not_tracked[{index}].reason",
                "Not-tracked decisions need a useful analyst rationale, such as noise, privacy risk, unavailable data, duplicate signal, or lack of business actionability.",
            )


def check_event(
    event: dict[str, Any],
    index: int,
    parameter_lookup: dict[str, dict[str, Any]],
    ga4_catalog: dict[str, Any],
    piano_catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{index}]"
    event_name = event.get("event_name", "")
    classification = event.get("classification", "")
    parameters = event.get("parameters", [])
    parameter_names = set(parameter_lookup)
    data_layer = event.get("data_layer", {})
    ga4_payload = event.get("ga4_payload", {})
    privacy = event.get("privacy", {})

    check_legacy_ua_field(str(event_name), f"{base}.event_name", issues)

    if not event.get("primary_platform"):
        add_issue(issues, "error", "PRIMARY_PLATFORM_MISSING", f"{base}.primary_platform", "Every event needs primary_platform for platform-specific QA and mapping.")
    if not str(event.get("official_match", "")).strip():
        add_issue(issues, "error", "OFFICIAL_MATCH_MISSING", f"{base}.official_match", "Every event needs official_match describing the official event match or custom rationale.")
    page_or_component = str(event.get("page_or_component", "")).strip()
    if page_or_component.lower().rstrip(".") in WEAK_COMPONENT_CONTEXTS or len(page_or_component.split()) < 2:
        add_issue(
            issues,
            "error",
            "EVENT_COMPONENT_CONTEXT_WEAK",
            f"{base}.page_or_component",
            "Event page_or_component must identify the concrete page area, module, form, list, or interaction target.",
        )
    data_dependencies = event.get("data_dependencies", [])
    if not isinstance(data_dependencies, list) or not data_dependencies:
        add_issue(
            issues,
            "error",
            "EVENT_DATA_DEPENDENCIES_MISSING",
            f"{base}.data_dependencies",
            "Every event needs concrete data dependencies so developers and QA know which source values are required.",
        )
    elif any(
        str(dependency).strip().lower().rstrip(".") in WEAK_DATA_DEPENDENCY_VALUES
        or len(str(dependency).strip().split()) < 2
        for dependency in data_dependencies
    ):
        add_issue(
            issues,
            "error",
            "EVENT_DATA_DEPENDENCY_WEAK",
            f"{base}.data_dependencies",
            "Event data_dependencies must list concrete source values or systems, not generic placeholders.",
        )
    role = str(event.get("measurement_role", ""))
    if role in NON_CONVERSION_MEASUREMENT_ROLES and event.get("key_event"):
        add_issue(
            issues,
            "error",
            "KEY_EVENT_ROLE_INVALID",
            f"{base}.measurement_role",
            f"Events with measurement_role '{role}' should not be marked as key events.",
        )
    if role == "macro_conversion" and not event.get("key_event"):
        add_issue(
            issues,
            "warning",
            "MACRO_CONVERSION_NOT_KEY_EVENT",
            f"{base}.key_event",
            "Macro conversions should normally be marked as key events or explicitly justified in implementation_notes.",
        )
    if role == "macro_conversion" and event.get("priority") != "must":
        add_issue(
            issues,
            "warning",
            "MACRO_CONVERSION_PRIORITY",
            f"{base}.priority",
            "Macro conversions should normally use priority='must'.",
        )
    check_business_question(event.get("business_question"), f"{base}.business_question", issues)

    for parameter in parameters:
        check_pii_name(str(parameter), f"{base}.parameters", issues)
        check_legacy_ua_field(str(parameter), f"{base}.parameters", issues)
        if parameter in LEGACY_WRAPPER_PARAMETERS:
            add_issue(
                issues,
                "warning",
                "LEGACY_WRAPPER_PARAMETER",
                f"{base}.parameters",
                f"Parameter '{parameter}' is a legacy wrapper pattern. Prefer direct GA4 event parameters.",
            )
        if parameter.startswith("items[].") and parameter not in OFFICIAL_ITEM_PARAMETERS and parameter not in parameter_names:
            add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_NOT_DEFINED", f"{base}.parameters", f"Custom item parameter '{parameter}' must be defined in the parameter reference.")
        elif parameter not in parameter_names and not parameter.startswith("items[]."):
            add_issue(issues, "warning", "PARAMETER_NOT_DEFINED", f"{base}.parameters", f"Parameter '{parameter}' is not in the parameter reference.")

    event_key = data_layer.get("event_key")
    if event_name in LEGACY_WRAPPER_EVENT_KEYS or event_key in LEGACY_WRAPPER_EVENT_KEYS:
        add_issue(
            issues,
            "error",
            "LEGACY_WRAPPER_EVENT",
            f"{base}.data_layer.event_key",
            "Use the GA4 event name directly instead of a wrapper event such as gtm.custom_event.",
        )

    push = data_layer.get("push", {})
    if isinstance(push, dict):
        pushed_event = push.get("event")
        if pushed_event in LEGACY_WRAPPER_EVENT_KEYS:
            add_issue(
                issues,
                "error",
                "LEGACY_WRAPPER_PUSH",
                f"{base}.data_layer.push.event",
                "dataLayer push uses a wrapper event. Push the final GA4 event name directly.",
            )
        for path, key in walk_keys(push, f"{base}.data_layer.push"):
            check_pii_name(key, path, issues)
            check_legacy_ua_field(key, path, issues)

    payload_name = ga4_payload.get("event_name")
    if payload_name and payload_name != event_name:
        add_issue(issues, "error", "PAYLOAD_EVENT_MISMATCH", f"{base}.ga4_payload.event_name", f"Payload event '{payload_name}' does not match event_name '{event_name}'.")

    payload_parameters = ga4_payload.get("parameters", {}) if isinstance(ga4_payload.get("parameters"), dict) else {}
    for name in payload_parameters:
        check_pii_name(name, f"{base}.ga4_payload.parameters.{name}", issues)
        check_legacy_ua_field(name, f"{base}.ga4_payload.parameters.{name}", issues)

    if event_name in ECOMMERCE_EVENTS and classification != "recommended_ecommerce":
        add_issue(issues, "warning", "ECOMMERCE_CLASSIFICATION", f"{base}.classification", f"Official ecommerce event '{event_name}' should usually be classified as recommended_ecommerce.")
    if classification == "recommended_ecommerce" and event_name not in ECOMMERCE_EVENTS:
        add_issue(issues, "error", "INVALID_ECOMMERCE_EVENT", f"{base}.event_name", f"'{event_name}' is not an official GA4 ecommerce event.")

    if classification == "recommended_ecommerce":
        official_event_parameters = EVENT_PARAMETERS_BY_EVENT.get(event_name, set())
        for name in payload_parameters:
            metadata = parameter_lookup.get(name)
            if name not in official_event_parameters:
                if metadata is None:
                    add_issue(issues, "warning", "CUSTOM_ECOMMERCE_PARAMETER_NOT_DEFINED", f"{base}.ga4_payload.parameters.{name}", f"Custom ecommerce event parameter '{name}' must be defined in the parameter reference.")
                elif metadata.get("classification") in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                    add_issue(issues, "error", "CUSTOM_ECOMMERCE_PARAMETER_MISCLASSIFIED", f"{base}.ga4_payload.parameters.{name}", f"'{name}' is not an official parameter for {event_name}; classify it as custom_event_parameter or remove it.")
        items = ga4_payload.get("items", [])
        if not isinstance(items, list) or not items:
            add_issue(issues, "error", "ECOMMERCE_ITEMS_MISSING", f"{base}.ga4_payload.items", "Ecommerce events need an items array when product/item data is available.")
        for item_index, item in enumerate(items if isinstance(items, list) else []):
            if not isinstance(item, dict):
                continue
            if "item_id" not in item and "item_name" not in item:
                add_issue(issues, "error", "ECOMMERCE_ITEM_ID_OR_NAME", f"{base}.ga4_payload.items[{item_index}]", "Each ecommerce item needs item_id or item_name.")
            if "currency" in item:
                add_issue(issues, "error", "ITEM_SCOPE_CURRENCY", f"{base}.ga4_payload.items[{item_index}].currency", "currency is event-scoped, not item-scoped.")
            for key in item:
                parameter_name = f"items[].{key}"
                metadata = parameter_lookup.get(parameter_name)
                if parameter_name in OFFICIAL_ITEM_PARAMETERS:
                    continue
                if metadata is None:
                    add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_NOT_DEFINED", f"{base}.ga4_payload.items[{item_index}].{key}", f"Custom item parameter '{parameter_name}' must be defined in the parameter reference.")
                elif metadata.get("classification") in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                    add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", f"{base}.ga4_payload.items[{item_index}].{key}", f"'{parameter_name}' is not an official GA4 item parameter; classify it as custom_item_parameter or remove it.")
        flush_keys = set(data_layer.get("flush_keys", []))
        if "ecommerce" not in flush_keys:
            add_issue(issues, "warning", "ECOMMERCE_FLUSH_MISSING", f"{base}.data_layer.flush_keys", "Flush ecommerce before ecommerce pushes to prevent stale item data.")

    if event_name in TRANSACTION_EVENTS and "transaction_id" not in payload_parameters:
        add_issue(issues, "error", "TRANSACTION_ID_MISSING", f"{base}.ga4_payload.parameters", f"{event_name} needs transaction_id for deduplication.")
    if event_name in VALUE_EVENTS_REQUIRE_CURRENCY and "value" in payload_parameters and "currency" not in payload_parameters:
        add_issue(issues, "error", "CURRENCY_MISSING", f"{base}.ga4_payload.parameters", "currency is required when value is sent.")

    if privacy.get("pii_risk") == "high":
        add_issue(issues, "error", "HIGH_PII_RISK", f"{base}.privacy.pii_risk", "High PII risk must be resolved before plan approval.")
    cardinality_notes = f"{privacy.get('notes', '')} {event.get('implementation_notes', '')}"
    if privacy.get("cardinality_risk") == "high" and not HIGH_CARDINALITY_GOVERNANCE_RE.search(cardinality_notes):
        add_issue(issues, "warning", "HIGH_CARDINALITY_RISK", f"{base}.privacy.cardinality_risk", "High-cardinality fields should not be registered as reporting dimensions unless justified.")

    qa = event.get("qa", {})
    if not qa.get("qa_id"):
        add_issue(issues, "error", "EVENT_QA_MISSING", f"{base}.qa.qa_id", "Every testable event needs a stable qa_id.")
    if not qa.get("expected_data_layer"):
        add_issue(issues, "warning", "EXPECTED_DATALAYER_MISSING", f"{base}.qa.expected_data_layer", "QA should include expected dataLayer keys or note why none apply.")
    if not qa.get("expected_network"):
        add_issue(issues, "warning", "EXPECTED_NETWORK_MISSING", f"{base}.qa.expected_network", "QA should include expected GA4/network event and key parameters.")
    elif not expected_network_mentions_event(qa.get("expected_network"), str(event_name)):
        add_issue(
            issues,
            "error",
            "QA_EXPECTED_NETWORK_EVENT_NAME_MISSING",
            f"{base}.qa.expected_network",
            f"Event QA expected_network must mention the expected event name '{event_name}'.",
        )

    if classification in GA4_CLASSIFICATIONS and classification != "automatic" and not ga4_payload:
        add_issue(
            issues,
            "warning",
            "GA4_PAYLOAD_MISSING",
            f"{base}.ga4_payload",
            "GA4 recommended, ecommerce, and custom events should include a ga4_payload example unless the event is intentionally automatic-only.",
        )

    if event.get("primary_platform") and event.get("platform_mappings"):
        mapped_platforms = {mapping.get("platform") for mapping in event.get("platform_mappings", []) if isinstance(mapping, dict)}
        if event.get("primary_platform") not in mapped_platforms and event.get("primary_platform") != "ga4":
            add_issue(
                issues,
                "warning",
                "PRIMARY_PLATFORM_MAPPING_MISSING",
                f"{base}.platform_mappings",
                f"primary_platform is {event.get('primary_platform')} but no matching platform mapping is listed.",
            )

    for payload_index, payload in enumerate(event.get("implementation_payloads", [])):
        if not isinstance(payload, dict):
            continue
        check_legacy_ua_field(str(payload.get("event_name", "")), f"{base}.implementation_payloads[{payload_index}].event_name", issues)
        payload_data = payload.get("payload", {})
        if isinstance(payload_data, dict):
            for key in payload_data:
                check_pii_name(str(key), f"{base}.implementation_payloads[{payload_index}].payload.{key}", issues)
                check_legacy_ua_field(str(key), f"{base}.implementation_payloads[{payload_index}].payload.{key}", issues)

    check_piano_event_shape(event, index, piano_catalog, issues)
    check_ga4_event_shape(event, index, ga4_catalog, issues)
    check_custom_event_rationale(event, index, issues)

    for mapping_index, mapping in enumerate(event.get("platform_mappings", [])):
        if isinstance(mapping, dict):
            check_platform_mapping(event, index, mapping, mapping_index, piano_catalog, issues)


def validate_plan_data(plan: dict[str, Any], schema_path: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    schema_path = schema_path or default_schema_path()
    validate_schema(plan, schema_path, issues)

    parameters = plan.get("parameters", [])
    parameter_lookup = {param.get("parameter_name", ""): param for param in parameters if isinstance(param, dict)}
    ga4_catalog = load_ga4_catalog()
    piano_catalog = load_piano_event_catalog()
    events = plan.get("events", [])
    qa_cases = plan.get("qa_cases", [])
    custom_definitions = plan.get("custom_definitions", [])
    documentation_sources = plan.get("documentation_sources_checked", [])
    registered_item_custom_dimensions = {
        definition.get("parameter_name")
        for definition in custom_definitions
        if isinstance(definition, dict)
        and definition.get("scope") == "item"
        and definition.get("registration_type") == "custom_dimension"
    }
    custom_definition_keys = {
        (definition.get("parameter_name"), definition.get("scope"))
        for definition in custom_definitions
        if isinstance(definition, dict)
    }

    check_duplicates([event.get("event_id", "") for event in events if isinstance(event, dict)], "event_id", "$.events", issues)
    check_duplicates([case.get("qa_id", "") for case in qa_cases if isinstance(case, dict)], "qa_id", "$.qa_cases", issues)
    check_measurement_alignment(plan, issues)
    check_measurement_strategy(plan, issues)
    check_not_tracked_decisions(plan, issues)
    source_urls = [
        str(source.get("url", "")).lower()
        for source in documentation_sources
        if isinstance(source, dict) and source.get("source_type") == "official"
    ]
    has_ga4_events = any(isinstance(event, dict) and is_ga4_event(event) for event in events)
    has_piano_events = any(
        isinstance(event, dict)
        and (event.get("primary_platform") == "piano_analytics" or event.get("classification") in PIANO_CLASSIFICATIONS)
        for event in events
    )
    if has_ga4_events and not any(any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS["ga4"]) for url in source_urls):
        add_issue(
            issues,
            "error",
            "GA4_OFFICIAL_SOURCE_MISSING",
            "$.documentation_sources_checked",
            "GA4 plans must cite at least one official Google Analytics documentation source.",
        )
    if has_piano_events and not any(any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS["piano_analytics"]) for url in source_urls):
        add_issue(
            issues,
            "error",
            "PIANO_OFFICIAL_SOURCE_MISSING",
            "$.documentation_sources_checked",
            "Piano Analytics plans must cite at least one official Piano documentation source.",
        )

    for index, param in enumerate(parameters):
        if not isinstance(param, dict):
            continue
        name = str(param.get("parameter_name", ""))
        check_pii_name(name, f"$.parameters[{index}].parameter_name", issues)
        check_legacy_ua_field(name, f"$.parameters[{index}].parameter_name", issues)
        classification = param.get("classification")
        if should_lint_ga4_parameter_name(name, param):
            check_ga4_name(name, f"$.parameters[{index}].parameter_name", "parameter", issues)
            if name in GA4_RESERVED_PARAMETER_NAMES and classification not in {
                "ga4_auto_collected_parameter",
                "ga4_native_parameter",
                "ga4_recommended_parameter",
                "ga4_ecommerce_parameter",
                "ga4_ecommerce_item_parameter",
            }:
                add_issue(
                    issues,
                    "error",
                    "GA4_RESERVED_PARAMETER_NAME",
                    f"$.parameters[{index}].parameter_name",
                    f"'{name}' is reserved/native in GA4 and must not be used as a custom parameter.",
                )
        if name.startswith("items[]."):
            if name in OFFICIAL_ITEM_PARAMETERS:
                if classification == "custom_item_parameter":
                    add_issue(issues, "warning", "OFFICIAL_ITEM_PARAMETER_MISCLASSIFIED", f"$.parameters[{index}].classification", f"'{name}' is an official GA4 item parameter; classify it as ga4_ecommerce_item_parameter.")
            else:
                if classification in OFFICIAL_ECOMMERCE_PARAMETER_CLASSES:
                    add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_MISCLASSIFIED", f"$.parameters[{index}].classification", f"'{name}' is not an official GA4 item parameter; classify it as custom_item_parameter.")
                elif classification != "custom_item_parameter":
                    add_issue(issues, "warning", "CUSTOM_ITEM_PARAMETER_CLASSIFICATION", f"$.parameters[{index}].classification", f"'{name}' is item-scoped and non-official; use custom_item_parameter.")
                if param.get("scope") != "item":
                    add_issue(issues, "error", "CUSTOM_ITEM_PARAMETER_SCOPE", f"$.parameters[{index}].scope", f"'{name}' must use item scope.")
                if param.get("register_custom_definition") and name not in registered_item_custom_dimensions:
                    add_issue(issues, "warning", "CUSTOM_ITEM_DIMENSION_MISSING", "$.custom_definitions", f"'{name}' is marked for registration but no matching item-scoped custom dimension is listed.")
        if param.get("pii_risk") == "high":
            add_issue(issues, "error", "HIGH_PII_RISK", f"$.parameters[{index}].pii_risk", f"Parameter '{name}' has high PII risk.")
        if param.get("cardinality_risk") == "high" and param.get("register_custom_definition"):
            add_issue(issues, "warning", "HIGH_CARDINALITY_CUSTOM_DIMENSION", f"$.parameters[{index}]", f"Parameter '{name}' is high-cardinality and marked for custom definition registration.")
        reporting_purpose = str(param.get("reporting_purpose", "")).strip()
        normalized_purpose = reporting_purpose.lower().rstrip(".")
        if normalized_purpose in WEAK_REPORTING_PURPOSES or len(reporting_purpose.split()) < 5:
            add_issue(
                issues,
                "error",
                "PARAMETER_REPORTING_PURPOSE_WEAK",
                f"$.parameters[{index}].reporting_purpose",
                f"Parameter '{name}' needs a concrete reporting or analysis purpose.",
            )
        elif classification in CUSTOM_PARAMETER_CLASSIFICATIONS and not REPORTING_PURPOSE_RE.search(reporting_purpose):
            add_issue(
                issues,
                "error",
                "CUSTOM_PARAMETER_REPORTING_PURPOSE_WEAK",
                f"$.parameters[{index}].reporting_purpose",
                f"Custom parameter '{name}' must state the analysis, segmentation, QA, or optimization use it supports.",
            )
        value_rules = str(param.get("value_rules", "")).strip()
        normalized_rules = value_rules.lower().rstrip(".")
        if classification in CUSTOM_PARAMETER_CLASSIFICATIONS and (normalized_rules in WEAK_VALUE_RULES or len(value_rules.split()) < 3):
            add_issue(
                issues,
                "error",
                "CUSTOM_PARAMETER_VALUE_RULES_WEAK",
                f"$.parameters[{index}].value_rules",
                f"Custom parameter '{name}' needs concrete value rules or controlled values.",
            )
        if param.get("register_custom_definition") and (name, param.get("scope")) not in custom_definition_keys:
            add_issue(
                issues,
                "error",
                "CUSTOM_DEFINITION_MISSING",
                "$.custom_definitions",
                f"Parameter '{name}' is marked for custom definition/Data Model registration but no matching custom_definitions row exists.",
            )
        if classification == "piano_custom_property" and param.get("register_custom_definition"):
            matching_definitions = [
                definition
                for definition in custom_definitions
                if isinstance(definition, dict)
                and definition.get("parameter_name") == name
                and definition.get("scope") == param.get("scope")
            ]
            if not any(definition.get("registration_type") == "piano_data_model_property" for definition in matching_definitions):
                add_issue(
                    issues,
                    "error",
                    "PIANO_DATA_MODEL_DEFINITION_MISSING",
                    "$.custom_definitions",
                    f"Piano custom property '{name}' is marked for registration but no Piano Data Model property row is listed.",
                )

    for index, event in enumerate(events):
        if isinstance(event, dict):
            check_event(event, index, parameter_lookup, ga4_catalog, piano_catalog, issues)

    events_by_id = {event.get("event_id"): event for event in events if isinstance(event, dict)}
    events_by_name = {event.get("event_name"): event for event in events if isinstance(event, dict)}
    event_qa_ids = {event.get("qa", {}).get("qa_id") for event in events if isinstance(event, dict)}
    qa_case_ids = {case.get("qa_id") for case in qa_cases if isinstance(case, dict)}
    for event_id, event in events_by_id.items():
        if event and event.get("qa", {}).get("qa_id") not in qa_case_ids:
            add_issue(issues, "warning", "QA_CASE_MISSING", "$.qa_cases", f"Event '{event_id}' has no matching qa_cases entry.")
    for index, case in enumerate(qa_cases):
        if not isinstance(case, dict):
            continue
        event_id = case.get("event_id")
        event = events_by_id.get(event_id)
        if not event:
            add_issue(issues, "error", "QA_EVENT_NOT_FOUND", f"$.qa_cases[{index}].event_id", f"QA case references unknown event_id '{event_id}'.")
            continue
        if case.get("event_name") != event.get("event_name"):
            add_issue(issues, "error", "QA_EVENT_NAME_MISMATCH", f"$.qa_cases[{index}].event_name", "QA case event_name does not match the referenced event.")
        if case.get("qa_id") not in event_qa_ids:
            add_issue(issues, "warning", "QA_ID_NOT_ON_EVENT", f"$.qa_cases[{index}].qa_id", "QA case qa_id is not referenced by an event qa block.")
        if not expected_network_mentions_event(case.get("expected_network"), str(case.get("event_name", ""))):
            add_issue(
                issues,
                "error",
                "QA_EXPECTED_NETWORK_EVENT_NAME_MISSING",
                f"$.qa_cases[{index}].expected_network",
                f"Top-level QA expected_network must mention the expected event name '{case.get('event_name')}'.",
            )

    for index, key_event in enumerate(plan.get("key_events", []) if isinstance(plan.get("key_events", []), list) else []):
        if not isinstance(key_event, dict):
            continue
        event = events_by_name.get(key_event.get("event_name"))
        if not event:
            add_issue(
                issues,
                "error",
                "KEY_EVENT_NOT_FOUND",
                f"$.key_events[{index}].event_name",
                f"Key event '{key_event.get('event_name')}' is not defined in events.",
            )
            continue
        if event.get("measurement_role") in NON_CONVERSION_MEASUREMENT_ROLES:
            add_issue(
                issues,
                "error",
                "KEY_EVENT_ROLE_INVALID",
                f"$.key_events[{index}].event_name",
                f"Key event '{key_event.get('event_name')}' points to a {event.get('measurement_role')} event.",
            )

    return issues


def render_text(issues: list[Issue]) -> str:
    if not issues:
        return "Tracking plan validation passed with no issues."
    lines = []
    for issue in issues:
        lines.append(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    plan = load_json(args.plan)
    issues = validate_plan_data(plan, args.schema or default_schema_path())
    if args.format == "json":
        print(json.dumps([issue.__dict__ for issue in issues], indent=2, ensure_ascii=False))
    else:
        print(render_text(issues))
    has_error = any(issue.severity == "error" for issue in issues)
    has_warning = any(issue.severity == "warning" for issue in issues)
    return 1 if has_error or (args.warnings_as_errors and has_warning) else 0


if __name__ == "__main__":
    sys.exit(main())
