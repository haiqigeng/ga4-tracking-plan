from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from tracking_plan_validation_common import check_duplicates
from tracking_plan_validation_model import Issue, add_issue

CAPTURED_STATUSES = {"captured", "shared_evidence"}
COMPLETE_STATUSES = CAPTURED_STATUSES | {"not_needed"}
BLOCKED_STATUSES = {"blocked", "not_needed"}
GENERIC_SCREENSHOT_EVENTS = {"page_view", "view_item_list", "select_item", "view_item"}
FINITE_SCREENSHOT_EVENTS = {
    "header_click",
    "menu_click",
    "submenu_click",
    "footer_click",
    "login",
    "sign_up",
    "payment_error",
    "checkout_error",
    "newsletter_subscribe",
    "contact_submit",
    "catalog_request",
    "start_return",
    "cancel_order",
    "update_profile",
    "update_preferences",
    "password_reset",
}


def screenshot_capture_requirement(plan: dict[str, Any]) -> str:
    capture = plan.get("screenshot_capture", {})
    return str(capture.get("requirement", "")) if isinstance(capture, dict) else ""


def evidence_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in plan.get("screenshot_evidence", []) if isinstance(row, dict)]


def _all_supplied(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and all(
        str(row.get("status", "")) in CAPTURED_STATUSES and str(row.get("file_name", "")).strip()
        for row in rows
    )


def _check_notice(capture: dict[str, Any], base: str, issues: list[Issue]) -> None:
    notice = str(capture.get("delivery_notice", "")).strip()
    outcome = str(capture.get("outcome", ""))
    if "screenshot" not in notice.lower():
        add_issue(
            issues,
            "error",
            "SCREENSHOT_DELIVERY_NOTICE_UNCLEAR",
            f"{base}.delivery_notice",
            "The delivery notice must explicitly state the screenshot-capture outcome for the analyst.",
        )
    if outcome in {"blocked", "partially_captured"} and not notice:
        add_issue(
            issues,
            "error",
            "SCREENSHOT_DELIVERY_NOTICE_TOO_SHORT",
            f"{base}.delivery_notice",
            "A blocked or partial capture needs a concrete analyst-facing explanation, not a terse status.",
        )


def _check_required_capture(capture: dict[str, Any], rows: list[dict[str, Any]], base: str, issues: list[Issue]) -> None:
    attempt = capture.get("playwright_mcp_attempt", {})
    attempt_status = str(attempt.get("status", "")) if isinstance(attempt, dict) else ""
    outcome = str(capture.get("outcome", ""))
    statuses = {str(row.get("status", "")) for row in rows}

    if attempt_status == "not_recorded":
        add_issue(
            issues,
            "error",
            "PLAYWRIGHT_MCP_ATTEMPT_MISSING",
            f"{base}.playwright_mcp_attempt.status",
            "A migrated or new plan cannot be delivered until a Playwright MCP attempt is recorded, unless every final screenshot was supplied by the requester.",
        )
    elif attempt_status == "not_required" and not _all_supplied(rows):
        add_issue(
            issues,
            "error",
            "PLAYWRIGHT_MCP_ATTEMPT_MISSING",
            f"{base}.playwright_mcp_attempt.status",
            "Required screenshot capture needs a Playwright MCP attempt before fallback. 'not_required' is valid only when every final screenshot was supplied by the requester.",
        )

    if outcome not in {"captured", "partially_captured", "blocked"}:
        add_issue(
            issues,
            "error",
            "SCREENSHOT_CAPTURE_OUTCOME_INVALID",
            f"{base}.outcome",
            "Required screenshot capture must be captured, partially_captured, or blocked.",
        )
        return

    captured_count = sum(str(row.get("status", "")) in CAPTURED_STATUSES for row in rows)
    blocked_count = sum(str(row.get("status", "")) == "blocked" for row in rows)
    if outcome == "captured":
        if captured_count == 0 or not statuses <= COMPLETE_STATUSES:
            add_issue(
                issues,
                "error",
                "SCREENSHOT_CAPTURE_INCOMPLETE",
                f"{base}.outcome",
                "A captured outcome requires final captured/shared evidence for every required screenshot row and no blocked or pending rows.",
            )
    elif outcome == "partially_captured":
        if captured_count == 0 or blocked_count == 0:
            add_issue(
                issues,
                "error",
                "SCREENSHOT_CAPTURE_PARTIAL_MISMATCH",
                f"{base}.outcome",
                "A partially_captured outcome needs both captured/shared evidence and blocked rows, with no pending or silent skips.",
            )
    elif outcome == "blocked" and (not rows or not statuses <= BLOCKED_STATUSES):
        add_issue(
            issues,
            "error",
            "SCREENSHOT_CAPTURE_BLOCKED_MISMATCH",
            f"{base}.outcome",
            "A blocked outcome requires every screenshot row to be blocked or explicitly not needed.",
        )


def _check_not_requested_capture(capture: dict[str, Any], rows: list[dict[str, Any]], base: str, issues: list[Issue]) -> None:
    attempt = capture.get("playwright_mcp_attempt", {})
    attempt_status = str(attempt.get("status", "")) if isinstance(attempt, dict) else ""
    outcome = str(capture.get("outcome", ""))
    if attempt_status != "not_required" or outcome != "not_requested":
        add_issue(
            issues,
            "error",
            "SCREENSHOT_NOT_REQUESTED_MISMATCH",
            base,
            "When screenshots are not requested, the Playwright MCP attempt must be not_required and the capture outcome must be not_requested.",
        )
    if rows:
        add_issue(
            issues,
            "error",
            "SCREENSHOT_EVIDENCE_NOT_REQUESTED",
            "$.screenshot_evidence",
            "A no-screenshot plan must omit Screenshot Register evidence rows entirely.",
        )


def check_screenshot_capture(plan: dict[str, Any], issues: list[Issue]) -> None:
    capture = plan.get("screenshot_capture", {})
    if not isinstance(capture, dict):
        return
    base = "$.screenshot_capture"
    requirement = screenshot_capture_requirement(plan)
    rows = evidence_rows(plan)
    _check_notice(capture, base, issues)
    if requirement == "required":
        _check_required_capture(capture, rows, base, issues)
    elif requirement == "not_requested":
        _check_not_requested_capture(capture, rows, base, issues)


def check_screenshot_row(
    row: dict[str, Any],
    index: int,
    event_ids: set[str],
    covered: Counter[str],
    file_usage: defaultdict[str, list[dict[str, Any]]],
    issues: list[Issue],
) -> None:
    base = f"$.screenshot_evidence[{index}]"
    related = [str(value) for value in row.get("event_ids", [])]
    for event_id in related:
        if event_id not in event_ids:
            add_issue(issues, "error", "SCREENSHOT_EVENT_UNKNOWN", f"{base}.event_ids", f"Screenshot evidence references unknown event_id '{event_id}'.")
        covered[event_id] += 1
    status = str(row.get("status", ""))
    file_name = str(row.get("file_name", "")).strip()
    if status in CAPTURED_STATUSES and not file_name:
        add_issue(issues, "error", "SCREENSHOT_FILE_MISSING", f"{base}.file_name", f"Screenshot status '{status}' requires an explicit evidence file name.")
    if status == "shared_evidence" and len(related) < 2:
        add_issue(issues, "error", "SCREENSHOT_SHARED_WITH_ONE_EVENT", f"{base}.event_ids", "shared_evidence must reference at least two events.")
    if status == "shared_evidence" and not str(row.get("shared_reason", "")).strip():
        add_issue(issues, "error", "SCREENSHOT_SHARED_REASON_WEAK", f"{base}.shared_reason", "Shared screenshot evidence needs a clear reason describing the common page state or interaction.")
    if file_name:
        file_usage[file_name.lower()].append(row)


def screenshot_rows_by_event(
    events: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    issues: list[Issue],
) -> defaultdict[str, list[dict[str, Any]]]:
    rows_by_event: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    events_by_id = {str(event.get("event_id", "")): event for event in events}
    for row in rows:
        for event_id in row.get("event_ids", []):
            rows_by_event[str(event_id)].append(row)
        related_names = {
            str(events_by_id.get(str(event_id), {}).get("event_name", ""))
            for event_id in row.get("event_ids", [])
        }
        if row.get("status") in CAPTURED_STATUSES and any(name and name != "page_view" for name in related_names) and not row.get("annotation"):
            add_issue(issues, "error", "SCREENSHOT_ANNOTATION_MISSING", "$.screenshot_evidence", "Captured interaction or visible-outcome evidence needs a bold red rectangle and no overlay text. Only a pure page_view example normally omits it.")
    return rows_by_event


def check_representative_screenshot(index: int, scenarios: list[str], rows: list[dict[str, Any]], issues: list[Issue]) -> None:
    row_scenarios = {str(row.get("scenario_id", "")) for row in rows}
    if len(scenarios) != 1 or len(rows) != 1 or row_scenarios != set(scenarios):
        add_issue(issues, "error", "REPRESENTATIVE_SCREENSHOT_INVALID", f"$.events[{index}].screenshot_coverage", "Representative screenshot coverage needs exactly one scenario and one matching evidence row.")


def check_all_scenario_screenshots(index: int, scenarios: list[str], rows: list[dict[str, Any]], issues: list[Issue]) -> None:
    row_scenarios = {str(row.get("scenario_id", "")) for row in rows}
    missing = sorted(set(scenarios) - row_scenarios)
    if not scenarios or missing:
        add_issue(issues, "error", "SCREENSHOT_SCENARIOS_MISSING", f"$.events[{index}].screenshot_coverage.scenarios", f"All finite screenshot scenarios need evidence rows. Missing: {', '.join(missing) or 'scenario inventory'}.")


def check_not_needed_screenshot(index: int, scenarios: list[str], rows: list[dict[str, Any]], issues: list[Issue]) -> None:
    if scenarios or rows:
        add_issue(issues, "error", "SCREENSHOT_NOT_NEEDED_INVALID", f"$.events[{index}].screenshot_coverage", "Not-needed coverage must have no scenarios and no evidence rows.")


def check_event_screenshot_mode(
    event: dict[str, Any],
    index: int,
    rows: list[dict[str, Any]],
    screenshots_not_requested: bool,
    issues: list[Issue],
) -> None:
    coverage = event.get("screenshot_coverage", {})
    if not isinstance(coverage, dict):
        return
    mode = str(coverage.get("mode", ""))
    scenarios = [str(value) for value in coverage.get("scenarios", [])]
    event_name = str(event.get("event_name", ""))
    if screenshots_not_requested:
        if mode != "not_needed" or scenarios:
            add_issue(
                issues,
                "error",
                "SCREENSHOT_COVERAGE_NOT_REQUESTED",
                f"$.events[{index}].screenshot_coverage",
                "When screenshots are not requested, event screenshot coverage must be not_needed with no scenarios.",
            )
            return
        check_not_needed_screenshot(index, scenarios, rows, issues)
        return
    if event_name in GENERIC_SCREENSHOT_EVENTS and mode != "representative":
        add_issue(issues, "error", "GENERIC_SCREENSHOT_MODE_INVALID", f"$.events[{index}].screenshot_coverage.mode", f"Repetitive generic event '{event_name}' needs one representative screenshot, not one screenshot per page or item.")
    if event_name in FINITE_SCREENSHOT_EVENTS and mode != "all_material_scenarios":
        add_issue(issues, "error", "FINITE_SCREENSHOT_MODE_INVALID", f"$.events[{index}].screenshot_coverage.mode", f"Finite event '{event_name}' needs all materially different visible scenarios listed for screenshot coverage.")
    if mode == "representative":
        check_representative_screenshot(index, scenarios, rows, issues)
    elif mode == "all_material_scenarios":
        check_all_scenario_screenshots(index, scenarios, rows, issues)
    elif mode == "not_needed":
        check_not_needed_screenshot(index, scenarios, rows, issues)


def check_screenshot_coverage(
    events: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    screenshots_not_requested: bool,
    issues: list[Issue],
) -> None:
    rows_by_event = screenshot_rows_by_event(events, rows, issues)
    for index, event in enumerate(events):
        event_id = str(event.get("event_id", ""))
        check_event_screenshot_mode(event, index, rows_by_event[event_id], screenshots_not_requested, issues)


def check_screenshot_evidence(plan: dict[str, Any], issues: list[Issue]) -> None:
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    event_ids = {str(event.get("event_id", "")) for event in events}
    rows = evidence_rows(plan)
    check_duplicates(
        [str(row.get("evidence_id", "")) for row in rows],
        "evidence_id",
        "$.screenshot_evidence",
        issues,
    )

    covered: Counter[str] = Counter()
    file_usage: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        check_screenshot_row(row, index, event_ids, covered, file_usage, issues)

    screenshots_not_requested = screenshot_capture_requirement(plan) == "not_requested"
    for event_id in sorted(event_ids):
        if covered[event_id] == 0 and not screenshots_not_requested:
            add_issue(issues, "error", "SCREENSHOT_EVENT_MISSING", "$.screenshot_evidence", f"Event '{event_id}' needs a screenshot-evidence row or an explicit not-needed decision.")

    for file_name, reused_rows in file_usage.items():
        related_events = {event_id for row in reused_rows for event_id in row.get("event_ids", [])}
        if len(reused_rows) > 1 and len(related_events) > 1 and not all(row.get("status") == "shared_evidence" for row in reused_rows):
            add_issue(
                issues,
                "warning",
                "SCREENSHOT_REUSE_NOT_EXPLICIT",
                "$.screenshot_evidence",
                f"Screenshot '{file_name}' is reused across events without one explicit shared_evidence row.",
            )
    check_screenshot_coverage(events, rows, screenshots_not_requested, issues)
