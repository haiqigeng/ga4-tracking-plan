from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from import_tracking_plan_workbook import import_workbook
from tracking_plan_model import load_json
from validate_tracking_plan import render_text, validate_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a semantic change log between two GA4 tracking plans."
    )
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument(
        "--allow-visible-recovery",
        action="store_true",
        help=(
            "Allow best-effort recovery when an XLSX input has no embedded "
            "canonical model."
        ),
    )
    parser.add_argument(
        "--reconcile-visible-edits",
        action="store_true",
        help="Reconcile supported visible event-tab edits in XLSX inputs before diffing.",
    )
    return parser.parse_args()


def load_plan(
    path: Path,
    allow_visible_recovery: bool = False,
    reconcile_visible_edits: bool = False,
) -> dict[str, Any]:
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return import_workbook(
            path,
            allow_visible_recovery,
            reconcile_visible_edits,
        )
    return load_json(path)


def _change(
    action: str,
    entity: str,
    key: str,
    summary: str,
    before: Any = None,
    after: Any = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "action": action,
        "entity": entity,
        "key": key,
        "summary": summary,
    }
    if before is not None:
        value["before"] = before
    if after is not None:
        value["after"] = after
    return value


def _indexed(values: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get(key)): item
        for item in values
        if isinstance(item, dict) and item.get(key)
    }


def _parameter_key(parameter: dict[str, Any]) -> str:
    return "|".join(
        str(parameter.get(name, ""))
        for name in ("name", "scope")
    )


def _parameter_display_key(parameter: dict[str, Any]) -> str:
    return "|".join(
        str(parameter.get(name, ""))
        for name in ("name", "scope", "data_layer_path")
    )


def _compare_parameters(
    event_name: str,
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    previous = {_parameter_key(item): item for item in before}
    current = {_parameter_key(item): item for item in after}
    changes: list[dict[str, Any]] = []
    for key in sorted(current.keys() - previous.keys()):
        parameter = current[key]
        changes.append(
            _change(
                "added",
                "parameter",
                f"{event_name}:{_parameter_display_key(parameter)}",
                f'Added parameter "{parameter.get("name")}" to "{event_name}".',
                after=parameter,
            )
        )
    for key in sorted(previous.keys() - current.keys()):
        parameter = previous[key]
        changes.append(
            _change(
                "deprecated",
                "parameter",
                f"{event_name}:{_parameter_display_key(parameter)}",
                f'Removed parameter "{parameter.get("name")}" from "{event_name}".',
                before=parameter,
            )
        )
    for key in sorted(previous.keys() & current.keys()):
        old = previous[key]
        new = current[key]
        display_key = _parameter_display_key(new)
        old_without_values = {k: v for k, v in old.items() if k != "allowed_values"}
        new_without_values = {k: v for k, v in new.items() if k != "allowed_values"}
        if old.get("allowed_values") != new.get("allowed_values"):
            changes.append(
                _change(
                    "changed",
                    "value_domain",
                    f"{event_name}:{display_key}",
                    f'Changed the finite values for "{new.get("name")}" on "{event_name}".',
                    before=old.get("allowed_values"),
                    after=new.get("allowed_values"),
                )
            )
        if old_without_values != new_without_values:
            changes.append(
                _change(
                    "changed",
                    "parameter",
                    f"{event_name}:{display_key}",
                    f'Changed parameter "{new.get("name")}" on "{event_name}".',
                    before=old_without_values,
                    after=new_without_values,
                )
            )
    return changes


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    if before.get("schema_version") != after.get("schema_version"):
        changes.append(
            _change(
                "changed",
                "document",
                "schema_version",
                "Changed canonical schema version.",
                before.get("schema_version"),
                after.get("schema_version"),
            )
        )
    previous_document = before.get("document", {})
    current_document = after.get("document", {})
    for field in sorted(set(previous_document) | set(current_document)):
        if previous_document.get(field) != current_document.get(field):
            changes.append(
                _change(
                    "changed",
                    "document",
                    f"document:{field}",
                    f'Changed document {field.replace("_", " ")}.',
                    previous_document.get(field),
                    current_document.get(field),
                )
            )
    if before.get("data_layer_convention") != after.get("data_layer_convention"):
        changes.append(
            _change(
                "changed",
                "data_layer_convention",
                "data_layer_convention",
                "Changed the declared dataLayer convention.",
                before.get("data_layer_convention"),
                after.get("data_layer_convention"),
            )
        )
    previous_journeys = _indexed(before.get("journeys", []), "journey_id")
    current_journeys = _indexed(after.get("journeys", []), "journey_id")
    for key in sorted(current_journeys.keys() - previous_journeys.keys()):
        changes.append(
            _change("added", "journey", key, f'Added journey "{key}".', after=current_journeys[key])
        )
    for key in sorted(previous_journeys.keys() - current_journeys.keys()):
        changes.append(
            _change("deprecated", "journey", key, f'Removed journey "{key}".', before=previous_journeys[key])
        )
    for key in sorted(previous_journeys.keys() & current_journeys.keys()):
        if previous_journeys[key] != current_journeys[key]:
            changes.append(
                _change(
                    "changed",
                    "journey",
                    key,
                    f'Changed journey "{key}".',
                    previous_journeys[key],
                    current_journeys[key],
                )
            )

    previous_events = _indexed(before.get("events", []), "event_name")
    current_events = _indexed(after.get("events", []), "event_name")
    for key in sorted(current_events.keys() - previous_events.keys()):
        changes.append(
            _change("added", "event", key, f'Added event "{key}".', after=current_events[key])
        )
    for key in sorted(previous_events.keys() - current_events.keys()):
        changes.append(
            _change("deprecated", "event", key, f'Removed event "{key}".', before=previous_events[key])
        )
    for key in sorted(previous_events.keys() & current_events.keys()):
        old = previous_events[key]
        new = current_events[key]
        event_fields = (set(old) | set(new)) - {"event_name", "parameters"}
        for field in sorted(event_fields):
            entity = {
                "trigger": "trigger",
                "data_layer": "data_layer",
                "business_question": "business_question",
                "custom_decision": "custom_decision",
            }.get(field, "event")
            if old.get(field) != new.get(field):
                changes.append(
                    _change(
                        "changed",
                        entity,
                        f"{key}:{field}",
                        f'Changed {field.replace("_", " ")} for "{key}".',
                        old.get(field),
                        new.get(field),
                    )
                )
        changes.extend(
            _compare_parameters(
                key,
                [item for item in old.get("parameters", []) if isinstance(item, dict)],
                [item for item in new.get("parameters", []) if isinstance(item, dict)],
            )
        )

    counts = {
        action: sum(1 for item in changes if item["action"] == action)
        for action in ("added", "changed", "deprecated")
    }
    return {
        "before_version": before.get("document", {}).get("version", ""),
        "after_version": after.get("document", {}).get("version", ""),
        "summary": counts,
        "changes": changes,
    }


def main() -> int:
    args = parse_args()
    try:
        before = load_plan(
            args.before,
            args.allow_visible_recovery,
            args.reconcile_visible_edits,
        )
        after = load_plan(
            args.after,
            args.allow_visible_recovery,
            args.reconcile_visible_edits,
        )
        issues = [*validate_plan(before), *validate_plan(after)]
        if issues:
            raise ValueError(
                "Semantic diff requires two delivery-valid canonical inputs:\n"
                + render_text(issues)
            )
        result = compare(before, after)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
