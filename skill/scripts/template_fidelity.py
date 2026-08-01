from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

INTERNAL_PREFIX = "__tracking_plan_"


def _value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _cell_snapshot(cell: Any) -> dict[str, Any]:
    hyperlink = cell.hyperlink.target if cell.hyperlink is not None else None
    return {
        "value": _value(cell.value),
        "data_type": str(cell.data_type),
        "hyperlink": hyperlink,
        "style_id": int(cell.style_id),
        "number_format": str(cell.number_format),
        "comment": str(cell.comment.text) if cell.comment else None,
    }


def workbook_fidelity_snapshot(workbook: Any) -> dict[str, Any]:
    sheets: list[dict[str, Any]] = []
    for index, sheet in enumerate(workbook.worksheets):
        if sheet.title.startswith(INTERNAL_PREFIX):
            continue
        cells = {
            cell.coordinate: _cell_snapshot(cell)
            for cell in sheet._cells.values()
            if cell.value not in (None, "")
            or cell.hyperlink is not None
            or cell.comment is not None
            or cell.has_style
        }
        sheets.append(
            {
                "index": index,
                "title": sheet.title,
                "state": sheet.sheet_state,
                "cells": cells,
                "merged_cells": sorted(str(item) for item in sheet.merged_cells.ranges),
                "image_count": len(sheet._images),
                "table_names": sorted(sheet.tables.keys()),
                "data_validation_count": len(sheet.data_validations.dataValidation),
                "freeze_panes": str(sheet.freeze_panes or ""),
                "auto_filter": str(sheet.auto_filter.ref or ""),
                "print_area": str(sheet.print_area or ""),
                "print_title_rows": str(sheet.print_title_rows or ""),
                "print_title_cols": str(sheet.print_title_cols or ""),
            }
        )
    return {"snapshot_version": "1.0.0", "sheets": sheets}


def _right(coordinate: str) -> str:
    letters, row = coordinate_from_string(coordinate)
    return f"{get_column_letter(column_index_from_string(letters) + 1)}{row}"


def authorized_template_changes(
    workbook: Any,
    mapping: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    title_to_index = {sheet.title: index for index, sheet in enumerate(workbook.worksheets)}
    cells: set[tuple[int, str]] = set()
    sheet_title_state: set[int] = set()
    auto_filter: set[int] = set()
    obsolete_targets: set[str] = set()

    def add_region(region: dict[str, Any], row_count: int) -> None:
        if not region:
            return
        title = str(region["sheet"])
        index = title_to_index[title]
        sheet = workbook[title]
        start = int(region["data_start_row"])
        columns = {int(value) for value in region.get("columns", {}).values()}
        last_existing = start - 1
        for row in range(start, min(sheet.max_row, start + 5000) + 1):
            if any(sheet.cell(row, column).value not in (None, "") for column in columns):
                last_existing = row
        end = max(last_existing, start + max(0, row_count - 1))
        for row in range(start, end + 1):
            for column in columns:
                cells.add((index, sheet.cell(row, column).coordinate))
        auto_filter.add(index)

    regions = mapping.get("regions", {})
    events = [item for item in plan.get("events", []) if isinstance(item, dict)]
    add_region(regions.get("event_matrix") or {}, len(events))
    add_region(
        regions.get("parameter_reference") or {},
        len(
            {
                (str(parameter.get("name")), str(parameter.get("scope")))
                for event in events
                for parameter in event.get("parameters", [])
                if isinstance(parameter, dict)
            }
        ),
    )
    add_region(regions.get("data_layer_table") or {}, len(events))

    max_parameter_count = max(
        (len(event.get("parameters", [])) for event in events),
        default=0,
    )
    for event_mapping in regions.get("event_tabs") or []:
        title = str(event_mapping["sheet"])
        index = title_to_index[title]
        sheet_title_state.add(index)
        existing = str(
            workbook[title][str(event_mapping["event_name_cell"])].value or ""
        ).strip()
        if existing and existing not in {
            str(event.get("event_name", "")) for event in events
        }:
            obsolete_targets.add(title)
        for coordinate in (event_mapping.get("field_labels") or {}).values():
            cells.add((index, _right(str(coordinate))))
        parameter_region = event_mapping.get("parameter_region") or {}
        if parameter_region:
            start = int(parameter_region["data_start_row"])
            columns = {int(value) for value in parameter_region["columns"].values()}
            last_existing = start - 1
            sheet = workbook[title]
            for row in range(start, min(sheet.max_row, start + 5000) + 1):
                if any(sheet.cell(row, column).value not in (None, "") for column in columns):
                    last_existing = row
            end = max(last_existing, start + max(0, max_parameter_count - 1))
            for row in range(start, end + 1):
                for column in columns:
                    cells.add((index, sheet.cell(row, column).coordinate))
            auto_filter.add(index)
        if event_mapping.get("data_layer_cell"):
            cells.add((index, str(event_mapping["data_layer_cell"])))
    return {
        "cells": cells,
        "sheet_title_state": sheet_title_state,
        "auto_filter": auto_filter,
        "obsolete_targets": obsolete_targets,
    }


def compare_template_fidelity(
    before: dict[str, Any],
    after: dict[str, Any],
    authorized: dict[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    before_sheets = {int(item["index"]): item for item in before["sheets"]}
    after_sheets = {int(item["index"]): item for item in after["sheets"]}
    added_indexes = sorted(set(after_sheets) - set(before_sheets))
    removed_indexes = sorted(set(before_sheets) - set(after_sheets))
    for index in added_indexes:
        violations.append({"kind": "sheet_added", "sheet_index": index})
    for index in removed_indexes:
        violations.append({"kind": "sheet_removed", "sheet_index": index})

    for index in sorted(set(before_sheets) & set(after_sheets)):
        old = before_sheets[index]
        new = after_sheets[index]
        if index not in authorized["sheet_title_state"]:
            for field in ("title", "state"):
                if old[field] != new[field]:
                    violations.append(
                        {"kind": f"sheet_{field}", "sheet": old["title"], "before": old[field], "after": new[field]}
                    )
        for field in (
            "merged_cells",
            "image_count",
            "table_names",
            "data_validation_count",
            "freeze_panes",
            "print_area",
            "print_title_rows",
            "print_title_cols",
        ):
            if old[field] != new[field]:
                violations.append(
                    {"kind": field, "sheet": old["title"], "before": old[field], "after": new[field]}
                )
        if index not in authorized["auto_filter"] and old["auto_filter"] != new["auto_filter"]:
            violations.append({"kind": "auto_filter", "sheet": old["title"]})
        old_cells = old["cells"]
        new_cells = new["cells"]
        for coordinate in sorted(set(old_cells) | set(new_cells)):
            if old_cells.get(coordinate) == new_cells.get(coordinate):
                continue
            if (index, coordinate) in authorized["cells"]:
                continue
            old_cell = old_cells.get(coordinate) or {}
            new_cell = new_cells.get(coordinate) or {}
            old_without_link = {key: value for key, value in old_cell.items() if key != "hyperlink"}
            new_without_link = {key: value for key, value in new_cell.items() if key != "hyperlink"}
            old_target = str(old_cell.get("hyperlink") or "")
            obsolete_link_change = (
                old_without_link == new_without_link
                and any(
                    old_target.startswith(f"#{target}!")
                    or old_target.startswith(f"#'{target}'!")
                    for target in authorized["obsolete_targets"]
                )
            )
            if not obsolete_link_change:
                violations.append(
                    {"kind": "unmapped_cell", "sheet": old["title"], "coordinate": coordinate}
                )
    return {
        "status": "passed" if not violations else "failed",
        "checked_unmapped_content": True,
        "checked_formulas_and_hyperlinks": True,
        "checked_images_tables_validations_and_print_settings": True,
        "violations": violations,
    }


def add_package_fidelity(
    report: dict[str, Any],
    template: Path,
    output: Path,
) -> dict[str, Any]:
    """Add macro-package preservation evidence after the adapted file is saved."""
    result = {**report, "violations": list(report.get("violations", []))}
    result["template_extension"] = template.suffix.lower()
    result["output_extension"] = output.suffix.lower()
    if template.suffix.lower() == ".xlsm":
        if output.suffix.lower() != ".xlsm":
            result["violations"].append(
                {"kind": "macro_extension", "message": "An XLSM template must remain XLSM."}
            )
        else:
            def macro_hash(path: Path) -> str:
                try:
                    with ZipFile(path) as archive:
                        content = archive.read("xl/vbaProject.bin")
                except (KeyError, OSError):
                    return ""
                return hashlib.sha256(content).hexdigest()

            before = macro_hash(template)
            after = macro_hash(output)
            result["vba_project_sha256_before"] = before
            result["vba_project_sha256_after"] = after
            if not before or before != after:
                result["violations"].append(
                    {"kind": "vba_project", "message": "VBA project was not preserved byte-for-byte."}
                )
    result["status"] = "passed" if not result["violations"] else "failed"
    return result
