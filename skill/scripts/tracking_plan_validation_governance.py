from __future__ import annotations

import re
from typing import Any

from tracking_plan_contract import parameter_value_domain
from tracking_plan_validation_model import Issue, add_issue

CONTROLLED_VALUE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
CORE_PAGE_FIELDS = {
    "page_location",
    "page_title",
    "page_referrer",
    "page_template",
    "nav_language",
    "nav_environment",
}
ACTUAL_BROWSER_ATTEMPTS = {"completed", "blocked", "unavailable"}
BROWSER_SOURCE_TYPES = {"playwright_crawl", "browser_exploration"}
OBSERVED_VALUE_SOURCE_TYPES = BROWSER_SOURCE_TYPES | {"synthetic_account_exploration"}
FINITE_VALUE_MODES = {"observed_exhaustive", "client_confirmed", "official_standard", "proposed_taxonomy"}
FRENCH_ENGLISH_SEMANTIC_VALUES = {
    "logged_in",
    "logged_out",
    "signed_in",
    "signed_out",
    "home",
    "homepage",
    "product_list",
    "product_detail",
    "cart",
    "checkout",
    "development",
    "staging",
    "returning",
    "new_customer",
    "existing_customer",
    "unknown",
}


def check_language_policy(plan: dict[str, Any], issues: list[Issue]) -> None:
    policy = plan.get("language_policy", {})
    if not isinstance(policy, dict):
        return
    scope = str(policy.get("site_language_scope", ""))
    workbook_language = str(policy.get("workbook_language", ""))
    value_language = str(policy.get("controlled_value_language", ""))
    languages = [str(value) for value in policy.get("site_languages", []) if str(value).strip()]
    base = "$.language_policy"

    if scope == "multilingual" and (workbook_language != "en" or value_language != "en"):
        add_issue(issues, "error", "MULTILINGUAL_LANGUAGE_POLICY_INVALID", base, "Multilingual and multi-market plans must use English workbook wording and English controlled values.")
    if scope == "single_language" and len(languages) != 1:
        add_issue(issues, "error", "SINGLE_LANGUAGE_SCOPE_INVALID", f"{base}.site_languages", "A single-language plan must identify exactly one observed or client-confirmed site language.")
    if scope == "multilingual" and len(languages) < 2:
        add_issue(issues, "error", "MULTILINGUAL_SCOPE_UNSUPPORTED", f"{base}.site_languages", "A multilingual decision needs at least two observed or client-confirmed site languages.")
    if scope == "unknown" and value_language != "en":
        add_issue(issues, "error", "UNKNOWN_LANGUAGE_POLICY_INVALID", base, "Use English controlled values provisionally while website language scope remains unknown; workbook wording may follow an explicit user or template choice.")
    if not str(policy.get("decision_basis", "")).strip():
        add_issue(issues, "error", "LANGUAGE_DECISION_BASIS_WEAK", f"{base}.decision_basis", "Explain whether the language decision came from the client template, brief, website selector, locale routes, or confirmed site scope.")


def _check_controlled_values(
    parameter: dict[str, Any],
    index: int,
    controlled_value_language: str,
    issues: list[Issue],
) -> None:
    domain = parameter_value_domain(parameter)
    entries = domain.get("entries", [])
    entries = entries if isinstance(entries, list) else []
    mode = str(domain.get("mode", ""))
    if mode == "official_standard":
        return
    for value_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        normalized = str(entry.get("normalized_value", ""))
        path = f"$.parameters[{index}].value_domain.entries[{value_index}]"
        if not CONTROLLED_VALUE_RE.fullmatch(normalized):
            add_issue(issues, "error", "CONTROLLED_VALUE_FORMAT_INVALID", f"{path}.normalized_value", "Controlled values must use lowercase ASCII snake_case in the selected controlled-value language.")
        raw_language = str(entry.get("language", ""))
        method = str(entry.get("mapping_method", ""))
        if controlled_value_language == "fr" and normalized in FRENCH_ENGLISH_SEMANTIC_VALUES and method != "official_or_technical_value":
            add_issue(
                issues,
                "error",
                "FRENCH_CONTROLLED_VALUE_NOT_TRANSLATED",
                f"{path}.normalized_value",
                "French controlled semantic values must be translated before normalization; keep English only for official, technical, or authoritative raw-system values.",
            )
        if raw_language not in {controlled_value_language, "und", "zxx"} and method != "translated_to_controlled_language":
            add_issue(
                issues,
                "error",
                "CONTROLLED_VALUE_TRANSLATION_UNDECLARED",
                f"{path}.mapping_method",
                "A raw label from another language must explicitly map through translated_to_controlled_language.",
            )
        if raw_language == controlled_value_language and method == "translated_to_controlled_language":
            add_issue(issues, "error", "CONTROLLED_VALUE_TRANSLATION_UNNECESSARY", f"{path}.mapping_method", "A raw label already in the controlled-value language should use normalization_only.")
        if entry.get("source_ref") and str(entry.get("source_ref")) not in {str(value) for value in domain.get("source_refs", [])}:
            add_issue(issues, "error", "VALUE_ENTRY_SOURCE_UNREGISTERED", f"{path}.source_ref", "Each value-level source must also appear in the value domain source_refs list.")


def _check_finite_domain(
    mode: str,
    entries: list[Any],
    refs: list[str],
    base: str,
    issues: list[Issue],
) -> None:
    if entries and mode not in FINITE_VALUE_MODES:
        add_issue(issues, "error", "VALUE_DOMAIN_MODE_INVALID", f"{base}.value_domain.mode", "Finite values must be observed exhaustively, client-confirmed, officially standardized, or a transparent proposed taxonomy.")
    if mode not in {"observed_exhaustive", "client_confirmed"}:
        return
    if not entries:
        add_issue(issues, "error", "FINITE_VALUE_LIST_MISSING", f"{base}.value_domain.entries", "An exhaustive or client-confirmed finite domain needs evidence-bearing values.")
    if len(entries) > 20:
        add_issue(issues, "error", "FINITE_VALUE_LIST_TOO_LARGE", f"{base}.value_domain.entries", "Domains above 20 values should use a governed rule or partial evidence instead of an exhaustive workbook list.")
    if not refs:
        add_issue(issues, "error", "FINITE_VALUE_EVIDENCE_MISSING", f"{base}.value_domain.source_refs", "Exhaustive and client-confirmed values need browser, page, interaction, or authoritative client evidence references.")


def _check_observed_domain(
    mode: str,
    refs: list[str],
    observed_evidence_refs: set[str],
    base: str,
    issues: list[Issue],
) -> None:
    if mode == "observed_exhaustive" and refs and not observed_evidence_refs.intersection(refs):
        add_issue(
            issues,
            "error",
            "OBSERVED_VALUE_BROWSER_EVIDENCE_MISSING",
            f"{base}.value_domain.source_refs",
            "Observed exhaustive values must reference a recorded Playwright, browser-exploration, or synthetic account-exploration source.",
        )


def _check_rule_domain(
    parameter: dict[str, Any],
    mode: str,
    entries: list[Any],
    refs: list[str],
    base: str,
    issues: list[Issue],
) -> None:
    if mode in {"observed_partial", "governed_rule", "not_applicable", "blocked"} and entries:
        add_issue(issues, "error", "NONFINITE_VALUE_LIST_PRESENT", f"{base}.value_domain.entries", f"Value domain mode '{mode}' must use a rule or example, not a finite value list.")
    if mode == "observed_partial" and (not refs or not str(parameter.get("example_value", "")).strip()):
        add_issue(issues, "error", "PARTIAL_VALUE_EVIDENCE_MISSING", f"{base}.value_domain", "Observed partial domains need evidence references and one representative example value.")
    if mode == "official_standard" and not refs:
        add_issue(issues, "error", "OFFICIAL_VALUE_STANDARD_MISSING", f"{base}.value_domain.source_refs", "Official-standard values need the governing standard or official documentation reference.")
    if mode in {"governed_rule", "blocked"} and not str(parameter.get("value_rules", "")).strip():
        add_issue(issues, "error", "VALUE_RULE_TOO_WEAK", f"{base}.value_rules", "Dynamic or blocked value domains need a precise format, source, sanitization, or confirmation rule.")


def _check_value_mode(parameter: dict[str, Any], index: int, observed_evidence_refs: set[str], issues: list[Issue]) -> None:
    base = f"$.parameters[{index}]"
    domain = parameter_value_domain(parameter)
    raw_entries = domain.get("entries", [])
    entries = raw_entries if isinstance(raw_entries, list) else []
    mode = str(domain.get("mode", ""))
    refs = [str(value) for value in domain.get("source_refs", []) if str(value).strip()]
    _check_finite_domain(mode, entries, refs, base, issues)
    _check_observed_domain(mode, refs, observed_evidence_refs, base, issues)
    _check_rule_domain(parameter, mode, entries, refs, base, issues)


def check_value_domains(plan: dict[str, Any], issues: list[Issue]) -> None:
    coverage = plan.get("website_coverage_map", {})
    coverage = coverage if isinstance(coverage, dict) else {}
    observed_evidence_refs = {
        str(source.get("source_ref", ""))
        for source in coverage.get("sources_checked", [])
        if isinstance(source, dict) and source.get("source_type") in OBSERVED_VALUE_SOURCE_TYPES
    }
    research = coverage.get("browser_exploration", {})
    if isinstance(research, dict):
        observed_evidence_refs.update(str(value) for value in research.get("evidence_refs", []) if str(value).strip())
    controlled_value_language = str(plan.get("language_policy", {}).get("controlled_value_language", ""))
    for index, parameter in enumerate(plan.get("parameters", [])):
        if not isinstance(parameter, dict):
            continue
        _check_controlled_values(parameter, index, controlled_value_language, issues)
        _check_value_mode(parameter, index, observed_evidence_refs, issues)


def check_browser_exploration(plan: dict[str, Any], issues: list[Issue]) -> None:
    coverage = plan.get("website_coverage_map", {})
    if not isinstance(coverage, dict):
        return
    research = coverage.get("browser_exploration", {})
    if not isinstance(research, dict):
        return
    base = "$.website_coverage_map.browser_exploration"
    whole_site = coverage.get("site_scope") == "whole_site"
    requirement = str(research.get("requirement", ""))
    attempt = research.get("playwright_mcp_attempt", {})
    attempt_status = str(attempt.get("status", "")) if isinstance(attempt, dict) else ""

    if whole_site and requirement != "required":
        add_issue(issues, "error", "WHOLE_SITE_BROWSER_EXPLORATION_NOT_REQUIRED", f"{base}.requirement", "Whole-site planning requires live browser exploration even when screenshots are excluded.")
    if requirement == "required" and attempt_status not in ACTUAL_BROWSER_ATTEMPTS:
        add_issue(issues, "error", "PLAYWRIGHT_EXPLORATION_ATTEMPT_MISSING", f"{base}.playwright_mcp_attempt.status", "Record an actual Playwright MCP attempt before claiming website journey or value coverage.")
    if attempt_status == "completed" and not str(research.get("selected_browser", "")).strip():
        add_issue(issues, "error", "BROWSER_CHANNEL_MISSING", f"{base}.selected_browser", "Record the eligible browser or Playwright channel used for live exploration.")
    source_types = {str(source.get("source_type", "")) for source in coverage.get("sources_checked", []) if isinstance(source, dict)}
    if attempt_status == "completed" and not source_types.intersection(BROWSER_SOURCE_TYPES):
        add_issue(issues, "error", "BROWSER_EVIDENCE_SOURCE_MISSING", "$.website_coverage_map.sources_checked", "A completed browser exploration needs a matching browser_exploration or playwright_crawl coverage source.")
    outcomes = {str(research.get("journey_discovery_status", "")), str(research.get("value_discovery_status", ""))}
    if outcomes.intersection({"partial", "blocked"}) and not coverage.get("coverage_gaps"):
        add_issue(issues, "error", "BROWSER_RESEARCH_GAP_MISSING", "$.website_coverage_map.coverage_gaps", "Partial or blocked journey/value discovery needs a concrete coverage gap and next step.")


def check_cmp_and_core_context(plan: dict[str, Any], issues: list[Issue]) -> None:
    user_context = plan.get("user_context", {})
    user_required = isinstance(user_context, dict) and user_context.get("status") != "not_applicable"
    user_id_required = user_required and bool(user_context.get("ga4_user_id", {}).get("enabled"))

    for index, event in enumerate(plan.get("events", [])):
        if not isinstance(event, dict) or not isinstance(event.get("data_layer"), dict):
            continue
        data_layer = event["data_layer"]
        push = data_layer.get("push", {})
        if not isinstance(push, dict):
            continue
        event_name = str(event.get("event_name", ""))
        timing = str(data_layer.get("consent_timing", ""))
        base = f"$.events[{index}].data_layer"

        if event_name == "page_view" and timing != "core_context_before_cmp_ready":
            add_issue(issues, "error", "PAGE_CONTEXT_CMP_TIMING_INVALID", f"{base}.consent_timing", "A page_view/core-context push must be marked core_context_before_cmp_ready.")
        if event_name != "page_view" and timing != "after_cmp_ready":
            add_issue(issues, "error", "EVENT_CMP_TIMING_INVALID", f"{base}.consent_timing", "Every non-page manual dataLayer event must be pushed after CMP readiness.")
        if event_name != "page_view":
            continue

        page = push.get("page", {})
        page_keys = set(page) if isinstance(page, dict) else set()
        missing_page = sorted(CORE_PAGE_FIELDS.difference(page_keys))
        if missing_page:
            add_issue(issues, "error", "CORE_PAGE_CONTEXT_INCOMPLETE", f"{base}.push.page", f"Page/core context is missing: {', '.join(missing_page)}.")
        if not user_required:
            continue
        user = push.get("user", {})
        user_keys = set(user) if isinstance(user, dict) else set()
        if "login_status" not in user_keys:
            add_issue(issues, "error", "CORE_USER_CONTEXT_INCOMPLETE", f"{base}.push.user", "Planned connected-user context requires login_status in the page/core push.")
        if user_id_required and "user_id" not in user_keys:
            add_issue(issues, "error", "CORE_USER_ID_CONTEXT_MISSING", f"{base}.push.user", "Enabled GA4 User-ID requires user.user_id in the page/core context, with omit-before-login and null-after-logout handling.")


def check_governance_contract(plan: dict[str, Any], issues: list[Issue]) -> None:
    check_language_policy(plan, issues)
    check_value_domains(plan, issues)
    check_browser_exploration(plan, issues)
    check_cmp_and_core_context(plan, issues)
