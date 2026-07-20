from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from official_ga4_catalog import (
    OFFICIAL_EVENT_CLASSES,
    OFFICIAL_PARAMETER_CLASSES,
    catalog_receipt_signature,
    event_parameter,
    load_catalog,
    load_parameter_library,
    load_scenario_library,
    normalize_requiredness,
    normalize_text,
    normalize_type,
    parameter_event_names,
    resolve_event_semantics,
    resolve_parameter_semantics,
)
from official_source_receipt import receipt_validation_errors, tracking_plan_sha256
from tracking_plan_contract import event_ga4_payload, event_parameter_bindings, event_parameter_names, source_registry
from tracking_plan_validation_catalogs import CUSTOM_PARAMETER_CLASSIFICATIONS, OFFICIAL_SOURCE_DOMAINS
from tracking_plan_validation_model import Issue, add_issue

RULES_DIR = Path(__file__).resolve().parents[1] / "references" / "03-rules"
RECOMMENDED_CATALOG = load_catalog(RULES_DIR / "library-ga4-recommended-events.json")
SCENARIO_LIBRARY = load_scenario_library(RULES_DIR / "library-ga4-event-scenarios.json")
PARAMETER_LIBRARY = load_parameter_library(RULES_DIR / "library-parameters.json")

GENERIC_DEFINITION_RE = re.compile(
    r"\b(?:official ga4 (?:event|parameter)|reusable (?:event|parameter|value)|"
    r"applicable events?|used (?:by|for) (?:the )?(?:event|tracking)|"
    r"parameter for [a-z0-9_]+|value associated with the applicable event)\b",
    re.I,
)
GENERIC_TRIGGER_RE = re.compile(
    r"^(?:on click|on page view|when applicable|when the event occurs|"
    r"when the user interacts|user interaction|track(?:ed)? when applicable|tbd|to confirm)\.?$",
    re.I,
)


def check_official_verification_freshness(plan: dict[str, Any], issues: list[Issue]) -> None:
    try:
        publish_date = date.fromisoformat(str(plan.get("document", {}).get("publish_date", "")))
    except ValueError:
        return
    expected_urls = {
        str(source.get("url", "")).split("#", 1)[0].rstrip("/")
        for source in plan.get("documentation_sources_checked", [])
        if isinstance(source, dict) and source.get("source_type") == "official" and source.get("url")
    }
    for message in receipt_validation_errors(
        plan.get("official_source_check"),
        publish_date=publish_date,
        expected_urls=expected_urls,
        expected_catalog_signature=catalog_receipt_signature(RECOMMENDED_CATALOG),
        expected_resolved_plan_sha256=tracking_plan_sha256(plan),
    ):
        add_issue(
            issues,
            "error",
            "OFFICIAL_SOURCE_RECEIPT_INVALID",
            "$.official_source_check",
            message,
        )


def _check_source_registry_entries(plan: dict[str, Any], issues: list[Issue]) -> None:
    source_ids = [
        str(source.get("source_id", ""))
        for source in plan.get("documentation_sources_checked", [])
        if isinstance(source, dict)
    ]
    if len(source_ids) != len(set(source_ids)):
        add_issue(issues, "error", "DUPLICATE_OFFICIAL_SOURCE_ID", "$.documentation_sources_checked", "Checked-source IDs must be unique.")
    for index, source in enumerate(plan.get("documentation_sources_checked", [])):
        if not isinstance(source, dict) or source.get("source_type") != "official":
            continue
        url = str(source.get("url", "")).lower()
        if not any(domain in url for domain in OFFICIAL_SOURCE_DOMAINS["google_measurement"]):
            add_issue(issues, "error", "OFFICIAL_SOURCE_DOMAIN_INVALID", f"$.documentation_sources_checked[{index}].url", "Official GA4 sources must use an official Google domain.")


def _check_official_item_source(
    item: dict[str, Any],
    collection_name: str,
    index: int,
    registry: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    classification = str(item.get("classification", ""))
    official_classes = OFFICIAL_EVENT_CLASSES if collection_name == "events" else OFFICIAL_PARAMETER_CLASSES
    if classification not in official_classes:
        return
    verification = item.get("official_verification", {})
    source_id = str(verification.get("source_id", "")) if isinstance(verification, dict) else ""
    if source_id not in registry or registry[source_id].get("source_type") != "official":
        add_issue(issues, "error", "OFFICIAL_SOURCE_REFERENCE_INVALID", f"$.{collection_name}[{index}].official_verification.source_id", "Official semantics must reference an official checked-source registry entry.")
    if collection_name != "events":
        return
    trigger_id = str(verification.get("trigger_source_id", "")) if isinstance(verification, dict) else ""
    if trigger_id not in registry or registry[trigger_id].get("source_type") != "official":
        add_issue(issues, "error", "OFFICIAL_TRIGGER_SOURCE_REFERENCE_INVALID", f"$.events[{index}].official_verification.trigger_source_id", "Official trigger guidance must reference an official checked-source registry entry.")


def check_official_source_registry(plan: dict[str, Any], issues: list[Issue]) -> None:
    registry = source_registry(plan)
    _check_source_registry_entries(plan, issues)
    for collection_name in ("events", "parameters"):
        for index, item in enumerate(plan.get(collection_name, [])):
            if isinstance(item, dict):
                _check_official_item_source(item, collection_name, index, registry, issues)


def _check_human_definition(value: Any, path: str, label: str, issues: list[Issue]) -> None:
    text = " ".join(str(value or "").split()).strip()
    if not text or GENERIC_DEFINITION_RE.search(text):
        add_issue(
            issues,
            "error",
            f"{label}_LAZY",
            path,
            "Use one concise, concrete sentence explaining what the event or value represents; names, reusable/applicable wording, and generic tracking language are not definitions.",
        )


def _check_source_locator(verification: Any, path: str, expected_locator: str, issues: list[Issue]) -> None:
    if not isinstance(verification, dict):
        return
    section = str(verification.get("source_section", "")).strip()
    locator = str(verification.get("source_locator", "")).strip()
    if not section:
        add_issue(issues, "error", "OFFICIAL_SOURCE_SECTION_MISSING", f"{path}.source_section", "Official verification must pinpoint the documentation section used.")
    if not locator:
        add_issue(issues, "error", "OFFICIAL_SOURCE_LOCATOR_MISSING", f"{path}.source_locator", "Official verification must pinpoint the event heading or parameter row used.")
    elif expected_locator and locator != expected_locator:
        add_issue(
            issues,
            "error",
            "OFFICIAL_SOURCE_LOCATOR_MISMATCH",
            f"{path}.source_locator",
            f"Expected official source locator '{expected_locator}', found '{locator}'.",
        )


def _translation_status_valid(workbook_language: str, translation_status: str) -> bool:
    if workbook_language == "en":
        return translation_status == "not_needed"
    return translation_status in {"official_localized_source", "analyst_translation"}


def _check_official_event_resolution(
    plan: dict[str, Any],
    event: dict[str, Any],
    resolution: dict[str, str],
    summary: str,
    base: str,
    issues: list[Issue],
) -> None:
    verification = event.get("official_verification", {})
    verification = verification if isinstance(verification, dict) else {}
    if normalize_text(verification.get("canonical_wording")) != normalize_text(resolution["definition"]):
        add_issue(issues, "error", "OFFICIAL_CANONICAL_WORDING_MISMATCH", f"{base}.official_verification.canonical_wording", "Keep the exact catalog-resolved Google event definition as canonical wording, including when the workbook wording is localized.")
    if normalize_text(verification.get("canonical_trigger_wording")) != normalize_text(resolution["trigger_guidance"]):
        add_issue(issues, "error", "OFFICIAL_CANONICAL_TRIGGER_MISMATCH", f"{base}.official_verification.canonical_trigger_wording", "Keep the catalog-resolved Google trigger guidance as the source basis for the website-specific firing condition.")
    workbook_language = str(plan.get("language_policy", {}).get("workbook_language", "en"))
    translation_status = str(verification.get("translation_status", ""))
    if translation_status != "official_localized_source":
        for field, code, label in (
            ("source_section", "OFFICIAL_SOURCE_SECTION_MISMATCH", "event-definition section"),
            ("source_locator", "OFFICIAL_SOURCE_LOCATOR_MISMATCH", "event-definition locator"),
            ("trigger_source_section", "OFFICIAL_TRIGGER_SOURCE_SECTION_MISMATCH", "implementation-guidance section"),
            ("trigger_source_locator", "OFFICIAL_TRIGGER_SOURCE_LOCATOR_MISMATCH", "implementation-guidance locator"),
        ):
            if normalize_text(verification.get(field)) != normalize_text(resolution[field]):
                add_issue(
                    issues,
                    "error",
                    code,
                    f"{base}.official_verification.{field}",
                    f"Use the catalog-resolved Google {label}; a nonempty but unrelated locator is not sufficient.",
                )
    registry = source_registry(plan)
    for id_field, resolved_url, code in (
        ("source_id", resolution["source_url"], "OFFICIAL_SOURCE_URL_MISMATCH"),
        ("trigger_source_id", resolution["trigger_source_url"], "OFFICIAL_TRIGGER_SOURCE_URL_MISMATCH"),
    ):
        registered = registry.get(str(verification.get(id_field, "")), {})
        registered_url = str(registered.get("url", "")).split("#", 1)[0].split("?", 1)[0].rstrip("/")
        expected_url = str(resolved_url).split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if registered_url and registered_url != expected_url:
            add_issue(issues, "error", code, f"{base}.official_verification.{id_field}", "The referenced checked source does not match the catalog-resolved official Google page.")
    if workbook_language == "en" and normalize_text(summary) != normalize_text(resolution["definition"]):
        add_issue(issues, "error", "OFFICIAL_EVENT_SUMMARY_MISMATCH", f"{base}.event_summary", "English official event summaries must use the resolved Google definition. Put website-specific timing and conditions in trigger instead.")
    if not _translation_status_valid(workbook_language, translation_status):
        add_issue(issues, "error", "OFFICIAL_TRANSLATION_STATUS_INVALID", f"{base}.official_verification.translation_status", "Record whether localized wording comes from an official localized source or an analyst translation of canonical Google wording.")


def _check_official_trigger_source(event: dict[str, Any], base: str, issues: list[Issue]) -> None:
    verification = event.get("official_verification", {})
    if not isinstance(verification, dict):
        return
    required_fields = {
        "trigger_source_id": ("OFFICIAL_TRIGGER_SOURCE_ID_MISSING", "Official events must reference the checked Google source used to design the firing condition."),
        "trigger_source_section": ("OFFICIAL_TRIGGER_SOURCE_SECTION_MISSING", "Official events must identify the implementation or event section used to design the firing condition."),
        "trigger_source_locator": ("OFFICIAL_TRIGGER_SOURCE_LOCATOR_MISSING", "Official events must pinpoint the implementation step, event heading, or instruction used to design the firing condition."),
    }
    for field, (code, message) in required_fields.items():
        if not str(verification.get(field, "")).strip():
            add_issue(issues, "error", code, f"{base}.official_verification.{field}", message)


def _check_event_trigger(event: dict[str, Any], base: str, issues: list[Issue]) -> None:
    trigger = " ".join(str(event.get("trigger", "")).split()).strip()
    if not trigger or GENERIC_TRIGGER_RE.fullmatch(trigger):
        add_issue(
            issues,
            "error",
            "EVENT_TRIGGER_LAZY",
            f"{base}.trigger",
            "State the concrete action or state, when it is sent, and the success/failure or repeat condition when relevant. Use a precise confirmation requirement when evidence is missing.",
        )


def check_event_wording(plan: dict[str, Any], event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    summary = str(event.get("event_summary", "")).strip()
    _check_human_definition(summary, f"{base}.event_summary", "EVENT_SUMMARY", issues)
    if classification in OFFICIAL_EVENT_CLASSES:
        resolution = resolve_event_semantics(event_name, classification, RECOMMENDED_CATALOG, SCENARIO_LIBRARY)
        if resolution:
            _check_official_event_resolution(plan, event, resolution, summary, base, issues)
        else:
            add_issue(issues, "error", "OFFICIAL_EVENT_SEMANTICS_UNRESOLVED", f"{base}.event_name", f"No bundled official semantic record resolves '{event_name}'.")
        _check_source_locator(event.get("official_verification"), f"{base}.official_verification", event_name, issues)
        _check_official_trigger_source(event, base, issues)
    _check_event_trigger(event, base, issues)


def check_parameter_wording(
    plan: dict[str, Any],
    parameter: dict[str, Any],
    index: int,
    issues: list[Issue],
) -> None:
    base = f"$.parameters[{index}]"
    name = str(parameter.get("parameter_name", ""))
    classification = str(parameter.get("classification", ""))
    description = str(parameter.get("description", "")).strip()
    _check_human_definition(description, f"{base}.description", "PARAMETER_DEFINITION", issues)
    if classification not in OFFICIAL_PARAMETER_CLASSES:
        return

    resolutions = resolve_parameter_semantics(
        name,
        classification,
        parameter_event_names(plan, name),
        RECOMMENDED_CATALOG,
        PARAMETER_LIBRARY,
    )
    if not resolutions:
        add_issue(issues, "error", "OFFICIAL_PARAMETER_SEMANTICS_UNRESOLVED", f"{base}.parameter_name", f"No official parameter definition resolves '{name}'.")
        return
    official_descriptions = {normalize_text(item["description"]) for item in resolutions}
    verification = parameter.get("official_verification", {})
    canonical = str(verification.get("canonical_wording", "")) if isinstance(verification, dict) else ""
    if normalize_text(canonical) not in official_descriptions:
        add_issue(
            issues,
            "error",
            "OFFICIAL_CANONICAL_WORDING_MISMATCH",
            f"{base}.official_verification.canonical_wording",
            "Keep the exact catalog-resolved Google parameter definition as canonical wording, including when the workbook wording is localized.",
        )
    workbook_language = str(plan.get("language_policy", {}).get("workbook_language", "en"))
    if workbook_language == "en" and normalize_text(description) not in official_descriptions:
        add_issue(
            issues,
            "error",
            "OFFICIAL_PARAMETER_DEFINITION_MISMATCH",
            f"{base}.description",
            "Official parameter definitions must use the resolved Google table-row definition and attached conditions.",
        )
    translation_status = str(verification.get("translation_status", "")) if isinstance(verification, dict) else ""
    valid_translation = "not_needed" if workbook_language == "en" else {"official_localized_source", "analyst_translation"}
    if (workbook_language == "en" and translation_status != valid_translation) or (
        workbook_language != "en" and translation_status not in valid_translation
    ):
        add_issue(
            issues,
            "error",
            "OFFICIAL_TRANSLATION_STATUS_INVALID",
            f"{base}.official_verification.translation_status",
            "Record whether localized wording comes from an official localized source or an analyst translation of canonical Google wording.",
        )
    official_types = {normalize_type(item.get("type")) for item in resolutions if item.get("type")}
    if official_types and normalize_type(parameter.get("type")) not in official_types:
        add_issue(issues, "error", "OFFICIAL_PARAMETER_TYPE_MISMATCH", f"{base}.type", f"Type must match the official definition: {', '.join(sorted(official_types))}.")
    _check_source_locator(parameter.get("official_verification"), f"{base}.official_verification", name, issues)


def _payload_parameter_names(event: dict[str, Any]) -> tuple[set[str], set[str]]:
    payload = event_ga4_payload(event)
    parameters = payload.get("parameters", {}) if isinstance(payload, dict) else {}
    event_names = set(parameters) if isinstance(parameters, dict) else set()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    item_names = {f"items[].{name}" for item in items if isinstance(item, dict) for name in item} if isinstance(items, list) else set()
    if isinstance(items, list) and items:
        event_names.add("items")
    return event_names, item_names


def _required_ecommerce_parameters(event_record: dict[str, Any]) -> set[str]:
    return {
        (f"items[].{parameter['name']}" if parameter.get("scope") == "item" else str(parameter["name"]))
        for parameter in event_record.get("parameters", [])
        if isinstance(parameter, dict) and normalize_text(parameter.get("required")) == "yes"
    }


def _check_required_ecommerce_parameters(base: str, selected: set[str], required: set[str], issues: list[Issue]) -> None:
    missing_required = sorted(required.difference(selected))
    if missing_required:
        add_issue(
            issues,
            "error",
            "OFFICIAL_REQUIRED_PARAMETER_NOT_SELECTED",
            f"{base}.parameters",
            f"Official required parameter(s) cannot be pruned: {', '.join(missing_required)}.",
        )

    item_identity = {"items[].item_id", "items[].item_name"}
    if ("items" in selected or "items" in required) and selected.isdisjoint(item_identity):
        add_issue(
            issues,
            "error",
            "OFFICIAL_ITEM_IDENTITY_NOT_SELECTED",
            f"{base}.parameters",
            "Select at least one official item identity field: items[].item_id or items[].item_name.",
        )


def _check_ecommerce_example_parity(base: str, event: dict[str, Any], selected: set[str], issues: list[Issue]) -> set[str]:
    payload_event, payload_items = _payload_parameter_names(event)
    selected_event = {name for name in selected if not name.startswith("items[].")}
    selected_items = {name for name in selected if name.startswith("items[].")}
    missing_from_example = sorted((selected_event - payload_event) | (selected_items - payload_items))
    unlisted_in_example = sorted((payload_event - selected_event) | (payload_items - selected_items))
    if missing_from_example:
        add_issue(issues, "error", "SELECTED_PARAMETER_NOT_IN_EXAMPLE", f"{base}.data_layer.push.ecommerce", f"Every selected ecommerce parameter must appear in the developer example: {', '.join(missing_from_example)}.")
    if unlisted_in_example:
        add_issue(issues, "error", "EXAMPLE_PARAMETER_NOT_SELECTED", f"{base}.parameters", f"Every ecommerce parameter in the developer example must be listed in the event specification: {', '.join(unlisted_in_example)}.")
    return payload_event


def _check_ecommerce_item_examples(base: str, event: dict[str, Any], issues: list[Issue]) -> None:
    payload = event_ga4_payload(event)
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return
    for item_index, item in enumerate(items):
        if not isinstance(item, dict) or str(item.get("item_id", "")).strip() or str(item.get("item_name", "")).strip():
            continue
        add_issue(
            issues,
            "error",
            "OFFICIAL_ITEM_IDENTITY_MISSING",
            f"{base}.data_layer.push.ecommerce.items[{item_index}]",
            "Each ecommerce item example needs item_id or item_name.",
        )


PURCHASE_PROPAGATED_PARAMETERS = {
    "shipping_tier",
    "payment_type",
    "items[].item_list_id",
    "items[].item_list_name",
}
WEAK_OFFICIAL_GAPS = {
    "",
    "none",
    "not applicable",
    "custom",
    "no official parameter",
    "tbd",
    "to confirm",
    "unknown",
}


def _check_purchase_parameter_lineage(
    event_name: str,
    name: str,
    binding: dict[str, Any],
    path: str,
    issues: list[Issue],
) -> None:
    if event_name != "purchase" or name not in PURCHASE_PROPAGATED_PARAMETERS:
        return
    if not str(binding.get("source_path", "")).strip():
        add_issue(issues, "error", "PROPAGATED_PARAMETER_SOURCE_MISSING", f"{path}.source_path", f"Purchase parameter '{name}' needs the event-specific source from which the confirmed order receives the value.")
    if not str(binding.get("persistence_rule", "")).strip():
        add_issue(issues, "error", "PROPAGATED_PARAMETER_PERSISTENCE_MISSING", f"{path}.persistence_rule", f"Purchase parameter '{name}' needs a capture, retention, fallback, and reset rule.")


def _check_unprescribed_event_parameter(
    event_name: str,
    name: str,
    binding: dict[str, Any],
    metadata_classification: str,
    path: str,
    issues: list[Issue],
) -> None:
    binding_classification = str(binding.get("classification", ""))
    effective_classification = binding_classification or metadata_classification
    if binding_classification in OFFICIAL_PARAMETER_CLASSES:
        add_issue(issues, "error", "EVENT_PARAMETER_CLASSIFICATION_INVALID", f"{path}.classification", f"Parameter '{name}' is not prescribed for {event_name}; do not classify this event binding as official.")
    elif metadata_classification in OFFICIAL_PARAMETER_CLASSES and not binding_classification:
        add_issue(issues, "error", "EVENT_PARAMETER_CLASSIFICATION_AMBIGUOUS", f"{path}.classification", f"Parameter '{name}' is official elsewhere in GA4 but not prescribed for {event_name}; classify this binding explicitly as a custom event or item parameter.")
    if effective_classification == "custom_event_parameter" and name.startswith("items[]."):
        add_issue(issues, "error", "EVENT_PARAMETER_CUSTOM_SCOPE_INVALID", f"{path}.classification", f"Item path '{name}' must use custom_item_parameter when it is not prescribed for {event_name}.")
    elif effective_classification == "custom_item_parameter" and not name.startswith("items[]."):
        add_issue(issues, "error", "EVENT_PARAMETER_CUSTOM_SCOPE_INVALID", f"{path}.classification", f"Event parameter '{name}' must use custom_event_parameter when it is not prescribed for {event_name}.")
    if binding_classification in CUSTOM_PARAMETER_CLASSIFICATIONS:
        official_gap = str(binding.get("official_gap", "")).strip()
        if official_gap.lower().rstrip(".") in WEAK_OFFICIAL_GAPS:
            add_issue(
                issues,
                "error",
                "EVENT_PARAMETER_OFFICIAL_GAP_MISSING",
                f"{path}.official_gap",
                f"Custom {event_name} binding '{name}' must identify the official fields reviewed and the specific need they do not answer.",
            )


def _check_prescribed_event_parameter(
    event_name: str,
    name: str,
    binding: dict[str, Any],
    record: dict[str, Any],
    path: str,
    issues: list[Issue],
) -> None:
    binding_classification = str(binding.get("classification", ""))
    if binding_classification in CUSTOM_PARAMETER_CLASSIFICATIONS:
        add_issue(issues, "error", "EVENT_PARAMETER_OFFICIAL_MISCLASSIFIED", f"{path}.classification", f"Parameter '{name}' is prescribed in the official {event_name} table and must not be classified as custom on this binding.")
    if name.startswith("items[].") and binding_classification and binding_classification != "ga4_ecommerce_item_parameter":
        add_issue(issues, "error", "EVENT_PARAMETER_OFFICIAL_SCOPE_INVALID", f"{path}.classification", f"Official item path '{name}' must use ga4_ecommerce_item_parameter on this binding.")
    expected = normalize_requiredness(record.get("required"))
    if binding.get("requirement") != expected:
        add_issue(issues, "error", "EVENT_PARAMETER_REQUIREDNESS_MISMATCH", f"{path}.requirement", f"Parameter '{name}' is '{expected}' for {event_name} in the official event table.")
    if not str(binding.get("official_source_id", "")).strip() or str(binding.get("official_source_locator", "")) != name:
        add_issue(issues, "error", "EVENT_PARAMETER_SOURCE_LOCATOR_INVALID", path, f"Official parameter '{name}' must reference its checked event-table source and exact parameter locator.")


def check_event_parameter_bindings(
    event: dict[str, Any],
    index: int,
    parameter_lookup: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{index}].parameter_bindings"
    bindings = event_parameter_bindings(event)
    names = [str(binding.get("parameter_name", "")) for binding in bindings]
    if len(names) != len(set(names)):
        add_issue(issues, "error", "DUPLICATE_EVENT_PARAMETER_BINDING", base, "An event may bind each parameter only once.")
    event_name = str(event.get("event_name", ""))
    official_event = event.get("classification") in OFFICIAL_EVENT_CLASSES
    for binding_index, binding in enumerate(bindings):
        path = f"{base}[{binding_index}]"
        name = str(binding.get("parameter_name", ""))
        requirement = str(binding.get("requirement", ""))
        condition = str(binding.get("condition", "")).strip()
        reason = str(binding.get("inclusion_reason", "")).strip()
        metadata_classification = str(parameter_lookup.get(name, {}).get("classification", ""))
        if requirement == "conditional" and not condition:
            add_issue(issues, "error", "CONDITIONAL_PARAMETER_CONDITION_MISSING", f"{path}.condition", f"Conditional parameter '{name}' needs the precise official or business condition that makes it required.")
        if requirement == "optional" and not reason:
            add_issue(issues, "error", "OPTIONAL_PARAMETER_REASON_WEAK", f"{path}.inclusion_reason", f"Optional parameter '{name}' needs a concrete analysis, segmentation, optimization, implementation, or diagnostic use.")
        owner = str(binding.get("data_owner", "")).strip()
        if binding.get("availability") in {"requires_development", "requires_backend", "to_confirm", "unavailable"} and owner.lower() in {"", "tbd", "to confirm", "unknown"}:
            add_issue(issues, "error", "EVENT_PARAMETER_OWNER_MISSING", f"{path}.data_owner", f"Parameter '{name}' needs a clear source owner for this event.")
        _check_purchase_parameter_lineage(event_name, name, binding, path, issues)
        if not official_event:
            continue
        event_record = next((item for item in RECOMMENDED_CATALOG if item.get("event") == event_name), None)
        if not event_record:
            continue
        record = event_parameter(RECOMMENDED_CATALOG, event_name, name)
        if not record:
            _check_unprescribed_event_parameter(event_name, name, binding, metadata_classification, path, issues)
            continue
        _check_prescribed_event_parameter(event_name, name, binding, record, path, issues)


def check_ecommerce_parameter_selection(event: dict[str, Any], index: int, issues: list[Issue]) -> None:
    if event.get("classification") != "recommended_ecommerce":
        return
    base = f"$.events[{index}]"
    event_name = str(event.get("event_name", ""))
    event_record = next((item for item in RECOMMENDED_CATALOG if item.get("event") == event_name), None)
    if not event_record:
        return
    selected = set(event_parameter_names(event))
    _check_required_ecommerce_parameters(base, selected, _required_ecommerce_parameters(event_record), issues)
    payload_event = _check_ecommerce_example_parity(base, event, selected, issues)
    if "value" in payload_event and "currency" not in payload_event:
        add_issue(issues, "error", "OFFICIAL_CONDITIONAL_PARAMETER_MISSING", f"{base}.data_layer.push.ecommerce", "currency is required when value is sent.")
    _check_ecommerce_item_examples(base, event, issues)


def check_quality_contract(plan: dict[str, Any], issues: list[Issue]) -> None:
    check_official_source_registry(plan, issues)
    check_official_verification_freshness(plan, issues)
    parameter_lookup = {
        str(parameter.get("parameter_name", "")): parameter
        for parameter in plan.get("parameters", [])
        if isinstance(parameter, dict)
    }
    for index, event in enumerate(plan.get("events", [])):
        if not isinstance(event, dict):
            continue
        check_event_wording(plan, event, index, issues)
        check_event_parameter_bindings(event, index, parameter_lookup, issues)
        check_ecommerce_parameter_selection(event, index, issues)
    for index, parameter in enumerate(plan.get("parameters", [])):
        if isinstance(parameter, dict):
            check_parameter_wording(plan, parameter, index, issues)
