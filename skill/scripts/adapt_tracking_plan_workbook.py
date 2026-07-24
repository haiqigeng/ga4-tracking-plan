from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from generate_tracking_plan_workbook import embed_model
from inspect_tracking_plan_template import sha256
from openpyxl import load_workbook
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string
from tracking_plan_model import (
    classification_label,
    compact_value,
    datalayer_code,
    event_journey_names,
    load_json,
    location_text,
    parameter_reference_rows,
    requirement_label,
    scope_label,
    value_rule_text,
)
from validate_tracking_plan import render_text, validate_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Semantically adapt a validated GA4 tracking plan into a supplied workbook."
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path, required=True)
    return parser.parse_args()


def _copy_row_style(sheet, source_row: int, target_row: int, columns: set[int]) -> None:
    for column in columns:
        source = sheet.cell(source_row, column)
        target = sheet.cell(target_row, column)
        if source.has_style:
            target._style = copy.copy(source._style)
        target.number_format = source.number_format
        target.protection = copy.copy(source.protection)
        target.alignment = copy.copy(source.alignment)
    sheet.row_dimensions[target_row].height = sheet.row_dimensions[source_row].height


def _existing_data_end(sheet, start_row: int, columns: set[int]) -> int:
    last = start_row - 1
    for row in range(start_row, min(sheet.max_row, start_row + 5000) + 1):
        populated = any(sheet.cell(row, column).value not in (None, "") for column in columns)
        if populated:
            last = row
        else:
            break
    return last


def _fill_region(
    workbook,
    region: dict[str, Any],
    rows: list[dict[str, Any]],
    value_for: Callable[[dict[str, Any], str], Any],
) -> None:
    if not region:
        return
    sheet = workbook[str(region["sheet"])]
    start_row = int(region["data_start_row"])
    columns = {str(key): int(value) for key, value in region["columns"].items()}
    mapped_columns = set(columns.values())
    end_row = _existing_data_end(sheet, start_row, mapped_columns)
    for row in range(start_row, end_row + 1):
        for column in mapped_columns:
            sheet.cell(row, column).value = None
    for offset, item in enumerate(rows):
        row = start_row + offset
        if offset and row > sheet.max_row:
            _copy_row_style(sheet, start_row, row, mapped_columns)
        elif offset:
            _copy_row_style(sheet, start_row, row, mapped_columns)
        for field, column in columns.items():
            sheet.cell(row, column, value_for(item, field))
    if sheet.auto_filter.ref:
        start_column = min(mapped_columns)
        end_column = max(mapped_columns)
        header_row = int(region["header_row"])
        sheet.auto_filter.ref = (
            f"{sheet.cell(header_row, start_column).coordinate}:"
            f"{sheet.cell(max(start_row, start_row + len(rows) - 1), end_column).coordinate}"
        )


def _event_matrix_value(plan: dict[str, Any], event: dict[str, Any], field: str) -> Any:
    values = {
        "journey": " | ".join(event_journey_names(plan, event)),
        "event": event.get("event_name", ""),
        "classification": classification_label(plan, str(event.get("classification", ""))),
        "definition": event.get("definition", ""),
        "trigger": event.get("trigger", ""),
        "locations": location_text(event),
        "variables": "\n".join(
            f'{parameter.get("name")} ({requirement_label(plan, str(parameter.get("requirement", "")))})'
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
        ),
        "datalayer": datalayer_code(event),
        "notes": event.get("notes", ""),
    }
    return values.get(field, "")


def _reference_value(plan: dict[str, Any], row: dict[str, Any], field: str) -> Any:
    values = {
        "variable": row.get("name", ""),
        "scope": scope_label(plan, str(row.get("scope", ""))),
        "type": row.get("type", ""),
        "definition": row.get("definition", ""),
        "example": row.get("example", ""),
        "values": row.get("values", ""),
        "concerned_events": " | ".join(row.get("events", [])),
    }
    return values.get(field, "")


def _coordinate_right(coordinate: str) -> str:
    letters, row = coordinate_from_string(coordinate)
    column = column_index_from_string(letters)
    from openpyxl.utils import get_column_letter

    return f"{get_column_letter(column + 1)}{row}"


def _fill_event_tab(
    workbook,
    plan: dict[str, Any],
    mapping: dict[str, Any],
    event: dict[str, Any],
) -> None:
    sheet = workbook[str(mapping["sheet"])]
    field_labels = mapping.get("field_labels", {})
    direct_values = {
        "event": event.get("event_name", ""),
        "journey": " | ".join(event_journey_names(plan, event)),
        "classification": classification_label(plan, str(event.get("classification", ""))),
        "definition": event.get("definition", ""),
        "trigger": event.get("trigger", ""),
        "locations": location_text(event),
        "notes": event.get("notes", ""),
    }
    for field, value in direct_values.items():
        if field in field_labels:
            sheet[_coordinate_right(str(field_labels[field]))] = value

    parameter_region = mapping.get("parameter_region") or {}
    if parameter_region:
        rows = [item for item in event.get("parameters", []) if isinstance(item, dict)]

        def parameter_value(parameter: dict[str, Any], field: str) -> Any:
            source = str(parameter.get("data_layer_path", ""))
            if parameter.get("source"):
                source += f'\n{parameter.get("source")}'
            values = {
                "variable": parameter.get("name", ""),
                "scope": scope_label(plan, str(parameter.get("scope", ""))),
                "type": parameter.get("type", ""),
                "requirement": requirement_label(plan, str(parameter.get("requirement", ""))),
                "condition": parameter.get("condition", ""),
                "definition": parameter.get("definition", ""),
                "values": value_rule_text(parameter, plan),
                "example": compact_value(parameter.get("example")),
                "source_path": source,
            }
            return values.get(field, "")

        _fill_region(workbook, parameter_region, rows, parameter_value)
    if mapping.get("data_layer_cell"):
        sheet[str(mapping["data_layer_cell"])] = datalayer_code(event)


def _event_tab_assignments(
    workbook,
    mappings: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[str]]:
    by_name = {str(event.get("event_name", "")): event for event in events}
    assignments: list[tuple[dict[str, Any], dict[str, Any]]] = []
    assigned: set[str] = set()
    blank_mappings: list[dict[str, Any]] = []
    for mapping in mappings:
        sheet = workbook[str(mapping["sheet"])]
        existing = str(sheet[str(mapping["event_name_cell"])].value or "").strip()
        if existing in by_name:
            assignments.append((mapping, by_name[existing]))
            assigned.add(existing)
        elif not existing:
            blank_mappings.append(mapping)
    remaining = [event for event in events if str(event.get("event_name", "")) not in assigned]
    for mapping, event in zip(blank_mappings, remaining):
        assignments.append((mapping, event))
        assigned.add(str(event.get("event_name", "")))
    missing = [
        str(event.get("event_name", ""))
        for event in events
        if str(event.get("event_name", "")) not in assigned
    ]
    return assignments, missing


def adapt(
    plan: dict[str, Any],
    template: Path,
    mapping: dict[str, Any],
):
    expected_hash = str(mapping.get("template", {}).get("sha256", ""))
    if expected_hash and sha256(template) != expected_hash:
        raise ValueError(
            "The supplied workbook no longer matches the inspected template hash. "
            "Inspect the current file again before adaptation."
        )
    workbook = load_workbook(
        template,
        data_only=False,
        read_only=False,
        keep_links=True,
        keep_vba=template.suffix.lower() == ".xlsm",
    )
    regions = mapping.get("regions", {})
    event_matrix = regions.get("event_matrix") or {}
    parameter_reference = regions.get("parameter_reference") or {}
    data_layer_table = regions.get("data_layer_table") or {}
    event_tabs = regions.get("event_tabs") or []
    if not event_matrix:
        raise ValueError("The mapping has no Event Matrix region for analyst review.")
    if not parameter_reference:
        raise ValueError("The mapping has no Parameter Reference region.")
    if not event_tabs and not data_layer_table:
        raise ValueError(
            "The mapping has no legitimate location for complete dataLayer examples. "
            "Approve and map a suitable template region before adaptation."
        )
    if (
        event_tabs
        and not data_layer_table
        and any(not item.get("data_layer_cell") for item in event_tabs)
    ):
        raise ValueError(
            "At least one mapped event tab has no dataLayer example cell. "
            "Map a legitimate code region before adaptation."
        )

    events = [item for item in plan.get("events", []) if isinstance(item, dict)]
    _fill_region(
        workbook,
        event_matrix,
        events,
        lambda item, field: _event_matrix_value(plan, item, field),
    )
    _fill_region(
        workbook,
        parameter_reference,
        parameter_reference_rows(plan),
        lambda item, field: _reference_value(plan, item, field),
    )
    if data_layer_table:
        _fill_region(
            workbook,
            data_layer_table,
            events,
            lambda item, field: _event_matrix_value(plan, item, field),
        )

    assignments, missing = _event_tab_assignments(workbook, event_tabs, events)
    for event_mapping, event in assignments:
        _fill_event_tab(workbook, plan, event_mapping, event)
    if missing and not data_layer_table:
        raise ValueError(
            "The template has no mapped event tab for: "
            + ", ".join(missing)
            + ". Do not add sheets without explicit template approval."
        )
    if (
        "__tracking_plan_model" in workbook.sheetnames
        or mapping.get("policy", {}).get("embed_internal_model") is True
    ):
        embed_model(workbook, plan)
    return workbook


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.plan)
        issues = validate_plan(plan)
        if issues:
            print(render_text(issues), file=sys.stderr)
        if any(item.severity == "error" for item in issues):
            return 1
        mapping = load_json(args.mapping)
        workbook = adapt(plan, args.template, mapping)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(args.output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
