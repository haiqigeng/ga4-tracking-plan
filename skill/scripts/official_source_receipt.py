from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any


def canonical_receipt_payload(receipt: dict[str, Any]) -> bytes:
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def receipt_sha256(receipt: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_receipt_payload(receipt)).hexdigest()


def tracking_plan_sha256(plan: dict[str, Any]) -> str:
    payload = {key: value for key, value in plan.items() if key != "official_source_check"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def finalize_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    result = dict(receipt)
    result["receipt_sha256"] = receipt_sha256(result)
    return result


def new_receipt(
    *,
    status: str,
    mode: str,
    sources: list[dict[str, Any]],
    catalog_signature_sha256: str,
    draft_plan_sha256: str,
    resolved_plan_sha256: str,
    errors: list[str],
    checked_at: str | None = None,
) -> dict[str, Any]:
    return finalize_receipt(
        {
            "schema_version": "1.0",
            "status": status,
            "mode": mode,
            "checked_at": checked_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sources": sources,
            "catalog_signature_sha256": catalog_signature_sha256,
            "draft_plan_sha256": draft_plan_sha256,
            "resolved_plan_sha256": resolved_plan_sha256,
            "errors": errors,
        }
    )


def pending_receipt(reason: str = "Live official-source check has not been run.") -> dict[str, Any]:
    return new_receipt(
        status="not_run",
        mode="not_run",
        checked_at="",
        sources=[],
        catalog_signature_sha256="",
        draft_plan_sha256="",
        resolved_plan_sha256="",
        errors=[reason],
    )


def receipt_validation_errors(
    receipt: Any,
    publish_date: date | None = None,
    expected_urls: set[str] | None = None,
    expected_catalog_signature: str | None = None,
    expected_draft_plan_sha256: str | None = None,
    expected_resolved_plan_sha256: str | None = None,
) -> list[str]:
    if not isinstance(receipt, dict):
        return ["Official-source receipt is missing."]
    errors: list[str] = []
    if receipt.get("schema_version") != "1.0":
        errors.append("Official-source receipt must use schema_version 1.0.")
    if receipt.get("status") != "passed":
        errors.append("Official-source receipt status must be passed.")
    expected_hash = receipt_sha256(receipt)
    if receipt.get("receipt_sha256") != expected_hash:
        errors.append("Official-source receipt hash does not match its content.")
    if receipt.get("status") != "passed":
        return errors
    if receipt.get("mode") != "live":
        errors.append("Delivery requires a live official-source receipt; offline checks are maintenance-only.")
    sources = receipt.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("Official-source receipt must contain fetched source records.")
    else:
        fetched_urls: set[str] = set()
        for index, source in enumerate(sources):
            if not isinstance(source, dict) or not source.get("url") or not source.get("content_sha256"):
                errors.append(f"Official-source receipt source {index} needs url and content_sha256.")
            elif isinstance(source, dict):
                fetched_urls.add(str(source["url"]).split("#", 1)[0].rstrip("/"))
        missing_urls = sorted((expected_urls or set()).difference(fetched_urls))
        if missing_urls:
            errors.append("Official-source receipt did not fetch: " + ", ".join(missing_urls) + ".")
    checked_at = str(receipt.get("checked_at", ""))
    try:
        checked_date = datetime.fromisoformat(checked_at.replace("Z", "+00:00")).date()
    except ValueError:
        errors.append("Official-source receipt checked_at must be an ISO-8601 timestamp.")
    else:
        if publish_date and checked_date != publish_date:
            errors.append("Official sources must be checked on the tracking-plan publish date.")
    if receipt.get("errors"):
        errors.append("Official-source receipt contains check errors.")
    signature = str(receipt.get("catalog_signature_sha256", ""))
    if not signature:
        errors.append("Official-source receipt is missing the catalog signature.")
    elif expected_catalog_signature and signature != expected_catalog_signature:
        errors.append("Official-source receipt was produced for a different bundled GA4 catalog.")
    draft_hash = str(receipt.get("draft_plan_sha256", ""))
    if not draft_hash:
        errors.append("Official-source receipt is not bound to a checked draft plan.")
    elif expected_draft_plan_sha256 and draft_hash != expected_draft_plan_sha256:
        errors.append("Official-source receipt was produced for a different draft plan.")
    resolved_hash = str(receipt.get("resolved_plan_sha256", ""))
    if expected_resolved_plan_sha256:
        if not resolved_hash:
            errors.append("Official-source receipt is not bound to the resolved plan.")
        elif resolved_hash != expected_resolved_plan_sha256:
            errors.append("Resolved plan content changed after official-source resolution.")
    return errors
