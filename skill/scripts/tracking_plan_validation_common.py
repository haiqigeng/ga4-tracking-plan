from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from tracking_plan_validation_catalogs import WEAK_BUSINESS_QUESTIONS
from tracking_plan_validation_model import Issue, add_issue


def check_duplicates(values: list[str], label: str, path: str, issues: list[Issue]) -> None:
    for value, count in Counter(values).items():
        if value and count > 1:
            add_issue(issues, "error", "DUPLICATE_ID", path, f"{label} '{value}' appears {count} times.")


def walk_keys(value: Any, prefix: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            yield path, key
            yield from walk_keys(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_keys(child, f"{prefix}[{index}]")


def check_business_question(value: Any, path: str, issues: list[Issue]) -> None:
    question = str(value or "").strip()
    if not question:
        return
    normalized = question.lower().rstrip(".")
    if normalized in WEAK_BUSINESS_QUESTIONS:
        add_issue(
            issues,
            "error",
            "EVENT_BUSINESS_QUESTION_WEAK",
            path,
            "Business question must express the analysis need or decision supported by the event, not just the implementation action to track.",
        )


def check_official_verification(
    verification: Any,
    platform: str,
    path: str,
    issues: list[Issue],
    *,
    required: bool,
) -> None:
    if not isinstance(verification, dict):
        if required:
            add_issue(issues, "error", "OFFICIAL_VERIFICATION_MISSING", path, "Official-first choices need a registered source, locator, and scope note.")
        return
    status = str(verification.get("status", ""))
    source_id = str(verification.get("source_id", "")).strip()
    scope_note = str(verification.get("scope_note", "")).strip()
    if required and status != "verified":
        add_issue(issues, "error", "OFFICIAL_VERIFICATION_NOT_VERIFIED", f"{path}.status", "Official/native/recommended/platform-standard fields must be marked verified against official documentation.")
    if required and not source_id:
        add_issue(issues, "error", "OFFICIAL_VERIFICATION_SOURCE_MISSING", f"{path}.source_id", f"Official verification for {platform} must reference the checked-source registry.")
    if required and not scope_note:
        add_issue(issues, "error", "OFFICIAL_VERIFICATION_SCOPE_WEAK", f"{path}.scope_note", "Official verification must state event, item, property, or implementation scope clearly.")


def governed_sensitive_implementation_parameter(parameter: dict[str, Any]) -> bool:
    if parameter.get("scope") != "implementation" or parameter.get("classification") != "implementation_variable":
        return False
    if parameter.get("register_custom_definition"):
        return False
    governance = " ".join(
        str(parameter.get(key, ""))
        for key in ("value_rules", "consent_dependency", "reporting_purpose", "description")
    )
    return bool(re.search(r"not.*ga4|never.*ga4|google ads|non-ga4|user-id", governance, re.I))
