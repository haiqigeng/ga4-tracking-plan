from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:password|passcode|secret|token|authorization|cookie|session|"
    r"email|e_mail|phone|mobile|first_name|last_name|firstname|lastname|"
    r"address|postal|postcode|zip|user_id|customer_id|card_number|cvv|iban)"
    r"(?:$|_)",
    re.I,
)
EMAIL_VALUE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_VALUE = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
BEARER_VALUE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+\b", re.I)


def _hashed_query_value(value: str) -> str:
    if not value:
        return ""
    return "sha256_" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def sanitize_evidence_url(value: str) -> str:
    """Keep the route and query keys while removing every query value and fragment."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return value
    query = urlencode(
        [(key, _hashed_query_value(raw)) for key, raw in parse_qsl(parsed.query, keep_blank_values=True)],
        doseq=True,
    )
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            query,
            "",
        )
    )


def _redact_text(value: str) -> str:
    value = EMAIL_VALUE.sub("[redacted_email]", value)
    value = PHONE_VALUE.sub("[redacted_phone]", value)
    return BEARER_VALUE.sub("Bearer [redacted]", value)


def sanitize_discovery_artifact(value: Any, *, key: str = "") -> Any:
    """Return a JSON-safe report copy without credentials, tokens, PII scalars, or URL values."""
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_discovery_artifact(
                child,
                key=str(child_key),
            )
            for child_key, child in value.items()
            if str(child_key).casefold() not in {"cookies", "origins", "storage_state"}
        }
    if isinstance(value, list):
        return [sanitize_discovery_artifact(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [sanitize_discovery_artifact(item, key=key) for item in value]
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            return sanitize_evidence_url(value)
        if SENSITIVE_KEY.search(key) and key not in {
            "environment_name",
            "storage_state_env",
        }:
            return "[redacted]" if value else ""
        if key.endswith("sha256") or key in {
            "run_id",
            "report_id",
            "recipe_id",
            "probe_id",
            "capability_id",
            "variant_id",
            "journey_id",
            "hint_id",
            "hint_key",
        }:
            return value
        return _redact_text(value)
    return value
