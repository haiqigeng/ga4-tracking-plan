from __future__ import annotations

import re
from typing import Any

from tracking_plan_validation_model import Issue, add_issue

NAVIGATION_EVENTS = {"header_click", "menu_click", "submenu_click", "footer_click"}
NAVIGATION_PARAMETERS = {"link_name", "link_url", "navigation_group"}
PAYMENT_FAILURE_EVENTS = {"payment_error", "checkout_error"}
PAYMENT_FAILURE_PARAMETERS = {"journey_step", "error_type", "error_code", "payment_type"}
DEDICATED_LEAD_EVENTS = {"newsletter_subscribe", "contact_submit", "catalog_request"}
AUTHENTICATED_ACCOUNT_EVENTS = {
    "view_order_history",
    "view_order",
    "start_return",
    "cancel_order",
    "update_profile",
    "update_preferences",
    "add_to_wishlist",
}
CONTROLLED_VALUE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
CONFIRMED_EVIDENCE = {"observed", "synthetic_observation", "confirmed"}
AUTHENTICATED_DISCOVERY = {"authenticated_observed", "client_confirmed"}
AUTHENTICATED_CONTEXT_RE = re.compile(
    r"authenticated|customer.?space|client.?space|espace.?client|order history|account dashboard|account area|my.?account|mon.?compte|mes.?commandes|after login|apres.?connexion|signed.?in",
    re.I,
)
AUTHENTICATION_FLOW_EVENTS = {"login", "sign_up", "password_reset"}


def _events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in plan.get("events", []) if isinstance(event, dict)]


def check_developer_examples(plan: dict[str, Any], issues: list[Issue]) -> None:
    for index, event in enumerate(_events(plan)):
        base = f"$.events[{index}]"
        classification = str(event.get("classification", ""))
        data_layer = event.get("data_layer")
        if classification in {"automatic", "enhanced_measurement"} and not data_layer:
            continue
        if not isinstance(data_layer, dict) or not isinstance(data_layer.get("push"), dict) or not data_layer.get("push"):
            add_issue(
                issues,
                "error",
                "DATALAYER_EXAMPLE_MISSING",
                f"{base}.data_layer",
                "Every manually collected event needs a complete dataLayer.push example for developers.",
            )
            continue

        event_name = str(event.get("event_name", ""))
        push = data_layer["push"]
        if push.get("event") != event_name:
            add_issue(
                issues,
                "error",
                "DATALAYER_TRIGGER_MISMATCH",
                f"{base}.data_layer.push.event",
                "The GTM dataLayer event key must match the final GA4 event name.",
            )
        if len(str(data_layer.get("mapping_notes", "")).split()) < 5:
            add_issue(
                issues,
                "error",
                "DATALAYER_MAPPING_MISSING",
                f"{base}.data_layer.mapping_notes",
                "Every manual event needs a developer-readable GTM-to-GA4 mapping note.",
            )
        if classification == "recommended_ecommerce":
            ecommerce = push.get("ecommerce")
            if not isinstance(ecommerce, dict):
                add_issue(
                    issues,
                    "error",
                    "GTM_ECOMMERCE_WRAPPER_MISSING",
                    f"{base}.data_layer.push.ecommerce",
                    "Use Google's GTM ecommerce format: event plus a nested ecommerce object and items array.",
                )
            elif not isinstance(ecommerce.get("items"), list):
                add_issue(
                    issues,
                    "error",
                    "GTM_ECOMMERCE_ITEMS_MISSING",
                    f"{base}.data_layer.push.ecommerce.items",
                    "Official GTM ecommerce examples need ecommerce.items as an array.",
                )
            if "ecommerce" not in set(data_layer.get("flush_keys", [])):
                add_issue(
                    issues,
                    "error",
                    "GTM_ECOMMERCE_RESET_MISSING",
                    f"{base}.data_layer.flush_keys",
                    "Clear the previous ecommerce object before the event push.",
                )


def check_controlled_values(plan: dict[str, Any], issues: list[Issue]) -> None:
    for index, parameter in enumerate(plan.get("parameters", [])):
        if not isinstance(parameter, dict):
            continue
        allowed = parameter.get("allowed_values", [])
        rules = str(parameter.get("value_rules", ""))
        path = f"$.parameters[{index}]"
        if "|" in rules and not allowed:
            add_issue(
                issues,
                "error",
                "CONTROLLED_VALUES_NOT_STRUCTURED",
                f"{path}.allowed_values",
                "Finite pipe-separated values must also be stored in allowed_values so human output can render them consistently.",
            )
        for value_index, value in enumerate(allowed if isinstance(allowed, list) else []):
            text = str(value)
            if not CONTROLLED_VALUE_RE.fullmatch(text):
                add_issue(
                    issues,
                    "error",
                    "CONTROLLED_VALUE_NOT_ENGLISH_ASCII",
                    f"{path}.allowed_values[{value_index}]",
                    "Controlled multilingual values must use English lowercase ASCII snake_case.",
                )


def check_navigation_model(plan: dict[str, Any], issues: list[Issue]) -> None:
    events = _events(plan)
    whole_site = plan.get("website_coverage_map", {}).get("site_scope") == "whole_site"
    nav_events = [event for event in events if event.get("event_name") in NAVIGATION_EVENTS]
    if whole_site and not nav_events:
        content_navigation = [
            event
            for event in events
            if event.get("event_name") == "select_content"
            and re.search(r"header|footer|menu|navigation", " ".join(str(event.get(key, "")) for key in ("page_or_component", "trigger")), re.I)
        ]
        assumptions = " ".join(str(value) for value in plan.get("assumptions", []))
        if content_navigation and "client convention" not in assumptions.lower():
            add_issue(
                issues,
                "error",
                "NAVIGATION_SURFACE_EVENTS_MISSING",
                "$.events",
                "Whole-site navigation needs an approved client convention or reusable header/menu/submenu/footer events; reserve select_content for content objects.",
            )

    for event in nav_events:
        missing = sorted(NAVIGATION_PARAMETERS - set(event.get("parameters", [])))
        if missing:
            add_issue(
                issues,
                "error",
                "NAVIGATION_PARAMETERS_MISSING",
                f"$.events[{events.index(event)}].parameters",
                f"Navigation events need the shared parameters: {', '.join(missing)}.",
            )


def check_authenticated_discovery(plan: dict[str, Any], issues: list[Issue]) -> None:
    if plan.get("website_coverage_map", {}).get("site_scope") != "whole_site":
        return
    auth_text = " ".join(
        str(value)
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict)
        for value in [brief.get("journey_id"), brief.get("journey_name"), brief.get("page_type"), brief.get("scope")]
    ).lower()
    if not re.search(r"account|login|sign.?up|authentication|customer.space|client.space", auth_text):
        return
    decision = plan.get("website_coverage_map", {}).get("authenticated_journey", {})
    if not isinstance(decision, dict) or not decision.get("applicable"):
        add_issue(
            issues,
            "error",
            "AUTHENTICATED_DISCOVERY_DECISION_MISSING",
            "$.website_coverage_map.authenticated_journey",
            "Whole-site account scope needs an explicit authenticated-journey discovery decision.",
        )
        return
    status = str(decision.get("discovery_status", ""))
    if status == "not_attempted":
        add_issue(
            issues,
            "error",
            "AUTHENTICATED_DISCOVERY_NOT_ATTEMPTED",
            "$.website_coverage_map.authenticated_journey.discovery_status",
            "Attempt safe synthetic signup or authenticated exploration unless the user explicitly excludes it.",
        )
    if status == "attempted_blocked" and len(str(decision.get("gap_reason", "")).split()) < 4:
        add_issue(
            issues,
            "error",
            "AUTHENTICATED_DISCOVERY_GAP_WEAK",
            "$.website_coverage_map.authenticated_journey.gap_reason",
            "A blocked authenticated journey needs a concrete access or safety reason.",
        )
    if status == "authenticated_observed" and (not decision.get("attempted_actions") or not decision.get("evidence")):
        add_issue(
            issues,
            "error",
            "AUTHENTICATED_DISCOVERY_EVIDENCE_MISSING",
            "$.website_coverage_map.authenticated_journey",
            "Authenticated observation needs the synthetic actions completed and concrete evidence from the gated journey.",
        )


def check_event_access_context(plan: dict[str, Any], issues: list[Issue]) -> None:
    events = _events(plan)
    discovery_status = str(plan.get("website_coverage_map", {}).get("authenticated_journey", {}).get("discovery_status", ""))
    for index, event in enumerate(events):
        access_context = str(event.get("access_context", ""))
        event_name = str(event.get("event_name", ""))
        evidence_status = str(event.get("evidence_basis", {}).get("status", ""))
        event_context = " ".join(str(event.get(key, "")) for key in ("page_type", "page_or_component", "page_url_pattern", "trigger"))
        if event_name in AUTHENTICATED_ACCOUNT_EVENTS and access_context != "authenticated_area":
            add_issue(issues, "error", "AUTHENTICATED_EVENT_CONTEXT_INVALID", f"$.events[{index}].access_context", f"Customer-space event '{event_name}' must use access_context='authenticated_area'.")
        if event_name in AUTHENTICATION_FLOW_EVENTS and access_context != "authentication_flow":
            add_issue(issues, "error", "AUTHENTICATION_FLOW_CONTEXT_INVALID", f"$.events[{index}].access_context", f"Authentication outcome '{event_name}' must use access_context='authentication_flow'.")
        if access_context == "public" and event_name != "account_access_intent" and AUTHENTICATED_CONTEXT_RE.search(event_context):
            add_issue(issues, "error", "AUTHENTICATED_CONTEXT_UNDERSTATED", f"$.events[{index}].access_context", "The event context appears to be behind login and cannot be classified as public.")
        if access_context == "authenticated_area":
            if discovery_status not in AUTHENTICATED_DISCOVERY:
                add_issue(issues, "error", "UNVERIFIED_AUTHENTICATED_EVENT", f"$.events[{index}]", "Do not propose any event behind authentication unless the real gated journey was synthetically observed or client-confirmed.")
            if evidence_status not in CONFIRMED_EVIDENCE:
                add_issue(issues, "error", "AUTHENTICATED_EVENT_EVIDENCE_WEAK", f"$.events[{index}].evidence_basis.status", "Behind-login events must be observed, synthetically observed, or client-confirmed; inference is not allowed.")
        if access_context == "authentication_flow" and event_name in {"login", "sign_up"} and evidence_status not in CONFIRMED_EVIDENCE:
            add_issue(issues, "error", "AUTHENTICATION_EVENT_EVIDENCE_WEAK", f"$.events[{index}].evidence_basis.status", f"Successful {event_name} must be observed or confirmed, not inferred from the presence of a form.")


def check_lead_mode(mode: str, mappings: list[dict[str, Any]], mapped_names: set[str], implemented_names: set[str], issues: list[Issue]) -> None:
    if mode == "not_applicable" and (mappings or implemented_names):
        add_issue(
            issues,
            "error",
            "LEAD_MODEL_NOT_APPLICABLE_CONFLICT",
            "$.measurement_strategy.lead_event_model",
            "A not_applicable lead model cannot contain lead mappings or implemented lead events.",
        )
    if mode == "consolidated" and mapped_names and mapped_names != {"generate_lead"}:
        add_issue(issues, "error", "LEAD_MODEL_CONSOLIDATED_INVALID", "$.measurement_strategy.lead_event_model", "Consolidated lead outcomes must all map to generate_lead.")
    if mode == "separate" and "generate_lead" in mapped_names:
        add_issue(issues, "error", "LEAD_MODEL_SEPARATE_INVALID", "$.measurement_strategy.lead_event_model", "A separate lead model must map each outcome to a dedicated event, not generate_lead.")
    if mode == "hybrid" and mapped_names and ("generate_lead" not in mapped_names or len(mapped_names) < 2):
        add_issue(issues, "error", "LEAD_MODEL_HYBRID_INVALID", "$.measurement_strategy.lead_event_model", "A hybrid lead model needs generate_lead plus at least one dedicated outcome event.")


def check_lead_event_mapping(mode: str, mapped_names: set[str], implemented_names: set[str], event_names: set[str], issues: list[Issue]) -> None:
    missing_events = sorted(mapped_names - event_names)
    if missing_events:
        add_issue(issues, "error", "LEAD_MODEL_EVENT_MISSING", "$.measurement_strategy.lead_event_model.outcome_mappings", f"Lead mappings reference events absent from the plan: {', '.join(missing_events)}.")
    unmapped_events = sorted(implemented_names - mapped_names)
    if mode != "not_applicable" and unmapped_events:
        add_issue(issues, "error", "LEAD_EVENT_UNMAPPED", "$.events", f"Lead events need explicit outcome mappings: {', '.join(unmapped_events)}.")


def check_lead_event_model(plan: dict[str, Any], issues: list[Issue]) -> None:
    event_names = {str(event.get("event_name", "")) for event in _events(plan)}
    model = plan.get("measurement_strategy", {}).get("lead_event_model", {})
    if not isinstance(model, dict):
        return
    mode = str(model.get("mode", ""))
    mappings = [item for item in model.get("outcome_mappings", []) if isinstance(item, dict)]
    mapped_names = {str(item.get("event_name", "")) for item in mappings if item.get("evidence_status") != "unavailable"}
    implemented_names = ({"generate_lead"} | DEDICATED_LEAD_EVENTS) & event_names
    check_lead_mode(mode, mappings, mapped_names, implemented_names, issues)
    check_lead_event_mapping(mode, mapped_names, implemented_names, event_names, issues)


def check_authenticated_outcome_coverage(plan: dict[str, Any], issues: list[Issue]) -> None:
    if plan.get("website_coverage_map", {}).get("site_scope") != "whole_site":
        return
    brief_text = " ".join(
        str(value)
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict)
        for value in brief.values()
    ).lower()
    has_customer_space = bool(re.search(r"customer.?space|client.?space|authenticated|account.*order|order history|returns?", brief_text))
    if not has_customer_space:
        return
    events = _events(plan)
    names = {str(event.get("event_name", "")) for event in events}
    discovery_status = str(plan.get("website_coverage_map", {}).get("authenticated_journey", {}).get("discovery_status", ""))
    has_reorder = "add_to_cart" in names and any(
        re.search(r"reorder|order history|previous order", f"{event.get('trigger', '')} {event.get('analysis_use', '')}", re.I)
        for event in _events(plan)
        if event.get("event_name") == "add_to_cart"
    )
    account_events = [event for event in events if event.get("access_context") == "authenticated_area" and event.get("event_name") != "page_view"]
    if discovery_status in AUTHENTICATED_DISCOVERY:
        if not account_events and not has_reorder:
            add_issue(
                issues,
                "error",
                "AUTHENTICATED_OUTCOMES_MISSING",
                "$.events",
                "Confirmed customer-space coverage needs meaningful observed outcomes beyond login and sign_up, or an explicit page_view-only decision.",
            )


def check_order_cancellation_model(plan: dict[str, Any], issues: list[Issue]) -> None:
    brief_text = " ".join(
        str(value)
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict)
        for value in brief.values()
    ).lower()
    if not re.search(r"cancel(?:lation|led| order)|order cancellation", brief_text):
        return
    journey_ids = {
        str(brief.get("journey_id", ""))
        for brief in plan.get("measurement_brief", [])
        if isinstance(brief, dict) and re.search(r"cancel(?:lation|led| order)|order cancellation", " ".join(str(value) for value in brief.values()).lower())
    }
    covered = {
        str(item.get("journey_id", ""))
        for item in plan.get("website_coverage_map", {}).get("journeys_covered", [])
        if isinstance(item, dict) and item.get("coverage_status") == "covered" and item.get("tracking_plan_decision") == "included"
    }
    names = {str(event.get("event_name", "")) for event in _events(plan)}
    if journey_ids & covered and "cancel_order" not in names:
        add_issue(
            issues,
            "error",
            "ORDER_CANCELLATION_EVENT_MISSING",
            "$.events",
            "A scoped order-cancellation journey needs backend-confirmed cancel_order; keep refund for actual refund completion.",
        )


def check_ga4_user_id(context: dict[str, Any], parameters: dict[str, dict[str, Any]], events: list[dict[str, Any]], issues: list[Issue]) -> None:
    user_id = context.get("ga4_user_id", {})
    if not isinstance(user_id, dict) or not user_id.get("enabled"):
        return
    metadata = parameters.get("user_id", {})
    if user_id.get("source_path") != "user_context.user_id":
        add_issue(issues, "error", "USER_ID_SOURCE_PATH_INVALID", "$.user_context.ga4_user_id.source_path", "GA4 User-ID should read from user_context.user_id.")
    if metadata.get("scope") != "implementation" or metadata.get("classification") != "implementation_variable" or metadata.get("register_custom_definition"):
        add_issue(issues, "error", "USER_ID_PARAMETER_GOVERNANCE_INVALID", "$.parameters", "user_id must be an implementation variable, must not be an event/user property, and must never be registered as a custom definition.")
    for index, event in enumerate(events):
        if "user_id" in event.get("parameters", []) or "user_id" in event.get("ga4_payload", {}).get("parameters", {}):
            add_issue(issues, "error", "USER_ID_EVENT_PARAMETER_INVALID", f"$.events[{index}]", "Set user_id through the Google tag configuration, never as an event parameter.")


def check_user_properties(context: dict[str, Any], parameters: dict[str, dict[str, Any]], issues: list[Issue]) -> None:
    for index, mapping in enumerate(context.get("user_properties", [])):
        if not isinstance(mapping, dict):
            continue
        name = str(mapping.get("parameter_name", ""))
        metadata = parameters.get(name, {})
        if metadata.get("scope") != "user" or metadata.get("classification") != "custom_user_property":
            add_issue(issues, "error", "USER_PROPERTY_PARAMETER_INVALID", f"$.user_context.user_properties[{index}]", f"User property '{name}' needs user scope and custom_user_property classification.")
        if list(mapping.get("allowed_values", [])) != list(metadata.get("allowed_values", [])):
            add_issue(issues, "error", "USER_PROPERTY_VALUES_MISMATCH", f"$.user_context.user_properties[{index}].allowed_values", f"User property '{name}' must reuse the Parameter Reference controlled values.")


def check_advertising_user_data(context: dict[str, Any], issues: list[Issue]) -> None:
    ads = context.get("advertising_user_data", {})
    if not isinstance(ads, dict):
        return
    if ads.get("status") == "not_applicable":
        if ads.get("destination") != "not_applicable" or ads.get("fields"):
            add_issue(issues, "error", "AD_USER_DATA_NOT_APPLICABLE_CONFLICT", "$.user_context.advertising_user_data", "Not-applicable advertising user data cannot define a destination or fields.")
        return
    handling = str(ads.get("handling_rule", ""))
    consent = set(ads.get("consent_requirements", []))
    if ads.get("destination") == "not_applicable" or "ad_user_data" not in consent or not re.search(r"hash|normaliz", handling, re.I) or not re.search(r"not.*ga4|never.*ga4", handling, re.I):
        add_issue(issues, "error", "AD_USER_DATA_GOVERNANCE_WEAK", "$.user_context.advertising_user_data", "Advertising user data needs a non-GA4 destination, ad_user_data consent, normalization or hashing rules, and an explicit prohibition on GA4 mapping.")


def check_user_context(plan: dict[str, Any], issues: list[Issue]) -> None:
    context = plan.get("user_context", {})
    if not isinstance(context, dict) or context.get("status") == "not_applicable":
        return
    if context.get("data_layer_object") != "user_context":
        add_issue(issues, "error", "USER_CONTEXT_OBJECT_INVALID", "$.user_context.data_layer_object", "Use user_context for GA4-safe authenticated context; reserve user_data for separately governed advertising user data.")
    parameters = {str(item.get("parameter_name", "")): item for item in plan.get("parameters", []) if isinstance(item, dict)}
    check_ga4_user_id(context, parameters, _events(plan), issues)
    check_user_properties(context, parameters, issues)
    check_advertising_user_data(context, issues)


def check_availability_scope(plan: dict[str, Any], issues: list[Issue]) -> None:
    for index, event in enumerate(_events(plan)):
        if "items[].availability_status" not in set(event.get("parameters", [])):
            continue
        name = str(event.get("event_name", ""))
        if name == "view_item":
            continue
        notes = f"{event.get('implementation_notes', '')} {event.get('analysis_use', '')}".lower()
        if name == "view_cart" and "persistent" in notes and ("live inventory" in notes or "real-time" in notes):
            continue
        add_issue(
            issues,
            "error",
            "AVAILABILITY_STATUS_SCOPE_INVALID",
            f"$.events[{index}].parameters",
            "Default variant availability belongs on view_item. Use it on view_cart only for a documented persistent-cart, live-inventory case; do not add it to list, selection, or add-to-cart events by default.",
        )


def check_payment_failure_branch(plan: dict[str, Any], issues: list[Issue]) -> None:
    events = _events(plan)
    names = {str(event.get("event_name", "")) for event in events}
    if "add_payment_info" not in names or "purchase" not in names:
        return
    failures = [event for event in events if event.get("event_name") in PAYMENT_FAILURE_EVENTS]
    if not failures:
        add_issue(
            issues,
            "error",
            "PAYMENT_FAILURE_BRANCH_MISSING",
            "$.events",
            "Checkout plans with add_payment_info and purchase need a refused/failed payment diagnostic branch.",
        )
        return
    for event in failures:
        missing = sorted(PAYMENT_FAILURE_PARAMETERS - set(event.get("parameters", [])))
        if missing:
            add_issue(
                issues,
                "error",
                "PAYMENT_FAILURE_PARAMETERS_MISSING",
                f"$.events[{events.index(event)}].parameters",
                f"Payment failure events need controlled parameters: {', '.join(missing)}.",
            )


def check_delivery_rules(plan: dict[str, Any], issues: list[Issue]) -> None:
    check_developer_examples(plan, issues)
    check_controlled_values(plan, issues)
    check_navigation_model(plan, issues)
    check_authenticated_discovery(plan, issues)
    check_event_access_context(plan, issues)
    check_lead_event_model(plan, issues)
    check_authenticated_outcome_coverage(plan, issues)
    check_order_cancellation_model(plan, issues)
    check_user_context(plan, issues)
    check_availability_scope(plan, issues)
    check_payment_failure_branch(plan, issues)
