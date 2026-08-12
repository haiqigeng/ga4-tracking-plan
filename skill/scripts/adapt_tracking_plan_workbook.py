from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from create_default_template import set_cell_value
from generate_tracking_plan_workbook import embed_model
from inspect_tracking_plan_template import sha256
from openpyxl import load_workbook
from openpyxl.utils import quote_sheetname
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string
from template_fidelity import (
    add_package_fidelity,
    authorized_template_changes,
    compare_template_fidelity,
    workbook_fidelity_snapshot,
)
from tracking_plan_model import (
    classification_label,
    combined_value_rule_text,
    compact_value,
    datalayer_code,
    event_journey_names,
    load_json,
    location_text,
    parameter_reference_rows,
    possible_values_or_example,
    requirement_label,
    safe_sheet_title,
    scope_label,
    value_rule_text,
)
from validate_tracking_plan import render_text, validate_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Semantically adapt a validated GA4 tracking plan into a supplied workbook.")
    parser.add_argument("plan", type=Path)
    parser.add_argument("template", type=Path)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument(
        "--fidelity-report",
        type=Path,
        help="Optional JSON output for the mandatory supplied-template fidelity gate.",
    )
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
        populated_count = sum(sheet.cell(row, column).value not in (None, "") for column in columns)
        if populated_count:
            last = row
            continue
        lookahead_end = min(sheet.max_row, row + 3)
        table_like_ahead = any(
            sum(sheet.cell(candidate, column).value not in (None, "") for column in columns) >= 2 for candidate in range(row + 1, lookahead_end + 1)
        )
        if not table_like_ahead:
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
            cell = sheet.cell(row, column)
            cell.value = None
            cell.hyperlink = None
    for offset, item in enumerate(rows):
        row = start_row + offset
        if offset:
            _copy_row_style(sheet, start_row, row, mapped_columns)
        for field, column in columns.items():
            set_cell_value(sheet.cell(row, column), value_for(item, field))
    if sheet.auto_filter.ref:
        start_column = min(mapped_columns)
        end_column = max(mapped_columns)
        header_row = int(region["header_row"])
        sheet.auto_filter.ref = (
            f"{sheet.cell(header_row, start_column).coordinate}:{sheet.cell(max(start_row, start_row + len(rows) - 1), end_column).coordinate}"
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
            f"{parameter.get('name')} ({requirement_label(plan, str(parameter.get('requirement', '')))})"
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
        ),
        "datalayer": datalayer_code(event, plan.get("data_layer_convention")),
        "notes": event.get("notes", ""),
    }
    return values.get(field, "")


def _reference_value(plan: dict[str, Any], row: dict[str, Any], field: str) -> Any:
    values = {
        "variable": row.get("name", ""),
        "scope": scope_label(plan, str(row.get("scope", ""))),
        "type": row.get("type", ""),
        "definition": row.get("definition", ""),
        "rule": row.get("rule", ""),
        "possible_values_or_examples": row.get("possible_values_or_example", ""),
        "example": row.get("possible_values_or_example", ""),
        "values": (f"{row.get('rule', '')}\n{row.get('possible_values_or_example', '')}".strip()),
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
            set_cell_value(
                sheet[_coordinate_right(str(field_labels[field]))],
                value,
            )

    parameter_region = mapping.get("parameter_region") or {}
    if parameter_region:
        rows = [item for item in event.get("parameters", []) if isinstance(item, dict)]

        def parameter_value(parameter: dict[str, Any], field: str) -> Any:
            source = str(parameter.get("data_layer_path", ""))
            if parameter.get("source"):
                source += f"\n{parameter.get('source')}"
            values = {
                "variable": parameter.get("name", ""),
                "scope": scope_label(plan, str(parameter.get("scope", ""))),
                "type": parameter.get("type", ""),
                "requirement": requirement_label(plan, str(parameter.get("requirement", ""))),
                "condition": parameter.get("condition", ""),
                "definition": parameter.get("definition", ""),
                "rule": value_rule_text(parameter, plan),
                "possible_values_or_examples": possible_values_or_example(parameter),
                "values": combined_value_rule_text(parameter, plan),
                "example": compact_value(parameter.get("example")),
                "source_path": source,
            }
            return values.get(field, "")

        _fill_region(workbook, parameter_region, rows, parameter_value)
    if mapping.get("data_layer_cell"):
        set_cell_value(
            sheet[str(mapping["data_layer_cell"])],
            datalayer_code(event, plan.get("data_layer_convention")),
        )


def _event_tab_assignments(
    workbook,
    mappings: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> tuple[
    list[tuple[dict[str, Any], dict[str, Any], str]],
    list[str],
    list[tuple[dict[str, Any], str]],
]:
    by_name = {str(event.get("event_name", "")): event for event in events}
    assignments: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    assigned: set[str] = set()
    reusable_mappings: list[tuple[dict[str, Any], str]] = []
    non_reusable_mappings: list[tuple[dict[str, Any], str]] = []
    for mapping in mappings:
        sheet = workbook[str(mapping["sheet"])]
        existing = str(sheet[str(mapping["event_name_cell"])].value or "").strip()
        if existing in by_name:
            assignments.append((mapping, by_name[existing], existing))
            assigned.add(existing)
        elif not existing or mapping.get("reusable") is True:
            reusable_mappings.append((mapping, existing))
        else:
            non_reusable_mappings.append((mapping, existing))
    remaining = [event for event in events if str(event.get("event_name", "")) not in assigned]
    reused_count = 0
    for (mapping, existing), event in zip(reusable_mappings, remaining, strict=False):
        assignments.append((mapping, event, existing))
        assigned.add(str(event.get("event_name", "")))
        reused_count += 1
    missing = [str(event.get("event_name", "")) for event in events if str(event.get("event_name", "")) not in assigned]
    return (
        assignments,
        missing,
        [
            *reusable_mappings[reused_count:],
            *non_reusable_mappings,
        ],
    )


def _clear_event_tab(workbook, mapping: dict[str, Any]) -> None:
    sheet = workbook[str(mapping["sheet"])]
    field_labels = mapping.get("field_labels", {})
    for field in (
        "event",
        "journey",
        "classification",
        "definition",
        "trigger",
        "locations",
        "notes",
    ):
        coordinate = field_labels.get(field)
        if not coordinate:
            continue
        value_cell = sheet[_coordinate_right(str(coordinate))]
        value_cell.value = None
        value_cell.hyperlink = None
    parameter_region = mapping.get("parameter_region") or {}
    if parameter_region:
        _fill_region(workbook, parameter_region, [], lambda _item, _field: "")
    if mapping.get("data_layer_cell"):
        cell = sheet[str(mapping["data_layer_cell"])]
        cell.value = None
        cell.hyperlink = None
    sheet.sheet_state = "hidden"


def _clear_hyperlinks_to_sheets(workbook, sheet_names: set[str]) -> None:
    if not sheet_names:
        return
    prefixes = {prefix for name in sheet_names for prefix in (f"#{quote_sheetname(name)}!", f"#{name}!")}
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                hyperlink = cell.hyperlink
                target = str(getattr(hyperlink, "target", "") or "") if hyperlink else ""
                if target and any(target.startswith(prefix) for prefix in prefixes):
                    cell.hyperlink = None


def _link_event_matrix(
    workbook,
    region: dict[str, Any],
    events: list[dict[str, Any]],
    event_sheets: dict[str, str],
) -> None:
    event_column = (region.get("columns") or {}).get("event")
    if not event_column:
        return
    sheet = workbook[str(region["sheet"])]
    start_row = int(region["data_start_row"])
    for offset, event in enumerate(events):
        event_name = str(event.get("event_name", ""))
        target = event_sheets.get(event_name)
        if target:
            sheet.cell(start_row + offset, int(event_column)).hyperlink = f"#{quote_sheetname(target)}!A1"


def adapt(
    plan: dict[str, Any],
    template: Path,
    mapping: dict[str, Any],
):
    expected_hash = str(mapping.get("template", {}).get("sha256", ""))
    if expected_hash and sha256(template) != expected_hash:
        raise ValueError("The supplied workbook no longer matches the inspected template hash. Inspect the current file again before adaptation.")
    workbook = load_workbook(
        template,
        data_only=False,
        read_only=False,
        keep_links=True,
        keep_vba=template.suffix.lower() == ".xlsm",
    )
    fidelity_before = workbook_fidelity_snapshot(workbook)
    fidelity_authorized = authorized_template_changes(workbook, mapping, plan)
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
            "The mapping has no legitimate location for complete dataLayer examples. Approve and map a suitable template region before adaptation."
        )
    if event_tabs and not data_layer_table and any(not item.get("data_layer_cell") for item in event_tabs):
        raise ValueError("At least one mapped event tab has no dataLayer example cell. Map a legitimate code region before adaptation.")

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
        parameter_reference_rows(
            plan,
            str(parameter_reference.get("semantic_role", "all_used_parameters")),
        ),
        lambda item, field: _reference_value(plan, item, field),
    )
    if data_layer_table:
        _fill_region(
            workbook,
            data_layer_table,
            events,
            lambda item, field: _event_matrix_value(plan, item, field),
        )

    assignments, missing, unused = _event_tab_assignments(
        workbook,
        event_tabs,
        events,
    )
    obsolete_sheet_names: set[str] = set()
    event_sheets: dict[str, str] = {}
    for event_mapping, event, previous_event_name in assignments:
        original_sheet_name = str(event_mapping["sheet"])
        _fill_event_tab(workbook, plan, event_mapping, event)
        sheet = workbook[original_sheet_name]
        sheet.sheet_state = "visible"
        event_name = str(event.get("event_name", ""))
        if previous_event_name and previous_event_name != event_name and sheet.title.casefold() == previous_event_name.casefold():
            used = [name for name in workbook.sheetnames if name != sheet.title]
            new_title = safe_sheet_title(event_name, used)
            obsolete_sheet_names.add(sheet.title)
            sheet.title = new_title
        event_sheets[event_name] = sheet.title
    for event_mapping, previous_event_name in unused:
        if not previous_event_name:
            continue
        obsolete_sheet_names.add(str(event_mapping["sheet"]))
        _clear_event_tab(workbook, event_mapping)
    if missing and not data_layer_table:
        raise ValueError("The template has no mapped event tab for: " + ", ".join(missing) + ". Do not add sheets without explicit template approval.")
    _clear_hyperlinks_to_sheets(workbook, obsolete_sheet_names)
    _link_event_matrix(workbook, event_matrix, events, event_sheets)
    embed_model(workbook, plan)
    fidelity_report = compare_template_fidelity(
        fidelity_before,
        workbook_fidelity_snapshot(workbook),
        fidelity_authorized,
    )
    if fidelity_report["violations"]:
        first = ", ".join(
            f"{item.get('kind')}:{item.get('sheet', item.get('sheet_index', ''))}" + (f"!{item.get('coordinate')}" if item.get("coordinate") else "")
            for item in fidelity_report["violations"][:12]
        )
        raise ValueError("Supplied-template fidelity gate failed for unmapped content: " + first)
    workbook._ga4_template_fidelity_report = fidelity_report
    workbook._ga4_template_fidelity_before = fidelity_before
    workbook._ga4_template_fidelity_authorized = fidelity_authorized
    return workbook


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.plan)
        issues = validate_plan(plan)
        if issues:
            print(render_text(issues), file=sys.stderr)
        if issues:
            return 1
        mapping = load_json(args.mapping)
        workbook = adapt(plan, args.template, mapping)
        if args.template.suffix.lower() == ".xlsm" and args.output.suffix.lower() != ".xlsm":
            raise ValueError("An XLSM supplied template must be delivered as XLSM.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(args.output)
        reopened = load_workbook(
            args.output,
            data_only=False,
            read_only=False,
            keep_links=True,
            keep_vba=args.output.suffix.lower() == ".xlsm",
        )
        final_fidelity = compare_template_fidelity(
            workbook._ga4_template_fidelity_before,
            workbook_fidelity_snapshot(reopened),
            workbook._ga4_template_fidelity_authorized,
        )
        final_fidelity = add_package_fidelity(
            final_fidelity,
            args.template,
            args.output,
        )
        if final_fidelity["violations"]:
            raise ValueError("Saved supplied-template fidelity gate failed: " + ", ".join(str(item.get("kind")) for item in final_fidelity["violations"][:12]))
        if args.fidelity_report:
            args.fidelity_report.parent.mkdir(parents=True, exist_ok=True)
            args.fidelity_report.write_text(
                json.dumps(
                    final_fidelity,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
