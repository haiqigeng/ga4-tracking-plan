from __future__ import annotations

import re
from typing import Any

from tracking_plan_contract import event_ga4_payload, event_parameter_names, parameter_allowed_values
from tracking_plan_validation_datalayer import check_developer_examples
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
CONFIRMED_EVIDENCE = {"observed", "synthetic_observation", "confirmed"}
AUTHENTICATED_DISCOVERY = {"authenticated_observed", "client_confirmed"}
RECOMMENDED_EVIDENCE = "recommended"
OFFICIAL_RECOMMENDATION_CLASSIFICATIONS = {"recommended", "recommended_ecommerce"}
RECOMMENDATION_BASES = {
    "official_capability",
    "observed_public_affordance",
    "client_brief",
    "documented_sector_pattern",
}
WHOLE_SITE_RETAIL_EVENT_DECISIONS = {
    "view_item_list",
    "select_item",
    "view_item",
    "add_to_cart",
    "view_cart",
    "remove_from_cart",
    "begin_checkout",
    "add_shipping_info",
    "add_payment_info",
    "purchase",
    "refund",
    "start_return",
    "cancel_order",
}
AUTHENTICATED_CONTEXT_RE = re.compile(
    r"authenticated|customer.?space|client.?space|espace.?client|order history|account dashboard|account area|my.?account|mon.?compte|mes.?commandes|after login|apres.?connexion|signed.?in",
    re.I,
)
AUTHENTICATION_FLOW_EVENTS = {"login", "sign_up", "password_reset"}
def _events(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in plan.get("events", []) if isinstance(event, dict)]


def _accepted_custom_event_names(plan: dict[str, Any]) -> set[str]:
    return {
        str(item.get("event_name", ""))
        for item in plan.get("measurement_strategy", {}).get("custom_event_acceptance", [])
        if isinstance(item, dict) and item.get("event_name")
    }


def _is_governed_recommendation(event: dict[str, Any], accepted_custom_names: set[str]) -> bool:
    if str(event.get("evidence_basis", {}).get("status", "")) != RECOMMENDED_EVIDENCE:
        return False
    classification = str(event.get("classification", ""))
    if classification in OFFICIAL_RECOMMENDATION_CLASSIFICATIONS:
        return str(event.get("official_verification", {}).get("status", "")) == "verified"
    return classification == "custom" and str(event.get("event_name", "")) in accepted_custom_names


def _check_recommendation_guardrails(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    evidence = event.get("evidence_basis", {})
    if str(evidence.get("confidence", "")) == "high":
        add_issue(
            issues,
            "error",
            "UNOBSERVED_RECOMMENDATION_CONFIDENCE_HIGH",
            f"$.events[{index}].evidence_basis.confidence",
            "An unobserved recommendation must use low or medium confidence, never high confidence.",
        )
    if evidence.get("basis_type") not in RECOMMENDATION_BASES:
        add_issue(
            issues,
            "error",
            "UNOBSERVED_RECOMMENDATION_BASIS_MISSING",
            f"$.events[{index}].evidence_basis.basis_type",
            "An unobserved recommendation needs a structured official, observed-affordance, client-brief, or documented-sector basis.",
        )
    if evidence.get("confirmation_required") is not True or not str(evidence.get("confirmation_owner", "")).strip():
        add_issue(
            issues,
            "error",
            "UNOBSERVED_RECOMMENDATION_CONFIRMATION_MISSING",
            f"$.events[{index}].evidence_basis",
            "An unobserved recommendation must explicitly require confirmation and name the responsible data owner.",
        )


def check_controlled_values(plan: dict[str, Any], issues: list[Issue]) -> None:
    for index, parameter in enumerate(plan.get("parameters", [])):
        if not isinstance(parameter, dict):
            continue
        allowed = parameter_allowed_values(parameter)
        rules = str(parameter.get("value_rules", ""))
        path = f"$.parameters[{index}]"
        if "|" in rules and not allowed:
            add_issue(
                issues,
                "error",
                "CONTROLLED_VALUES_NOT_STRUCTURED",
                f"{path}.value_domain.entries",
                "Finite pipe-separated values must also be stored as evidence-bearing value-domain entries so human output can render them consistently.",
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
        missing = sorted(NAVIGATION_PARAMETERS - set(event_parameter_names(event)))
        if missing:
            add_issue(
                issues,
                "error",
                "NAVIGATION_PARAMETERS_MISSING",
                f"$.events[{events.index(event)}].parameter_bindings",
                f"Navigation events need the shared parameters: {', '.join(missing)}.",
            )


def check_authenticated_discovery(plan: dict[str, Any], issues: list[Issue]) -> None:
    if plan.get("website_coverage_map", {}).get("site_scope") != "whole_site":
        return
    decision = plan.get("website_coverage_map", {}).get("authenticated_journey")
    if not isinstance(decision, dict) or "applicable" not in decision:
        add_issue(
            issues,
            "error",
            "AUTHENTICATED_DISCOVERY_DECISION_MISSING",
            "$.website_coverage_map.authenticated_journey",
            "Whole-site scope needs an explicit authenticated-journey applicability decision.",
        )
        return
    if not decision.get("applicable"):
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
    if status == "attempted_blocked" and not str(decision.get("gap_reason", "")).strip():
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
    accepted_custom_names = _accepted_custom_event_names(plan)
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
            governed_recommendation = _is_governed_recommendation(event, accepted_custom_names)
            if discovery_status not in AUTHENTICATED_DISCOVERY and not governed_recommendation:
                add_issue(
                    issues,
                    "error",
                    "UNVERIFIED_AUTHENTICATED_EVENT",
                    f"$.events[{index}]",
                    "An unobserved authenticated event must be an officially verified or explicitly accepted custom recommendation, not an inference.",
                )
            if evidence_status not in CONFIRMED_EVIDENCE and not governed_recommendation:
                add_issue(
                    issues,
                    "error",
                    "AUTHENTICATED_EVENT_EVIDENCE_WEAK",
                    f"$.events[{index}].evidence_basis.status",
                    "Behind-login events must be observed, confirmed, or governed recommendations; inferred evidence is not allowed.",
                )
            if governed_recommendation:
                _check_recommendation_guardrails(event, index, issues)
        if access_context == "authentication_flow" and event_name in {"login", "sign_up"} and evidence_status not in CONFIRMED_EVIDENCE:
            governed_recommendation = _is_governed_recommendation(event, accepted_custom_names)
            if not governed_recommendation:
                add_issue(
                    issues,
                    "error",
                    "AUTHENTICATION_EVENT_EVIDENCE_WEAK",
                    f"$.events[{index}].evidence_basis.status",
                    f"Successful {event_name} must be observed, confirmed, or retained as an officially verified recommendation; inference from a form is invalid.",
                )
            else:
                _check_recommendation_guardrails(event, index, issues)


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
    if not plan.get("website_coverage_map", {}).get("authenticated_journey", {}).get("applicable"):
        return
    events = _events(plan)
    names = {str(event.get("event_name", "")) for event in events}
    has_reorder = "add_to_cart" in names and any(
        re.search(r"reorder|order history|previous order", f"{event.get('trigger', '')} {event.get('analysis_use', '')}", re.I)
        for event in _events(plan)
        if event.get("event_name") == "add_to_cart"
    )
    account_events = [event for event in events if event.get("access_context") == "authenticated_area" and event.get("event_name") != "page_view"]
    if not account_events and not has_reorder:
        add_issue(
            issues,
            "error",
            "AUTHENTICATED_OUTCOMES_MISSING",
            "$.events",
            "Whole-site customer-space coverage needs meaningful outcomes beyond login and sign_up. If access is blocked, retain applicable official or accepted custom outcomes as recommendations instead of omitting the journey.",
        )


def _explicit_event_exclusions(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for item in plan.get("not_tracked", []):
        if not isinstance(item, dict):
            continue
        interaction = str(item.get("interaction", "")).lower()
        for event_name in WHOLE_SITE_RETAIL_EVENT_DECISIONS:
            if re.search(rf"(?<![a-z0-9_]){re.escape(event_name)}(?![a-z0-9_])", interaction):
                decisions[event_name] = item
    return decisions


def check_whole_site_ecommerce_coverage(plan: dict[str, Any], issues: list[Issue]) -> None:
    if plan.get("website_coverage_map", {}).get("site_scope") != "whole_site":
        return
    events = _events(plan)
    event_names = {str(event.get("event_name", "")) for event in events}
    selected_family_ids = {
        str(item.get("family_id", ""))
        for item in plan.get("measurement_strategy", {}).get("selected_event_families", [])
        if isinstance(item, dict)
    }
    if not any(event.get("classification") == "recommended_ecommerce" for event in events) and not selected_family_ids.intersection({"ecommerce", "online_sales"}):
        return

    exclusions = _explicit_event_exclusions(plan)
    for event_name in sorted(WHOLE_SITE_RETAIL_EVENT_DECISIONS):
        if event_name in event_names:
            continue
        exclusion = exclusions.get(event_name)
        if not exclusion:
            add_issue(
                issues,
                "error",
                "WHOLE_SITE_ECOMMERCE_EVENT_DECISION_MISSING",
                "$.events",
                f"Whole-site physical retail needs '{event_name}' as an observed, confirmed, or recommended event, or an explicit confirmed-not-applicable decision naming that event.",
            )
        elif exclusion.get("reason_code") != "not_applicable_confirmed":
            add_issue(
                issues,
                "error",
                "ECOMMERCE_EVENT_EXCLUSION_UNCONFIRMED",
                "$.not_tracked",
                f"'{event_name}' may be excluded from a whole-site retail plan only with reason_code='not_applicable_confirmed'; blocked discovery must remain a recommendation.",
            )


def check_ga4_user_id(context: dict[str, Any], parameters: dict[str, dict[str, Any]], events: list[dict[str, Any]], issues: list[Issue]) -> None:
    user_id = context.get("ga4_user_id", {})
    if not isinstance(user_id, dict) or not user_id.get("enabled"):
        return
    metadata = parameters.get("user_id", {})
    if user_id.get("source_path") != "user.user_id":
        add_issue(issues, "error", "USER_ID_SOURCE_PATH_INVALID", "$.user_context.ga4_user_id.source_path", "GA4 User-ID should read from user.user_id.")
    if metadata.get("scope") != "implementation" or metadata.get("classification") != "implementation_variable" or metadata.get("register_custom_definition"):
        add_issue(issues, "error", "USER_ID_PARAMETER_GOVERNANCE_INVALID", "$.parameters", "user_id must be an implementation variable, must not be an event/user property, and must never be registered as a custom definition.")
    for index, event in enumerate(events):
        if "user_id" in event_parameter_names(event) or "user_id" in event_ga4_payload(event).get("parameters", {}):
            add_issue(issues, "error", "USER_ID_EVENT_PARAMETER_INVALID", f"$.events[{index}]", "Set user_id through the Google tag configuration, never as an event parameter.")


def check_user_properties(context: dict[str, Any], parameters: dict[str, dict[str, Any]], issues: list[Issue]) -> None:
    for index, mapping in enumerate(context.get("user_properties", [])):
        if not isinstance(mapping, dict):
            continue
        name = str(mapping.get("parameter_name", ""))
        metadata = parameters.get(name, {})
        if metadata.get("scope") != "user" or metadata.get("classification") != "custom_user_property":
            add_issue(issues, "error", "USER_PROPERTY_PARAMETER_INVALID", f"$.user_context.user_properties[{index}]", f"User property '{name}' needs user scope and custom_user_property classification.")


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
    if context.get("data_layer_object") != "user":
        add_issue(issues, "error", "USER_CONTEXT_OBJECT_INVALID", "$.user_context.data_layer_object", "Use user for GA4-safe authenticated context; reserve user_data for separately governed advertising user data.")
    parameters = {str(item.get("parameter_name", "")): item for item in plan.get("parameters", []) if isinstance(item, dict)}
    check_ga4_user_id(context, parameters, _events(plan), issues)
    check_user_properties(context, parameters, issues)
    check_advertising_user_data(context, issues)


def check_availability_scope(plan: dict[str, Any], issues: list[Issue]) -> None:
    for index, event in enumerate(_events(plan)):
        if "items[].availability_status" not in set(event_parameter_names(event)):
            continue
        name = str(event.get("event_name", ""))
        if name in {"view_item", "view_cart"}:
            continue
        add_issue(
            issues,
            "error",
            "AVAILABILITY_STATUS_SCOPE_INVALID",
            f"$.events[{index}].parameter_bindings",
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
        missing = sorted(PAYMENT_FAILURE_PARAMETERS - set(event_parameter_names(event)))
        if missing:
            add_issue(
                issues,
                "error",
                "PAYMENT_FAILURE_PARAMETERS_MISSING",
                f"$.events[{events.index(event)}].parameter_bindings",
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
    check_user_context(plan, issues)
    check_availability_scope(plan, issues)
    check_payment_failure_branch(plan, issues)
    check_whole_site_ecommerce_coverage(plan, issues)
