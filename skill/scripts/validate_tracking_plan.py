from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from tracking_plan_model import (
    flatten_push_paths,
    journey_lookup,
    load_json,
    path_exists,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "references" / "schema-tracking-plan.json"
CATALOG_PATH = ROOT / "references" / "library-ga4-recommended-events.json"

GENERIC_TEXT = re.compile(
    r"^\s*(?:"
    r"(?:use|utiliser)\s+(?:the|la)\s+(?:official|officielle?)\s+definition|"
    r"value associated with(?: the event)?|valeur associ[eé]e(?: [àa] l['’]événement)?|"
    r"variable (?:used|utilis[eé]e) (?:for|pour) (?:the )?track(?:ing)?|"
    r"when applicable|lorsque applicable|"
    r"to confirm|[àa] confirmer|"
    r"tbd"
    r")\s*[.!]?\s*$",
    re.I,
)

GENERIC_TRIGGER = re.compile(
    r"^(?:on click|au clic|on page view|[àa] la vue|when the event occurs|"
    r"lorsque l['’]événement se produit|when applicable|lorsque applicable)$",
    re.I,
)

SUPPORTED_WORKBOOK_LANGUAGES = {"en", "fr"}
ASCII_SNAKE_VALUE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
RESERVED_WEB_EVENT_NAMES = {
    "ad_impression",
    "app_remove",
    "app_store_refund",
    "app_store_subscription_cancel",
    "app_store_subscription_renew",
    "click",
    "error",
    "file_download",
    "first_open",
    "first_visit",
    "form_start",
    "form_submit",
    "in_app_purchase",
    "page_view",
    "scroll",
    "session_start",
    "user_engagement",
    "view_complete",
    "video_progress",
    "video_start",
    "view_search_results",
}
RESERVED_PARAMETER_PREFIXES = ("_", "firebase_", "ga_", "google_", "gtag.")
RESERVED_EVENT_PARAMETER_NAMES = {
    "cid",
    "currency",
    "customer_id",
    "customerid",
    "dclid",
    "gclid",
    "session_id",
    "sessionid",
    "sfmc_id",
    "sid",
    "srsltid",
    "uid",
    "user_id",
    "userid",
}
RESERVED_USER_PROPERTY_NAMES = {
    "cid",
    "customer_id",
    "customerid",
    "first_open_after_install",
    "first_open_time",
    "first_visit_time",
    "google_allow_ad_personalization_signals",
    "last_advertising_id_reset",
    "last_deep_link_referrer",
    "last_gclid",
    "lifetime_user_engagement",
    "non_personalized_ads",
    "session_id",
    "session_number",
    "sessionid",
    "sfmc_id",
    "sid",
    "uid",
    "user_id",
    "userid",
}
RESERVED_ITEM_PARAMETER_NAMES = {
    "affiliation",
    "cid",
    "creative_name",
    "currency",
    "customer_id",
    "customerid",
    "item_brand",
    "item_category",
    "item_category2",
    "item_category3",
    "item_category4",
    "item_category5",
    "item_id",
    "item_list_id",
    "item_list_name",
    "item_name",
    "item_variant",
    "promotion_id",
    "promotion_name",
    "session_id",
    "sessionid",
    "sid",
    "uid",
    "user_id",
    "userid",
}


@dataclass
class Issue:
    severity: str
    code: str
    path: str
    message: str


def issue(issues: list[Issue], severity: str, code: str, path: str, message: str) -> None:
    issues.append(Issue(severity, code, path, message))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the lean human-first GA4 tracking-plan model.")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--warnings-as-errors", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def load_catalog() -> dict[str, dict[str, Any]]:
    records = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    return {str(record.get("event")): record for record in records if isinstance(record, dict) and record.get("event")}


def normalize(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def normalize_ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize(value))
    return "".join(character for character in text if not unicodedata.combining(character))


def normalize_type(value: Any) -> str:
    text = normalize(value)
    if text.startswith("array"):
        return "array"
    if text.startswith("string"):
        return "string"
    if text in {"float", "double"}:
        return "number"
    return text


def validate_schema(plan: dict[str, Any], schema_path: Path, issues: list[Issue]) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.absolute_path)):
        path = "$" + "".join(f"[{part!r}]" if isinstance(part, str) else f"[{part}]" for part in error.absolute_path)
        issue(issues, "error", "SCHEMA", path, error.message)


def check_unique_ids(plan: dict[str, Any], issues: list[Issue]) -> None:
    journey_ids = [str(item.get("journey_id", "")) for item in plan.get("journeys", []) if isinstance(item, dict)]
    if len(journey_ids) != len(set(journey_ids)):
        issue(issues, "error", "DUPLICATE_JOURNEY", "$.journeys", "Journey IDs must be unique.")
    event_names = [str(item.get("event_name", "")) for item in plan.get("events", []) if isinstance(item, dict)]
    if len(event_names) != len(set(event_names)):
        issue(issues, "error", "DUPLICATE_EVENT", "$.events", "Event names must be unique.")


def check_document(plan: dict[str, Any], issues: list[Issue]) -> None:
    language = str(plan.get("document", {}).get("language", "")).lower()
    base_language = language.split("-", 1)[0]
    if base_language not in SUPPORTED_WORKBOOK_LANGUAGES:
        issue(
            issues,
            "error",
            "UNSUPPORTED_WORKBOOK_LANGUAGE",
            "$.document.language",
            "The default workbook currently supports English and French language tags only.",
        )


def check_human_text(value: Any, path: str, label: str, issues: list[Issue]) -> None:
    text = " ".join(str(value or "").split()).strip()
    code_label = label.upper()
    if not text:
        issue(issues, "error", f"{code_label}_MISSING", path, f"{label.replace('_', ' ').title()} is required.")
    elif GENERIC_TEXT.search(text):
        issue(issues, "error", f"{code_label}_GENERIC", path, "Replace generic filler with concrete official or official-like wording.")


def check_custom_decision(
    value: Any,
    path: str,
    issues: list[Issue],
) -> None:
    if not isinstance(value, dict):
        return
    for field in ("business_need", "official_candidate", "why_not_fit"):
        check_human_text(
            value.get(field),
            f"{path}.{field}",
            f"custom_{field}",
            issues,
        )


def catalog_parameters(record: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(parameter.get("name")), str(parameter.get("scope", "event"))): parameter
        for parameter in record.get("parameters", [])
        if isinstance(parameter, dict) and parameter.get("name")
    }


OFFICIAL_ANALYSIS_ANCHORS: dict[str, tuple[tuple[str, str], ...]] = {
    # These optional official parameters express the defining choice made at
    # the corresponding step. Omitting them makes the event materially less
    # useful even though the collection protocol permits omission.
    "add_payment_info": (("payment_type", "event"),),
    "add_shipping_info": (("shipping_tier", "event"),),
}


def check_official_event(
    plan: dict[str, Any],
    event: dict[str, Any],
    event_index: int,
    catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    base = f"$.events[{event_index}]"
    if name in RESERVED_WEB_EVENT_NAMES:
        issue(
            issues,
            "error",
            "RESERVED_OR_AUTOMATIC_EVENT",
            f"{base}.event_name",
            (f"'{name}' is reserved or belongs to automatic/enhanced web measurement and must not appear as a manual tracking-plan row."),
        )
    record = catalog.get(name)
    if classification == "custom" and record:
        issue(
            issues,
            "error",
            "CUSTOM_EVENT_IS_OFFICIAL",
            f"{base}.classification",
            f"'{name}' exists in the official recommended-event catalog; classify and assess it as official first.",
        )
    if classification not in {"official", "official_ecommerce"}:
        return
    source = event.get("official_source", {})
    if "google.com" not in str(source.get("url", "")).lower():
        issue(issues, "error", "OFFICIAL_EVENT_SOURCE", f"{base}.official_source.url", "Use a current official Google source.")
    if not record:
        issue(
            issues,
            "warning",
            "OFFICIAL_EVENT_NOT_IN_LOCAL_CATALOG",
            f"{base}.event_name",
            "The event is not in the bundled recommended-event catalog; verify the supplied official source live.",
        )
        return
    if source.get("wording_origin") == "exact" and normalize(event.get("definition")) != normalize(record.get("description")):
        issue(
            issues,
            "error",
            "OFFICIAL_EVENT_WORDING",
            f"{base}.definition",
            "Exact official wording must match the selected event's current official definition.",
        )
    official_text = normalize(source.get("official_text"))
    if official_text != normalize(record.get("description")):
        issue(
            issues,
            "error",
            "OFFICIAL_EVENT_SOURCE_TEXT",
            f"{base}.official_source.official_text",
            ("Store the exact current official event definition internally, including when the visible definition is a faithful translation."),
        )
    selected = {(str(item.get("name")), str(item.get("scope", "event"))) for item in event.get("parameters", []) if isinstance(item, dict)}
    prescribed = catalog_parameters(record)
    for key, parameter in prescribed.items():
        required = normalize(parameter.get("required"))
        if required == "yes" and key not in selected:
            issue(
                issues,
                "error",
                "OFFICIAL_REQUIRED_PARAMETER_MISSING",
                f"{base}.parameters",
                f"Required official parameter '{key[0]}' ({key[1]} scope) is missing.",
            )
    for key in OFFICIAL_ANALYSIS_ANCHORS.get(name, ()):
        if key not in selected:
            issue(
                issues,
                "error",
                "OFFICIAL_ANALYSIS_ANCHOR_MISSING",
                f"{base}.parameters",
                (
                    f"Include official parameter '{key[0]}' ({key[1]} scope): it captures the defining "
                    f"choice made when '{name}' is emitted. Preserve its official optional/conditional semantics."
                ),
            )
    selected_names = {name for name, _scope in selected}
    if "value" in selected_names and ("currency", "event") in prescribed and ("currency", "event") not in selected:
        issue(issues, "error", "CURRENCY_REQUIRED_WITH_VALUE", f"{base}.parameters", "Include event-level currency when value is sent.")
    if ("items", "event") in selected:
        item_names = {name for name, scope in selected if scope == "item"}
        if not {"item_id", "item_name"}.intersection(item_names):
            issue(issues, "error", "ITEM_IDENTITY_MISSING", f"{base}.parameters", "Items require item_id or item_name at item scope.")
    if name == "purchase":
        customer_type = next(
            (
                parameter
                for parameter in event.get("parameters", [])
                if isinstance(parameter, dict) and parameter.get("name") == "customer_type" and parameter.get("scope") == "event"
            ),
            None,
        )
        if customer_type is None:
            issue(
                issues,
                "error",
                "PURCHASE_CUSTOMER_TYPE_MISSING",
                f"{base}.parameters",
                ("Include official customer_type as a conditional purchase parameter, using new or returning only when classification is reliable."),
            )
        else:
            if customer_type.get("requirement") != "conditional":
                issue(
                    issues,
                    "error",
                    "PURCHASE_CUSTOMER_TYPE_REQUIREMENT",
                    f"{base}.parameters",
                    "customer_type must be conditional because uncertain orders must omit it.",
                )
            if customer_type.get("allowed_values") != ["new", "returning"]:
                issue(
                    issues,
                    "error",
                    "PURCHASE_CUSTOMER_TYPE_VALUES",
                    f"{base}.parameters",
                    "customer_type must exhaust the official values in this order: new, returning.",
                )
            if customer_type.get("value_mode") != "official_enum":
                issue(
                    issues,
                    "error",
                    "PURCHASE_CUSTOMER_TYPE_VALUE_MODE",
                    f"{base}.parameters",
                    "customer_type uses the prescribed official enum, not a localized controlled domain.",
                )


def check_parameter(
    plan: dict[str, Any],
    event: dict[str, Any],
    event_index: int,
    parameter: dict[str, Any],
    parameter_index: int,
    catalog_record: dict[str, Any] | None,
    issues: list[Issue],
) -> None:
    base = f"$.events[{event_index}].parameters[{parameter_index}]"
    name = str(parameter.get("name", ""))
    scope = str(parameter.get("scope", "event"))
    classification = str(parameter.get("classification", ""))
    path = str(parameter.get("data_layer_path", ""))
    destination = str(parameter.get("destination", ""))
    expected_scope = {
        "ga4_event_parameter": "event",
        "ga4_item_parameter": "item",
        "ga4_user_property": "user",
        "ga4_user_id": "user",
    }.get(destination)
    if expected_scope and scope != expected_scope:
        issue(
            issues,
            "error",
            "SCOPE_DESTINATION_MISMATCH",
            f"{base}.destination",
            f"Destination {destination} requires {expected_scope} scope, not {scope}.",
        )
    if name == "user_id":
        if destination != "ga4_user_id" or scope != "user" or classification != "implementation":
            issue(
                issues,
                "error",
                "USER_ID_DESTINATION",
                base,
                ("user_id must be user-scope implementation context mapped only to the GA4 User-ID configuration setting."),
            )
    elif destination == "ga4_user_id":
        issue(
            issues,
            "error",
            "USER_ID_NAME",
            f"{base}.name",
            "Only the reserved user_id field can use the ga4_user_id destination.",
        )
    final_key = path.rsplit(".", 1)[-1].replace("[]", "")
    if name and final_key and name != final_key:
        issue(
            issues,
            "error",
            "PARAMETER_PATH_NAME_MISMATCH",
            f"{base}.data_layer_path",
            f"The final dataLayer key '{final_key}' must match parameter name '{name}'.",
        )
    check_human_text(parameter.get("definition"), f"{base}.definition", "parameter_definition", issues)
    check_human_text(parameter.get("value_rule"), f"{base}.value_rule", "value_rule", issues)
    if parameter.get("requirement") == "conditional" and not str(parameter.get("condition", "")).strip():
        issue(issues, "error", "CONDITION_MISSING", f"{base}.condition", "A conditional parameter needs a separate concrete condition.")
    allowed = parameter.get("allowed_values")
    value_refs = parameter.get("value_evidence_refs", [])
    example = parameter.get("example")
    value_mode = str(parameter.get("value_mode", ""))
    document_language = str(plan.get("document", {}).get("language", "")).lower()
    if value_mode == "controlled_semantic":
        value_language = str(parameter.get("value_language", "")).lower()
        if value_language != document_language:
            issue(
                issues,
                "error",
                "CONTROLLED_VALUE_LANGUAGE",
                f"{base}.value_language",
                "Controlled semantic values must use the selected workbook language.",
            )
        controlled_values = list(allowed or [])
        if not controlled_values and isinstance(example, str):
            controlled_values = [example]
        for value in controlled_values:
            if isinstance(value, str) and not ASCII_SNAKE_VALUE.fullmatch(value):
                issue(
                    issues,
                    "error",
                    "CONTROLLED_VALUE_FORMAT",
                    f"{base}.allowed_values",
                    (f"Controlled value '{value}' must be lowercase ASCII snake_case in the workbook language."),
                )
    expected_value_mode = {
        "array": "structured",
        "object": "structured",
        "number": "numeric",
        "integer": "numeric",
        "boolean": "boolean",
    }.get(str(parameter.get("type", "")))
    if expected_value_mode and value_mode != expected_value_mode:
        issue(
            issues,
            "error",
            "VALUE_MODE_TYPE_MISMATCH",
            f"{base}.value_mode",
            f"Type '{parameter.get('type')}' requires value_mode '{expected_value_mode}'.",
        )
    if allowed and not value_refs and not (classification == "official" and name == "customer_type" and allowed == ["new", "returning"]):
        issue(
            issues,
            "error",
            "FINITE_VALUE_EVIDENCE_MISSING",
            f"{base}.value_evidence_refs",
            "A finite value domain must reference its project evidence record unless it is the prescribed customer_type enum.",
        )
    if destination == "ga4_user_property":
        if len(name) > 24:
            issue(
                issues,
                "error",
                "USER_PROPERTY_NAME_LIMIT",
                f"{base}.name",
                "GA4 user property names must not exceed 24 characters.",
            )
        if isinstance(example, str) and len(example) > 36:
            issue(
                issues,
                "error",
                "USER_PROPERTY_VALUE_LIMIT",
                f"{base}.example",
                "GA4 user property values must not exceed 36 characters.",
            )
    if destination == "ga4_user_id" and isinstance(example, str) and len(example) > 256:
        issue(
            issues,
            "error",
            "USER_ID_VALUE_LIMIT",
            f"{base}.example",
            "GA4 User-ID values must not exceed 256 characters.",
        )
    if destination in {"ga4_event_parameter", "ga4_item_parameter"} and isinstance(example, str):
        value_limit = {
            "page_title": 300,
            "page_referrer": 420,
            "page_location": 1000,
        }.get(name, 100)
        if len(example) > value_limit:
            issue(
                issues,
                "error",
                "PARAMETER_VALUE_LIMIT",
                f"{base}.example",
                f"GA4 limits the example value for {name} to {value_limit} characters.",
            )
    if isinstance(allowed, list) and allowed and not isinstance(example, (dict, list)) and example not in allowed:
        issue(issues, "error", "EXAMPLE_OUTSIDE_ALLOWED_VALUES", f"{base}.example", "The example must belong to the exhaustive allowed values.")
    if not path_exists(event.get("data_layer", {}).get("push", {}), path):
        issue(
            issues,
            "error",
            "PARAMETER_NOT_IN_DATALAYER",
            f"{base}.data_layer_path",
            "Every selected parameter must appear in the event's complete dataLayer example.",
        )
    prescribed = catalog_parameters(catalog_record) if catalog_record else {}
    official = prescribed.get((name, scope))
    if classification == "official":
        if catalog_record and not official:
            issue(
                issues,
                "error",
                "OFFICIAL_PARAMETER_NOT_PRESCRIBED",
                f"{base}.classification",
                f"'{name}' is not an official {scope}-scope parameter for this selected event; classify it as custom if justified.",
            )
        if official:
            if normalize_type(parameter.get("type")) != normalize_type(official.get("type")):
                issue(
                    issues,
                    "error",
                    "OFFICIAL_PARAMETER_TYPE",
                    f"{base}.type",
                    f"Use official type '{official.get('type')}'.",
                )
            source = parameter.get("official_source", {})
            if normalize(source.get("official_text")) != normalize(official.get("description")):
                issue(
                    issues,
                    "error",
                    "OFFICIAL_PARAMETER_SOURCE_TEXT",
                    f"{base}.official_source.official_text",
                    ("Store the exact current official parameter-row definition internally, including for faithful translations."),
                )
            if source.get("wording_origin") == "exact" and normalize(parameter.get("definition")) != normalize(official.get("description")):
                issue(
                    issues,
                    "error",
                    "OFFICIAL_PARAMETER_WORDING",
                    f"{base}.definition",
                    "Exact official wording must match the selected event's current parameter-row definition.",
                )
            if name == "index" and scope == "item":
                rule = normalize_ascii(parameter.get("value_rule"))
                if not re.search(r"(?:^|\D)0(?:\D|$)|\bzero\b", rule):
                    issue(
                        issues,
                        "error",
                        "INDEX_ZERO_BASE_MISSING",
                        f"{base}.value_rule",
                        "The official ecommerce implementation convention is zero-based: the first item uses index 0.",
                    )
                if re.search(r"(?:commence|start|base|premier|first)[^.!;]{0,40}\b1\b", rule):
                    issue(
                        issues,
                        "error",
                        "INDEX_ONE_BASED",
                        f"{base}.value_rule",
                        "index must not be described as one-based.",
                    )
            if name == "value" and scope == "event" and event.get("classification") == "official_ecommerce":
                rule = normalize_ascii(parameter.get("value_rule"))
                concepts = {
                    "price": ("price", "prix"),
                    "quantity": ("quantity", "quantite"),
                    "shipping": ("shipping", "livraison", "expedition"),
                    "tax": ("tax", "taxe", "tva"),
                }
                missing = [concept for concept, terms in concepts.items() if not any(term in rule for term in terms)]
                if missing:
                    issue(
                        issues,
                        "error",
                        "ECOMMERCE_VALUE_RULE_INCOMPLETE",
                        f"{base}.value_rule",
                        ("Define value as the sum of price * quantity and state that shipping and tax are excluded. Missing concepts: " + ", ".join(missing)),
                    )
    elif classification == "custom" and official:
        issue(
            issues,
            "error",
            "CUSTOM_PARAMETER_IS_OFFICIAL",
            f"{base}.classification",
            f"'{name}' is already an official {scope}-scope parameter for this event.",
        )
    if classification == "custom":
        check_custom_decision(parameter.get("custom_decision"), f"{base}.custom_decision", issues)
        reserved_names = {
            "event": RESERVED_EVENT_PARAMETER_NAMES,
            "item": RESERVED_ITEM_PARAMETER_NAMES,
            "user": RESERVED_USER_PROPERTY_NAMES,
        }.get(scope, set())
        if name in reserved_names or name.startswith(RESERVED_PARAMETER_PREFIXES):
            issue(
                issues,
                "error",
                "CUSTOM_PARAMETER_RESERVED_NAME",
                f"{base}.name",
                (f"'{name}' is reserved for GA4 at {scope} scope. Use the official field and destination or choose a non-reserved custom name."),
            )
    if classification == "implementation" and destination not in {
        "implementation_only",
        "ga4_user_id",
        "other",
    }:
        issue(
            issues,
            "error",
            "IMPLEMENTATION_DESTINATION",
            f"{base}.destination",
            ("An implementation parameter must remain implementation-only, map to the official User-ID setting, or target another explicit destination."),
        )


def check_event(
    plan: dict[str, Any],
    event: dict[str, Any],
    index: int,
    catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{index}]"
    name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    if classification in {"automatic", "enhanced_measurement"}:
        issue(issues, "error", "NON_MANUAL_CLASSIFICATION", f"{base}.classification", "The tracking plan contains manually implemented measurement only.")
    if classification == "custom":
        check_custom_decision(event.get("custom_decision"), f"{base}.custom_decision", issues)
    check_human_text(event.get("definition"), f"{base}.definition", "event_definition", issues)
    trigger = " ".join(str(event.get("trigger", "")).split()).strip()
    check_human_text(trigger, f"{base}.trigger", "trigger", issues)
    if GENERIC_TRIGGER.fullmatch(trigger):
        issue(issues, "error", "TRIGGER_GENERIC", f"{base}.trigger", "State the concrete action or state and firing moment.")
    known_journeys = journey_lookup(plan)
    for journey_id in event.get("journey_ids", []):
        if str(journey_id) not in known_journeys:
            issue(issues, "error", "UNKNOWN_JOURNEY", f"{base}.journey_ids", f"Unknown journey '{journey_id}'.")
    push = event.get("data_layer", {}).get("push", {})
    if classification == "context":
        if "event" in push:
            issue(issues, "error", "CONTEXT_HAS_EVENT", f"{base}.data_layer.push.event", "A context push must not create a GTM Custom Event trigger.")
    elif push.get("event") != name:
        issue(
            issues,
            "error",
            "EVENT_PUSH_MISMATCH",
            f"{base}.data_layer.push.event",
            f'Top-level "event" must equal "{name}".',
        )
    parameters = [item for item in event.get("parameters", []) if isinstance(item, dict)]
    paths = [str(item.get("data_layer_path", "")) for item in parameters]
    if len(paths) != len(set(paths)):
        issue(issues, "error", "DUPLICATE_PARAMETER_PATH", f"{base}.parameters", "Parameter dataLayer paths must be unique inside an event.")
    parameter_keys = [(str(item.get("name", "")), str(item.get("scope", ""))) for item in parameters]
    if len(parameter_keys) != len(set(parameter_keys)):
        issue(
            issues,
            "error",
            "DUPLICATE_PARAMETER_NAME_SCOPE",
            f"{base}.parameters",
            "Parameter name and scope pairs must be unique inside an event.",
        )
    ga4_event_parameter_count = sum(item.get("scope") == "event" and item.get("destination") == "ga4_event_parameter" for item in parameters)
    if ga4_event_parameter_count > 25:
        issue(
            issues,
            "error",
            "EVENT_PARAMETER_COLLECTION_LIMIT",
            f"{base}.parameters",
            (f"The event sends {ga4_event_parameter_count} event parameters; GA4 collects at most 25 per event."),
        )
    custom_item_parameter_count = sum(
        item.get("scope") == "item" and item.get("classification") == "custom" and item.get("destination") == "ga4_item_parameter" for item in parameters
    )
    if custom_item_parameter_count > 27:
        issue(
            issues,
            "error",
            "ITEM_PARAMETER_COLLECTION_LIMIT",
            f"{base}.parameters",
            (f"The event sends {custom_item_parameter_count} custom item parameters; GA4 collects at most 27 per ecommerce event."),
        )
    bound_paths = set(paths)
    unbound = sorted(flatten_push_paths(push) - bound_paths)
    if unbound:
        issue(
            issues,
            "error",
            "UNBOUND_DATALAYER_FIELDS",
            f"{base}.data_layer.push",
            "Every pushed field must belong to this event specification. Missing bindings: " + ", ".join(unbound),
        )
    check_official_event(plan, event, index, catalog, issues)
    record = catalog.get(name)
    for parameter_index, parameter in enumerate(event.get("parameters", [])):
        if isinstance(parameter, dict):
            check_parameter(plan, event, index, parameter, parameter_index, record, issues)


def check_datalayer_convention(
    plan: dict[str, Any],
    issues: list[Issue],
) -> None:
    convention = plan.get("data_layer_convention", {})
    wrappers = convention.get("wrappers", {})
    if not isinstance(wrappers, dict):
        return
    event_key = str(convention.get("event_key", "event"))
    declared_wrappers = {str(value) for value in wrappers.values() if isinstance(value, str) and value}
    page_wrapper = str(wrappers.get("page", ""))
    event_wrapper = str(wrappers.get("event", ""))
    ecommerce_wrapper = str(wrappers.get("ecommerce", ""))
    user_wrapper = str(wrappers.get("user", ""))

    for event_index, event in enumerate(plan.get("events", [])):
        if not isinstance(event, dict):
            continue
        base = f"$.events[{event_index}]"
        classification = str(event.get("classification", ""))
        push = event.get("data_layer", {}).get("push", {})
        if not isinstance(push, dict):
            continue
        unknown_top_level = sorted(str(key) for key in push if str(key) != event_key and str(key) not in declared_wrappers)
        if unknown_top_level:
            issue(
                issues,
                "error",
                "UNDECLARED_DATALAYER_WRAPPER",
                f"{base}.data_layer.push",
                "Top-level push keys are not declared by the dataLayer convention: " + ", ".join(unknown_top_level),
            )
        clear_values = event.get("data_layer", {}).get("clear", [])
        invalid_clear = sorted(str(value) for value in clear_values if str(value) not in declared_wrappers)
        if invalid_clear:
            issue(
                issues,
                "error",
                "UNDECLARED_DATALAYER_CLEAR",
                f"{base}.data_layer.clear",
                "Only declared wrappers may be cleared: " + ", ".join(invalid_clear),
            )

        event_parameter_destinations = {
            "ga4_event_parameter",
            "ga4_item_parameter",
        }
        has_ecommerce_payload = any(
            isinstance(parameter, dict) and parameter.get("destination") in event_parameter_destinations for parameter in event.get("parameters", [])
        )
        if classification == "official_ecommerce" and has_ecommerce_payload and ecommerce_wrapper not in push:
            issue(
                issues,
                "error",
                "ECOMMERCE_WRAPPER_MISSING",
                f"{base}.data_layer.push",
                (f"Official ecommerce event '{event.get('event_name')}' must place its GA4 ecommerce payload under '{ecommerce_wrapper}'."),
            )

        for parameter_index, parameter in enumerate(event.get("parameters", [])):
            if not isinstance(parameter, dict):
                continue
            path = str(parameter.get("data_layer_path", ""))
            prefix = path.split(".", 1)[0].replace("[]", "")
            destination = str(parameter.get("destination", ""))
            expected_wrapper = ""
            if destination in {"ga4_user_property", "ga4_user_id"}:
                expected_wrapper = user_wrapper
            elif destination in event_parameter_destinations:
                expected_wrapper = ecommerce_wrapper if classification == "official_ecommerce" else event_wrapper
            elif destination == "implementation_only":
                if prefix not in declared_wrappers:
                    expected_wrapper = page_wrapper
            if expected_wrapper and prefix != expected_wrapper:
                issue(
                    issues,
                    "error",
                    "DATALAYER_WRAPPER_MISMATCH",
                    f"{base}.parameters[{parameter_index}].data_layer_path",
                    (f"Parameter '{parameter.get('name')}' must use wrapper '{expected_wrapper}' for destination '{destination}', not '{prefix}'."),
                )


def check_plan_event_coherence(
    plan: dict[str, Any],
    issues: list[Issue],
) -> None:
    """Check objective event-purpose and exact-trigger coherence signals."""
    candidates: list[tuple[int, str, str, set[str]]] = []
    for event_index, event in enumerate(plan.get("events", [])):
        if not isinstance(event, dict) or event.get("classification") == "context":
            continue
        base = f"$.events[{event_index}]"
        business_question = " ".join(str(event.get("business_question", "")).split()).strip()
        if business_question:
            check_human_text(
                business_question,
                f"{base}.business_question",
                "business_question",
                issues,
            )
        else:
            issue(
                issues,
                "error",
                "EVENT_PURPOSE_MISSING",
                f"{base}.business_question",
                ("Record the concrete analysis question or decision this non-context event supports. Keep it internal to the canonical model."),
            )
        trigger = normalize(event.get("trigger"))
        journeys = {str(journey_id) for journey_id in event.get("journey_ids", []) if str(journey_id)}
        if trigger:
            candidates.append((event_index, str(event.get("event_name", "")), trigger, journeys))

    for left_index, left_name, left_trigger, left_journeys in candidates:
        for right_index, right_name, right_trigger, right_journeys in candidates:
            if right_index <= left_index:
                continue
            shared_journeys = sorted(left_journeys & right_journeys)
            if left_trigger != right_trigger or not shared_journeys:
                continue
            issue(
                issues,
                "warning",
                "POTENTIAL_DUPLICATE_EVENT_TRIGGER",
                f"$.events[{right_index}].trigger",
                (
                    f"Events '{left_name}' and '{right_name}' use the same "
                    "trigger in shared journey(s): "
                    f"{', '.join(shared_journeys)}. Reconcile them or retain "
                    "both only when their purposes and semantics are distinct."
                ),
            )


def check_core_context_and_user_id(
    plan: dict[str, Any],
    issues: list[Issue],
) -> None:
    page_contexts: set[int] = set()
    user_contexts: set[int] = set()
    user_id_occurrences: list[tuple[int, dict[str, Any]]] = []
    event_names: set[str] = set()
    for event_index, event in enumerate(plan.get("events", [])):
        if not isinstance(event, dict):
            continue
        event_names.add(str(event.get("event_name", "")))
        if event.get("classification") != "context":
            for parameter in event.get("parameters", []):
                if isinstance(parameter, dict) and parameter.get("destination") == "ga4_user_id":
                    user_id_occurrences.append((event_index, parameter))
            continue
        paths = {str(parameter.get("data_layer_path", "")) for parameter in event.get("parameters", []) if isinstance(parameter, dict)}
        if any(path.startswith("page.") for path in paths):
            page_contexts.add(event_index)
        if any(path.startswith("user.") for path in paths):
            user_contexts.add(event_index)
        for parameter in event.get("parameters", []):
            if isinstance(parameter, dict) and parameter.get("destination") == "ga4_user_id":
                user_id_occurrences.append((event_index, parameter))

    if page_contexts and user_contexts and len(page_contexts | user_contexts) > 1:
        issue(
            issues,
            "error",
            "CORE_CONTEXT_SPLIT",
            "$.events",
            ("Reusable page and user state must share one core context push, not separate page-context and user-context events."),
        )

    authentication_exists = bool(event_names & {"login", "sign_up"})
    if authentication_exists and not user_id_occurrences:
        issue(
            issues,
            "error",
            "AUTHENTICATION_USER_ID_MISSING",
            "$.events",
            ("Authenticated journeys require user.user_id in the core context, mapped to the GA4 User-ID configuration setting."),
        )
    for event_index, parameter in user_id_occurrences:
        event = plan.get("events", [])[event_index]
        if not isinstance(event, dict) or event.get("classification") != "context":
            issue(
                issues,
                "error",
                "USER_ID_NOT_IN_CONTEXT",
                f"$.events[{event_index}]",
                "user_id belongs in the core context push, not an event push.",
            )
            continue
        if parameter.get("data_layer_path") != "user.user_id":
            issue(
                issues,
                "error",
                "USER_ID_PATH",
                f"$.events[{event_index}].parameters",
                "Use user.user_id as the canonical dataLayer path.",
            )
        if event_index not in page_contexts:
            issue(
                issues,
                "error",
                "USER_ID_CORE_CONTEXT",
                f"$.events[{event_index}]",
                "The User-ID setting must share the core push with page context.",
            )
        source_url = str(parameter.get("official_source", {}).get("url", ""))
        if "/analytics/devguides/collection/ga4/user-id" not in source_url:
            issue(
                issues,
                "error",
                "USER_ID_OFFICIAL_SOURCE",
                f"$.events[{event_index}].parameters",
                "Resolve User-ID handling from the current official GA4 User-ID documentation.",
            )


def check_plan_parameter_consistency_and_budgets(
    plan: dict[str, Any],
    issues: list[Issue],
) -> None:
    semantics: dict[tuple[str, str], dict[str, Any]] = {}
    custom_event_definitions: set[str] = set()
    custom_item_definitions: set[str] = set()
    user_properties: set[str] = set()
    for event_index, event in enumerate(plan.get("events", [])):
        if not isinstance(event, dict):
            continue
        for parameter in event.get("parameters", []):
            if not isinstance(parameter, dict):
                continue
            name = str(parameter.get("name", ""))
            scope = str(parameter.get("scope", ""))
            parameter_type = str(parameter.get("type", ""))
            destination = str(parameter.get("destination", ""))
            key = (name, scope)
            signature = {
                "type": parameter_type,
                "destination": destination,
                "classification": str(parameter.get("classification", "")),
                "definition": normalize(parameter.get("definition")),
                "value_rule": normalize(parameter.get("value_rule")),
                "allowed_values": {json.dumps(value, ensure_ascii=False, sort_keys=True) for value in parameter.get("allowed_values", [])},
                "has_custom_decision": isinstance(parameter.get("custom_decision"), dict),
            }
            previous = semantics.get(key)
            if previous is None:
                semantics[key] = signature
            else:
                if previous["type"] != signature["type"] or previous["destination"] != signature["destination"]:
                    issue(
                        issues,
                        "error",
                        "PARAMETER_SEMANTIC_CONFLICT",
                        f"$.events[{event_index}].parameters",
                        (f"Parameter {name} at {scope} scope has inconsistent type or destination across events."),
                    )
                if previous["classification"] != signature["classification"]:
                    fallback_pair = {previous["classification"], signature["classification"]} == {"official", "custom"}
                    justified_fallback = fallback_pair and (
                        previous["has_custom_decision"] or signature["has_custom_decision"]
                    )
                    if not justified_fallback:
                        issue(
                            issues,
                            "warning",
                            "PARAMETER_CLASSIFICATION_VARIATION",
                            f"$.events[{event_index}].parameters",
                            (f"Parameter {name} at {scope} scope changes classification across events; confirm it remains one semantic concept."),
                        )
                if previous["value_rule"] != signature["value_rule"]:
                    issue(
                        issues,
                        "warning",
                        "PARAMETER_VALUE_RULE_VARIATION",
                        f"$.events[{event_index}].parameters",
                        (f"Parameter {name} at {scope} scope uses different value rules across events. Use one compatible rule or a different name."),
                    )
                if previous["allowed_values"] and signature["allowed_values"] and previous["allowed_values"] != signature["allowed_values"]:
                    issue(
                        issues,
                        "error",
                        "PARAMETER_VALUE_DOMAIN_CONFLICT",
                        f"$.events[{event_index}].parameters",
                        (f"Parameter {name} at {scope} scope has incompatible exhaustive value domains across events."),
                    )
                if previous["classification"] != "official" and signature["classification"] != "official" and previous["definition"] != signature["definition"]:
                    issue(
                        issues,
                        "error",
                        "PARAMETER_DEFINITION_CONFLICT",
                        f"$.events[{event_index}].parameters",
                        (f"Parameter {name} at {scope} scope has incompatible definitions across events."),
                    )
            if destination == "ga4_user_property":
                user_properties.add(name)
            if parameter.get("classification") == "custom":
                if destination == "ga4_event_parameter":
                    custom_event_definitions.add(name)
                elif destination == "ga4_item_parameter":
                    custom_item_definitions.add(name)

    if len(user_properties) > 25:
        issue(
            issues,
            "error",
            "USER_PROPERTY_COLLECTION_LIMIT",
            "$.events",
            (f"The plan defines {len(user_properties)} user properties; a standard GA4 property collects at most 25."),
        )
    if len(custom_event_definitions) > 50:
        issue(
            issues,
            "warning",
            "EVENT_CUSTOM_DEFINITION_BUDGET",
            "$.events",
            (
                f"The plan contains {len(custom_event_definitions)} distinct "
                "custom event parameters, above the standard 50 event-scoped "
                "custom-dimension budget."
            ),
        )
    if len(custom_item_definitions) > 10:
        issue(
            issues,
            "warning",
            "ITEM_CUSTOM_DEFINITION_BUDGET",
            "$.events",
            (f"The plan contains {len(custom_item_definitions)} distinct custom item parameters, above the standard 10 item-scoped custom-dimension budget."),
        )


def validate_plan(plan: dict[str, Any], schema_path: Path = DEFAULT_SCHEMA) -> list[Issue]:
    issues: list[Issue] = []
    validate_schema(plan, schema_path, issues)
    check_document(plan, issues)
    check_unique_ids(plan, issues)
    catalog = load_catalog()
    for index, event in enumerate(plan.get("events", [])):
        if isinstance(event, dict):
            check_event(plan, event, index, catalog, issues)
    check_datalayer_convention(plan, issues)
    check_plan_event_coherence(plan, issues)
    check_core_context_and_user_id(plan, issues)
    check_plan_parameter_consistency_and_budgets(plan, issues)
    return issues


def render_text(issues: list[Issue]) -> str:
    return "\n".join(f"{item.severity.upper()} {item.code} {item.path}: {item.message}" for item in issues)


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.plan)
        issues = validate_plan(plan, args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(item) for item in issues], indent=2, ensure_ascii=False))
    elif issues:
        print(render_text(issues))
    else:
        print("Tracking plan is valid.")
    has_error = any(item.severity == "error" for item in issues)
    has_warning = any(item.severity == "warning" for item in issues)
    return int(has_error or (args.warnings_as_errors and has_warning))


if __name__ == "__main__":
    raise SystemExit(main())
