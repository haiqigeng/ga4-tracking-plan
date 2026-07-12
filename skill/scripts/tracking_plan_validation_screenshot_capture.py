from __future__ import annotations

from typing import Any

from tracking_plan_validation_model import Issue, add_issue

CAPTURED_STATUSES = {"captured", "shared_evidence"}
COMPLETE_STATUSES = CAPTURED_STATUSES | {"not_needed"}
BLOCKED_STATUSES = {"blocked", "not_needed"}
PENDING_STATUSES = {"capture_required", "skip_allowed"}


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
    if outcome in {"blocked", "partially_captured"} and len(notice.split()) < 6:
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

    if "skip_allowed" in statuses:
        add_issue(
            issues,
            "error",
            "SCREENSHOT_SKIP_NOT_EXPLICIT",
            "$.screenshot_evidence",
            "Do not use skip_allowed to hide an unavailable capture. Use blocked evidence and an explicit Screenshot Register delivery notice.",
        )

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
        if captured_count == 0 or blocked_count == 0 or statuses & PENDING_STATUSES:
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
    if any(str(row.get("status", "")) != "not_needed" for row in rows):
        add_issue(
            issues,
            "error",
            "SCREENSHOT_EVIDENCE_NOT_REQUESTED",
            "$.screenshot_evidence",
            "A no-screenshot plan must mark every Screenshot Register row not_needed rather than leaving pending, skipped, or blocked evidence.",
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
