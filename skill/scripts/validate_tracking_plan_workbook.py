from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from import_tracking_plan_workbook import (
    MODEL_SHEET,
    PROJECTION_SHEET,
    import_workbook,
)
from openpyxl import load_workbook
from tracking_plan_model import (
    classification_label,
    compact_value,
    datalayer_code,
    event_journey_names,
    label,
    load_json,
    location_text,
    parameter_reference_rows,
    requirement_label,
    scope_label,
    value_rule_text,
)


def _value(sheet: Any, row: int, column: int) -> str:
    value = sheet.cell(row, column).value
    return "" if value is None else str(value).strip()


def validate_workbook(path: Path, plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    workbook = load_workbook(path, data_only=False, read_only=False)
    try:
        imported = import_workbook(path)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        return [str(error)]
    if imported != plan:
        errors.append("Embedded canonical model does not equal the delivery plan.")
    for internal in (MODEL_SHEET, PROJECTION_SHEET):
        if internal not in workbook.sheetnames:
            errors.append(f"Missing internal maintenance sheet {internal}.")
        elif workbook[internal].sheet_state != "veryHidden":
            errors.append(f"Internal maintenance sheet {internal} must be veryHidden.")

    if workbook.properties.creator != "ga4-tracking-plan":
        return errors

    reference_name = label(plan, "parameter_reference")
    required_sheets = {"Guide", "Event Matrix", reference_name}
    missing = required_sheets - set(workbook.sheetnames)
    if missing:
        errors.append("Default workbook is missing: " + ", ".join(sorted(missing)))
        return errors

    matrix = workbook["Event Matrix"]
    expected_headers = [label(plan, "event"), label(plan, "definition")]
    if [_value(matrix, 4, column) for column in (1, 2)] != expected_headers:
        errors.append("Event Matrix headers do not match the lean two-column contract.")
    if any(_value(matrix, 4, column) for column in range(3, matrix.max_column + 1)):
        errors.append("Event Matrix contains an unapproved visible column after Definition.")
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    observed_matrix = [
        (_value(matrix, row, 1), _value(matrix, row, 2))
        for row in range(5, 5 + len(events))
    ]
    expected_matrix = [
        (str(event.get("event_name", "")), str(event.get("definition", "")).strip())
        for event in events
    ]
    if observed_matrix != expected_matrix:
        errors.append("Event Matrix rows differ from the canonical events and definitions.")

    reference = workbook[reference_name]
    expected_reference = [
        (
            str(row["name"]),
            scope_label(plan, str(row["scope"])),
            str(row["type"]),
            str(row["definition"]),
            str(row["example"]),
            str(row["values"]),
            " | ".join(row["events"]),
        )
        for row in parameter_reference_rows(plan)
    ]
    observed_reference = [
        tuple(_value(reference, row, column) for column in range(1, 8))
        for row in range(5, 5 + len(expected_reference))
    ]
    if observed_reference != expected_reference:
        errors.append("Parameter Reference does not exactly project the canonical parameter semantics.")

    event_sheets = {
        _value(sheet, 3, 2): sheet
        for sheet in workbook.worksheets
        if _value(sheet, 3, 1) == label(plan, "event") and _value(sheet, 3, 2)
    }
    if set(event_sheets) != {str(event.get("event_name")) for event in events}:
        errors.append("Visible event tabs do not match the canonical event set.")
        return errors
    for event in events:
        event_name = str(event["event_name"])
        sheet = event_sheets[event_name]
        expected_fields = [
            event_name,
            classification_label(plan, str(event.get("classification", ""))),
            " | ".join(event_journey_names(plan, event)),
            str(event.get("definition", "")),
            str(event.get("trigger", "")),
            location_text(event),
            str(event.get("notes", "")),
        ]
        if [_value(sheet, row, 2) for row in range(3, 10)] != [
            value.strip() for value in expected_fields
        ]:
            errors.append(f'Event-tab header fields differ for "{event_name}".')
        parameters = [
            parameter
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
        ]
        expected_parameters = [
            (
                str(parameter.get("name", "")),
                scope_label(plan, str(parameter.get("scope", ""))),
                str(parameter.get("type", "")),
                requirement_label(plan, str(parameter.get("requirement", ""))),
                str(parameter.get("definition", "")),
                value_rule_text(parameter, plan),
                compact_value(parameter.get("example")),
            )
            for parameter in parameters
        ]
        observed_parameters = [
            tuple(_value(sheet, row, column) for column in range(1, 8))
            for row in range(12, 12 + len(parameters))
        ]
        if observed_parameters != expected_parameters:
            errors.append(f'Parameter rows differ for "{event_name}".')
        code_row = 14 + max(1, len(parameters))
        if _value(sheet, code_row, 1) != datalayer_code(event).strip():
            errors.append(f'dataLayer code differs for "{event_name}".')
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the rendered human workbook against canonical semantics."
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        errors = validate_workbook(args.workbook, load_json(args.plan))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if errors:
        print("\n".join(f"ERROR {error}" for error in errors), file=sys.stderr)
        return 1
    print(args.workbook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
