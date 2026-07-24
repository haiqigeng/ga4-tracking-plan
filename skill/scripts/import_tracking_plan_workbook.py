from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from tracking_plan_model import (
    BASE_SHEETS,
    CLASSIFICATION_LABELS,
    LABELS,
    REQUIREMENT_LABELS,
    SCOPE_LABELS,
    slugify,
)

MODEL_SHEET = "__tracking_plan_model"
MODEL_MARKER = "ga4-tracking-plan/model"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a generated GA4 tracking-plan workbook into its canonical JSON model."
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument(
        "--allow-visible-recovery",
        action="store_true",
        help="Recover a best-effort model from visible event tabs when no embedded model exists.",
    )
    return parser.parse_args()


def _normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).strip().casefold()


def _reverse_labels(table: dict[str, dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for translations in table.values():
        for key, value in translations.items():
            result[_normalized(value)] = key
    return result


CLASSIFICATION_BY_LABEL = _reverse_labels(CLASSIFICATION_LABELS)
SCOPE_BY_LABEL = _reverse_labels(SCOPE_LABELS)
REQUIREMENT_BY_LABEL = _reverse_labels(REQUIREMENT_LABELS)


def read_embedded_model(workbook) -> dict[str, Any] | None:
    if MODEL_SHEET not in workbook.sheetnames:
        return None
    sheet = workbook[MODEL_SHEET]
    if sheet.cell(1, 1).value != MODEL_MARKER:
        return None
    chunks: list[str] = []
    row = 2
    while sheet.cell(row, 1).value is not None:
        chunks.append(str(sheet.cell(row, 1).value))
        row += 1
    if not chunks:
        raise ValueError("The embedded tracking-plan model is empty.")
    value = json.loads("".join(chunks))
    if not isinstance(value, dict):
        raise ValueError("The embedded tracking-plan model is not a JSON object.")
    return value


def _cell_value(sheet, row: int, column: int) -> str:
    return str(sheet.cell(row, column).value or "").strip()


def _language_from_workbook(workbook) -> str:
    if "Valeurs des variables" in workbook.sheetnames:
        return "fr"
    for sheet in workbook.worksheets:
        values = {_normalized(cell.value) for row in sheet.iter_rows(max_row=20) for cell in row}
        if _normalized(LABELS["fr"]["definition"]) in values:
            return "fr"
    return "en"


def _parse_json_example(value: Any, expected_type: str) -> Any:
    if value is None:
        return None
    if expected_type in {"array", "object", "boolean", "integer", "number"}:
        try:
            return json.loads(str(value))
        except (json.JSONDecodeError, TypeError):
            pass
    return value


def _extract_push(code: str, event_name: str) -> dict[str, Any]:
    candidates = re.findall(
        r"window\.dataLayer\.push\(\s*(\{.*?\})\s*\);",
        code,
        flags=re.DOTALL,
    )
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and (value.get("event") == event_name or "event" not in value):
            return value
    return {"event": event_name}


def _event_tabs(workbook, language: str) -> list[Any]:
    event_label = _normalized(LABELS[language]["event"])
    result: list[Any] = []
    for sheet in workbook.worksheets:
        if sheet.title in BASE_SHEETS or sheet.title in {"Valeurs des variables", "Journal des modifications"}:
            continue
        if sheet.sheet_state != "visible":
            continue
        if _normalized(sheet.cell(3, 1).value) == event_label and _cell_value(sheet, 3, 2):
            result.append(sheet)
    return result


def _recover_visible_model(workbook, source: Path) -> dict[str, Any]:
    language = _language_from_workbook(workbook)
    sheets = _event_tabs(workbook, language)
    if not sheets:
        raise ValueError(
            "No embedded model or recognizable event tabs were found. "
            "Use inspect_tracking_plan_template.py and analyst-led semantic mapping for this workbook."
        )

    journey_by_name: dict[str, str] = {}
    events: list[dict[str, Any]] = []
    for sheet in sheets:
        event_name = _cell_value(sheet, 3, 2)
        classification = CLASSIFICATION_BY_LABEL.get(
            _normalized(_cell_value(sheet, 4, 2)), "custom"
        )
        journey_names = [
            item.strip()
            for item in _cell_value(sheet, 5, 2).split("|")
            if item.strip()
        ] or ["Imported journey"]
        for journey_name in journey_names:
            journey_by_name.setdefault(journey_name, slugify(journey_name))

        locations = [
            {"url_pattern": line.strip()}
            for line in _cell_value(sheet, 8, 2).splitlines()
            if line.strip()
        ] or [{"state": "Imported workbook; location requires review."}]

        headers = {
            _normalized(sheet.cell(11, column).value): column
            for column in range(1, sheet.max_column + 1)
            if sheet.cell(11, column).value
        }
        parameter_column = headers.get(_normalized(LABELS[language]["variable"]), 1)
        scope_column = headers.get(_normalized(LABELS[language]["scope_label"]), 2)
        type_column = headers.get(_normalized(LABELS[language]["type"]), 3)
        requirement_column = headers.get(_normalized(LABELS[language]["requirement"]), 4)
        condition_column = headers.get(_normalized(LABELS[language]["condition"]), 5)
        definition_column = headers.get(_normalized(LABELS[language]["definition"]), 6)
        values_column = headers.get(_normalized(LABELS[language]["values"]), 7)
        example_column = headers.get(_normalized(LABELS[language]["example"]), 8)
        source_column = headers.get(_normalized(LABELS[language]["source_path"]), 9)

        parameters: list[dict[str, Any]] = []
        row = 12
        while row <= sheet.max_row:
            name = _cell_value(sheet, row, parameter_column)
            if not name:
                break
            if "datalayer" in _normalized(name):
                break
            scope = SCOPE_BY_LABEL.get(
                _normalized(_cell_value(sheet, row, scope_column)), "event"
            )
            parameter_type = _cell_value(sheet, row, type_column) or "string"
            requirement = REQUIREMENT_BY_LABEL.get(
                _normalized(_cell_value(sheet, row, requirement_column)), "optional"
            )
            source_lines = _cell_value(sheet, row, source_column).splitlines()
            path = source_lines[0].strip() if source_lines else name
            parameter: dict[str, Any] = {
                "name": name,
                "data_layer_path": path,
                "classification": "implementation" if classification == "context" else "custom",
                "scope": scope,
                "type": parameter_type if parameter_type in {
                    "string", "integer", "number", "boolean", "array", "object"
                } else "string",
                "requirement": requirement,
                "definition": _cell_value(sheet, row, definition_column)
                or f"Imported definition for {name}.",
                "value_rule": _cell_value(sheet, row, values_column)
                or "Retain the source-workbook rule pending analyst review.",
                "example": _parse_json_example(
                    sheet.cell(row, example_column).value,
                    parameter_type,
                ),
                "source": "\n".join(source_lines[1:]).strip(),
                "destination": "implementation_only"
                if classification == "context"
                else ("ga4_item_parameter" if scope == "item" else "ga4_event_parameter"),
            }
            condition = _cell_value(sheet, row, condition_column)
            if requirement == "conditional":
                parameter["condition"] = condition or "Condition was not preserved in the source workbook."
            if parameter["classification"] == "custom":
                parameter["custom_decision"] = {
                    "business_need": f"Retain the imported {name} semantic until the analyst confirms its business use.",
                    "official_candidate": f"Resolve {name} against the current official table for {event_name}.",
                    "why_not_fit": "The source workbook did not preserve the prior official-gap decision.",
                }
            parameters.append(parameter)
            row += 1

        code = ""
        for candidate_row in range(row, sheet.max_row + 1):
            candidate = sheet.cell(candidate_row, 1).value
            if isinstance(candidate, str) and "window.dataLayer" in candidate:
                code = candidate
                break
        event: dict[str, Any] = {
            "event_name": event_name,
            "classification": classification,
            "journey_ids": [journey_by_name[name] for name in journey_names],
            "definition": _cell_value(sheet, 6, 2) or f"Imported event {event_name}.",
            "trigger": _cell_value(sheet, 7, 2) or "Trigger requires analyst review.",
            "locations": locations,
            "parameters": parameters,
            "data_layer": {"push": _extract_push(code, event_name)},
            "notes": (
                "Recovered from visible workbook content. Official sources and custom-gap decisions "
                "must be re-resolved before delivery."
            ),
        }
        if classification == "custom":
            event["custom_decision"] = {
                "business_need": f"Retain the imported {event_name} measurement until its business use is confirmed.",
                "official_candidate": "Resolve the event against the current official GA4 event catalog.",
                "why_not_fit": "The source workbook did not preserve the prior official-gap decision.",
            }
        events.append(event)

    journeys = [
        {
            "journey_id": journey_id,
            "name": name,
            "scope": "Recovered from event-tab associations.",
            "status": "partial",
            "business_goal": "Confirm the business goal during maintenance review.",
        }
        for name, journey_id in journey_by_name.items()
    ]
    return {
        "schema_version": "4.0.0",
        "document": {
            "title": source.stem,
            "version": "imported",
            "date": date.today().isoformat(),
            "language": language,
            "value_language": language,
            "scope": "Recovered from a workbook without an embedded canonical model.",
            "target_state": "hybrid",
            "notes": "Best-effort visible-content recovery; review before regeneration.",
        },
        "data_layer_convention": {
            "name": "Recovered workbook convention",
            "origin": "existing",
            "event_key": "event",
            "wrappers": {
                "page": "page",
                "event": "event_data",
                "ecommerce": "ecommerce",
                "user": "user",
            },
        },
        "journeys": journeys,
        "events": events,
    }


def import_workbook(path: Path, allow_visible_recovery: bool = False) -> dict[str, Any]:
    workbook = load_workbook(path, data_only=False, read_only=False)
    embedded = read_embedded_model(workbook)
    if embedded is not None:
        return embedded
    if not allow_visible_recovery:
        raise ValueError(
            "This workbook has no embedded canonical model. Re-run with --allow-visible-recovery "
            "for a best-effort import, then review every recovered semantic."
        )
    return _recover_visible_model(workbook, path)


def main() -> int:
    args = parse_args()
    try:
        plan = import_workbook(args.workbook, args.allow_visible_recovery)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
