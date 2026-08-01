from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JSON_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        item_schema = _schema_from_value(value[0]) if value else {}
        return {"type": "array", "items": item_schema}
    if isinstance(value, dict):
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                str(key): _schema_from_value(child) for key, child in value.items()
            },
            "required": [],
        }
    return {"type": ["null", "string", "number", "boolean", "object", "array"]}


def _parameter_schema(parameter: dict[str, Any]) -> dict[str, Any]:
    parameter_type = str(parameter.get("type", "string"))
    schema: dict[str, Any] = {
        "type": parameter_type if parameter_type in JSON_TYPES else "string",
        "description": str(parameter.get("definition", "")),
    }
    if parameter.get("allowed_values"):
        schema["enum"] = parameter["allowed_values"]
    return schema


def _apply_parameter(
    root: dict[str, Any],
    parameter: dict[str, Any],
) -> None:
    parts = [part for part in str(parameter.get("data_layer_path", "")).split(".") if part]
    current = root
    required_path = parameter.get("requirement") == "required"
    for index, raw_part in enumerate(parts):
        is_array = raw_part.endswith("[]")
        name = raw_part[:-2] if is_array else raw_part
        final = index == len(parts) - 1
        current.setdefault("type", "object")
        current.setdefault("additionalProperties", False)
        properties = current.setdefault("properties", {})
        if required_path:
            required = current.setdefault("required", [])
            if name not in required:
                required.append(name)
        if final:
            inferred = _parameter_schema(parameter)
            if is_array:
                inferred = {"type": "array", "items": inferred}
            existing = properties.get(name, {})
            if existing.get("type") == "array" and inferred.get("type") == "array":
                existing.update(
                    {
                        key: value
                        for key, value in inferred.items()
                        if key not in {"items"}
                    }
                )
                existing.setdefault("items", inferred.get("items", {}))
                properties[name] = existing
            else:
                properties[name] = {**existing, **inferred}
            return
        existing = properties.get(name)
        if is_array:
            if not isinstance(existing, dict) or existing.get("type") != "array":
                existing = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {},
                        "required": [],
                    },
                }
                properties[name] = existing
            current = existing.setdefault("items", {})
        else:
            if not isinstance(existing, dict) or existing.get("type") != "object":
                existing = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {},
                    "required": [],
                }
                properties[name] = existing
            current = existing


def event_push_schema(event: dict[str, Any]) -> dict[str, Any]:
    event_name = str(event.get("event_name", ""))
    push = event.get("data_layer", {}).get("push", {})
    schema = _schema_from_value(push)
    schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://example.invalid/ga4-tracking-plan/events/{event_name}.schema.json",
            "title": f'dataLayer push contract for "{event_name}"',
        }
    )
    if "event" in push:
        schema.setdefault("properties", {})["event"] = {
            "type": "string",
            "const": event_name,
        }
        required = schema.setdefault("required", [])
        if "event" not in required:
            required.append("event")
    for parameter in event.get("parameters", []):
        if isinstance(parameter, dict):
            _apply_parameter(schema, parameter)
    _sort_required(schema)
    return schema


def _sort_required(schema: Any) -> None:
    if isinstance(schema, dict):
        if isinstance(schema.get("required"), list):
            schema["required"] = sorted(dict.fromkeys(schema["required"]))
            if not schema["required"]:
                schema.pop("required")
        for child in schema.values():
            _sort_required(child)
    elif isinstance(schema, list):
        for child in schema:
            _sort_required(child)


def expected_events_contract(plan: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for event in plan.get("events", []):
        if not isinstance(event, dict):
            continue
        parameters = [
            {
                "name": parameter.get("name"),
                "scope": parameter.get("scope"),
                "type": parameter.get("type"),
                "requirement": parameter.get("requirement"),
                **(
                    {"condition": parameter.get("condition")}
                    if parameter.get("condition")
                    else {}
                ),
                "data_layer_path": parameter.get("data_layer_path"),
                "destination": parameter.get("destination"),
            }
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
        ]
        event_name = str(event.get("event_name", ""))
        events.append(
            {
                "event_name": event_name,
                "classification": event.get("classification"),
                "journey_ids": event.get("journey_ids", []),
                **(
                    {"business_question": event.get("business_question")}
                    if event.get("business_question")
                    else {}
                ),
                "trigger": event.get("trigger"),
                "locations": event.get("locations", []),
                "clear_before_push": event.get("data_layer", {}).get("clear", []),
                "push_schema": f"schemas/{event_name}.schema.json",
                "parameters": parameters,
            }
        )
    return {
        "contract_version": "1.0.0",
        "plan_version": str(plan.get("document", {}).get("version", "")),
        "data_layer_convention": plan.get("data_layer_convention", {}),
        "events": events,
    }


def build_handoff(
    *,
    skill_version: str,
    plan: dict[str, Any],
    analysis_context: dict[str, Any],
    approval_state: str,
    approved_by: str | None,
    artifact_paths: list[tuple[Path, str]],
    root: Path,
) -> dict[str, Any]:
    artifacts = [
        {
            "path": path.relative_to(root).as_posix(),
            "role": role,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path, role in artifact_paths
    ]
    canonical = next(
        (artifact for artifact in artifacts if artifact["role"] == "canonical_tracking_plan"),
        {},
    )
    upstream = [
        {
            "source_id": source.get("source_id"),
            "source_type": source.get("source_type"),
            "reference": source.get("reference"),
            "evidence_role": source.get("evidence_role"),
            "state": source.get("state"),
            **({"sha256": source.get("sha256")} if source.get("sha256") else {}),
        }
        for source in analysis_context.get("sources", [])
        if isinstance(source, dict)
    ]
    target_sites = sorted(
        {
            str(source.get("reference"))
            for source in analysis_context.get("sources", [])
            if isinstance(source, dict)
            and source.get("source_type") == "live_website"
            and str(source.get("reference", "")).startswith(("http://", "https://"))
        }
    )
    return {
        "handoff_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skill": {"name": "ga4-tracking-plan", "version": skill_version},
        "plan": {
            "title": plan.get("document", {}).get("title"),
            "version": plan.get("document", {}).get("version"),
            "schema_version": plan.get("schema_version"),
            "target_state": plan.get("document", {}).get("target_state"),
            "language": plan.get("document", {}).get("language"),
            "scope": plan.get("document", {}).get("scope"),
            "canonical_sha256": canonical.get("sha256"),
            "target_sites": target_sites,
        },
        "approval": {
            "state": approval_state,
            **({"approved_by": approved_by} if approved_by else {}),
        },
        "upstream_evidence": upstream,
        "artifacts": artifacts,
    }
