from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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

GA4_CLASSIFICATIONS = {"automatic", "enhanced_measurement", "recommended", "recommended_ecommerce", "custom"}
CUSTOM_CLASSIFICATIONS = {"custom"}
CUSTOM_PARAMETER_CLASSIFICATIONS = {
    "custom_event_parameter",
    "custom_item_parameter",
    "custom_user_property",
}
OFFICIAL_VERIFICATION_CLASSES = {
    "automatic",
    "enhanced_measurement",
    "recommended",
    "recommended_ecommerce",
}
OFFICIAL_PARAMETER_CLASSES = {
    "ga4_auto_collected_parameter",
    "ga4_native_parameter",
    "ga4_recommended_parameter",
    "ga4_ecommerce_parameter",
    "ga4_ecommerce_item_parameter",
}
POTENTIAL_DUPLICATE_EVENTS = {
    "page_view",
    "scroll",
    "click",
    "file_download",
    "form_start",
    "form_submit",
    "video_start",
    "video_progress",
    "video_complete",
    "search",
}
MANUAL_COLLECTION_SOURCES = {"manual_gtm", "data_layer", "gtag", "sdk", "server_side"}
WEAK_TEMPLATE_REASON_RE = re.compile(r"^(n/a|none|no|not applicable|tbd|same)$", re.I)
NON_CONVERSION_MEASUREMENT_ROLES = {"context", "diagnostic"}
OFFICIAL_SOURCE_DOMAINS = {
    "ga4": ("developers.google.com/analytics", "support.google.com/analytics"),
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
}
HIGH_CARDINALITY_GOVERNANCE_RE = re.compile(
    r"(do not register|not register|not registered|avoid registering|high[- ]cardinality|governance|"
    r"standard report|exploration only|raw value is required)",
    re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def default_schema_path() -> Path:
    return references_dir() / "schema-tracking-plan.json"


def references_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "03-rules"


def default_ga4_recommended_events_path() -> Path:
    return references_dir() / "library-ga4-recommended-events.json"


def default_ga4_scenario_library_path() -> Path:
    return references_dir() / "library-ga4-event-scenarios.json"


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
