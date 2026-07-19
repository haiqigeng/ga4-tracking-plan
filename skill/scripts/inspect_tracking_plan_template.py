from __future__ import annotations

import argparse
import hashlib
import json
import re
from operator import attrgetter
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from openpyxl import load_workbook

UNSUPPORTED_STRICT_PART_PREFIXES = (
    "customUI/",
    "xl/activeX/",
    "xl/charts/",
    "xl/ctrlProps/",
    "xl/customData/",
    "xl/diagrams/",
    "xl/embeddings/",
    "xl/externalLinks/",
    "xl/pivotCache/",
    "xl/pivotTables/",
    "xl/persons/",
    "xl/printerSettings/",
    "xl/queryTables/",
    "xl/revisions/",
    "xl/richData/",
    "xl/slicerCaches/",
    "xl/slicers/",
    "xl/threadedComments/",
    "xl/timelines/",
    "xl/webextensions/",
    "xl/xmlMaps/",
    "customXml/",
)
UNSUPPORTED_STRICT_PART_NAMES = {
    "xl/connections.xml",
    "xl/vbaProject.bin",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a client tracking-plan workbook before adaptation.")
    parser.add_argument("template", type=Path, help="Client XLSX template.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="JSON inventory output.")
    return parser.parse_args()


def inspect_sheet_safety(sheet) -> dict:
    formula_count = 0
    formula_cells: list[str] = []
    comment_count = 0
    comment_cells: list[str] = []
    hyperlink_count = 0
    styled_cell_count = 0
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                formula_count += 1
                if len(formula_cells) < 20:
                    formula_cells.append(cell.coordinate)
            if cell.comment:
                comment_count += 1
                if len(comment_cells) < 20:
                    comment_cells.append(cell.coordinate)
            if cell.hyperlink:
                hyperlink_count += 1
            if cell.has_style:
                styled_cell_count += 1
    table_names = sorted(str(name) for name in sheet.tables.keys())
    data_validation_count = len(sheet.data_validations.dataValidation)
    return {
        "formula_count": formula_count,
        "formula_cells": formula_cells,
        "sheet_protected": bool(sheet.protection.sheet),
        "table_count": len(table_names),
        "table_names": table_names,
        "data_validation_count": data_validation_count,
        "comment_count": comment_count,
        "comment_cells": comment_cells,
        "hyperlink_count": hyperlink_count,
        "styled_cell_count": styled_cell_count,
        "image_count": len(sheet._images),
        "conditional_format_count": len(sheet.conditional_formatting),
    }


def hazards_from_safety(safety: dict) -> list[str]:
    labels = {
        "formula_count": "formula cells",
        "sheet_protected": "sheet protection",
        "table_count": "Excel tables",
        "data_validation_count": "data validations",
        "comment_count": "cell comments",
        "image_count": "embedded images",
        "conditional_format_count": "conditional formatting",
    }
    return [labels[key] for key in labels if safety[key]]


def unsupported_strict_package_parts(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
            unsupported = [
                name
                for name in names
                if name in UNSUPPORTED_STRICT_PART_NAMES
                or name.startswith(UNSUPPORTED_STRICT_PART_PREFIXES)
            ]
            for name in names:
                if re.fullmatch(r"xl/drawings/[^/]+\.xml", name):
                    drawing = archive.read(name)
                    if re.search(rb"<(?:[A-Za-z0-9_]+:)?(?:sp|graphicFrame|cxnSp|grpSp|contentPart)(?:\s|/|>)", drawing):
                        unsupported.append(f"{name}#unsupported-drawing-object")
                elif re.fullmatch(r"xl/drawings/[^/]+\.vml", name):
                    drawing = archive.read(name)
                    object_types = re.findall(rb'ObjectType="([^"]+)"', drawing)
                    if b":shape" in drawing and set(object_types) != {b"Note"}:
                        unsupported.append(f"{name}#unsupported-vml-object")
                elif name == "xl/sharedStrings.xml":
                    shared_strings = archive.read(name)
                    if re.search(rb"<(?:[A-Za-z0-9_]+:)?si(?:\s|>).*?<(?:[A-Za-z0-9_]+:)?r(?:\s|>)", shared_strings, re.S):
                        unsupported.append(f"{name}#rich-text-runs")
                elif re.fullmatch(r"xl/worksheets/[^/]+\.xml", name):
                    worksheet = archive.read(name)
                    if re.search(rb"<(?:[A-Za-z0-9_]+:)?is(?:\s|>).*?<(?:[A-Za-z0-9_]+:)?r(?:\s|>)", worksheet, re.S):
                        unsupported.append(f"{name}#inline-rich-text-runs")
                    if re.search(rb"<(?:[A-Za-z0-9_]+:)?extLst(?:\s|>)", worksheet):
                        unsupported.append(f"{name}#unsupported-extension-list")
    except Exception as exc:
        return [f"unreadable-workbook-package:{type(exc).__name__}"]
    return sorted(set(unsupported))


def load_client_workbook(path: Path):
    return load_workbook(
        path,
        read_only=False,
        data_only=False,
        keep_links=True,
        keep_vba=path.suffix.lower() == ".xlsm",
    )


def _color_signature(color: Any) -> tuple[Any, ...]:
    return tuple(getattr(color, key, None) for key in ("type", "rgb", "indexed", "auto", "theme", "tint"))


def _cell_signature(cell, *, ignore_value: bool) -> tuple[Any, ...]:
    value = "<mapped-value>" if ignore_value else cell.value
    data_type = "<mapped-data-type>" if ignore_value else cell.data_type
    comment = None if cell.comment is None else (cell.comment.text, cell.comment.author)
    hyperlink = None if cell.hyperlink is None else (cell.hyperlink.target, cell.hyperlink.location, cell.hyperlink.tooltip)
    return (
        value,
        data_type,
        tuple(cell._style) if cell.has_style else (),
        repr(cell.font),
        repr(cell.fill),
        repr(cell.border),
        repr(cell.alignment),
        repr(cell.protection),
        cell.number_format,
        comment,
        hyperlink,
    )


def _dimension_signature(dimensions: dict[str, Any]) -> dict[str, tuple[Any, ...]]:
    return {
        key: tuple((name, getattr(value, name, None)) for name in value.__attrs__)
        + (("style_id", getattr(value, "style_id", None)),)
        for key, value in dimensions.items()
    }


def _validation_signature(sheet) -> list[tuple[Any, ...]]:
    return sorted(
        tuple((name, getattr(item, name, None)) for name in item.__attrs__)
        + (("formula1", item.formula1), ("formula2", item.formula2))
        for item in sheet.data_validations.dataValidation
    )


def _conditional_format_signature(sheet) -> list[tuple[str, tuple[Any, ...]]]:
    values: list[tuple[str, tuple[Any, ...]]] = []
    for conditional_format, rules in sheet.conditional_formatting._cf_rules.items():
        for rule in rules:
            values.append(
                (
                    str(conditional_format.sqref),
                    tuple((name, getattr(rule, name, None)) for name in rule.__attrs__)
                    + tuple((name, repr(getattr(rule, name, None))) for name in rule.__elements__),
                )
            )
    return sorted(values, key=repr)


def _marker_signature(marker: Any) -> tuple[Any, ...] | None:
    if marker is None:
        return None
    return tuple(getattr(marker, name, None) for name in ("col", "colOff", "row", "rowOff"))


def _image_anchor_signature(image) -> tuple[Any, ...]:
    anchor = image.anchor
    if isinstance(anchor, str):
        return ("cell", anchor)
    extent = getattr(anchor, "ext", None)
    position = getattr(anchor, "pos", None)
    return (
        type(anchor).__name__,
        _marker_signature(getattr(anchor, "_from", None)),
        _marker_signature(getattr(anchor, "to", None)),
        None if extent is None else (getattr(extent, "cx", None), getattr(extent, "cy", None)),
        None if position is None else (getattr(position, "x", None), getattr(position, "y", None)),
        getattr(anchor, "editAs", None),
    )


def _image_signature(image) -> tuple[Any, ...]:
    return (
        _image_anchor_signature(image),
        image.width,
        image.height,
        getattr(image, "format", None),
        hashlib.sha256(image._data()).hexdigest(),
    )


def _object_signature(value: Any, names: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(getattr(value, name, None) for name in names)


def _table_signature(table: Any) -> tuple[Any, ...]:
    style = table.tableStyleInfo
    columns = tuple(
        (
            column.id,
            column.name,
            column.totalsRowLabel,
            column.totalsRowFunction,
            getattr(column.calculatedColumnFormula, "text", None),
            getattr(column.totalsRowFormula, "text", None),
        )
        for column in table.tableColumns
    )
    return (
        table.name,
        table.displayName,
        table.ref,
        table.headerRowCount,
        table.totalsRowCount,
        table.totalsRowShown,
        table.insertRow,
        table.insertRowShift,
        table.published,
        str(getattr(table.autoFilter, "ref", "") or ""),
        columns,
        None if style is None else _object_signature(
            style,
            ("name", "showFirstColumn", "showLastColumn", "showRowStripes", "showColumnStripes"),
        ),
    )


def _header_footer_signature(sheet: Any) -> tuple[Any, ...]:
    return tuple(
        getattr(getattr(sheet, section), position).text
        for section in ("oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter")
        for position in ("left", "center", "right")
    )


def _sheet_view_signature(sheet: Any) -> tuple[Any, ...]:
    view = sheet.sheet_view
    pane = view.pane
    selections = tuple(
        _object_signature(selection, ("pane", "activeCell", "activeCellId", "sqref"))
        for selection in view.selection
    )
    return (
        _object_signature(
            view,
            (
                "showFormulas",
                "showGridLines",
                "showRowColHeaders",
                "showZeros",
                "rightToLeft",
                "tabSelected",
                "view",
                "topLeftCell",
                "zoomScale",
                "zoomScaleNormal",
                "zoomScaleSheetLayoutView",
                "zoomScalePageLayoutView",
                "workbookViewId",
            ),
        ),
        None if pane is None else _object_signature(
            pane,
            ("xSplit", "ySplit", "topLeftCell", "activePane", "state"),
        ),
        selections,
    )


def _sheet_properties_signature(sheet: Any) -> tuple[Any, ...]:
    properties = sheet.sheet_properties
    return (
        _object_signature(
            properties,
            ("codeName", "enableFormatConditionsCalculation", "filterMode", "published", "syncHorizontal", "syncRef", "syncVertical", "transitionEntry", "transitionEvaluation"),
        ),
        _color_signature(properties.tabColor),
        _object_signature(properties.pageSetUpPr, ("autoPageBreaks", "fitToPage")),
        _object_signature(properties.outlinePr, ("applyStyles", "summaryBelow", "summaryRight", "showOutlineSymbols")),
    )


def _workbook_properties_signature(workbook: Any) -> tuple[Any, ...]:
    properties = workbook.properties
    return _object_signature(
        properties,
        (
            "title",
            "subject",
            "creator",
            "keywords",
            "description",
            "lastModifiedBy",
            "category",
            "contentStatus",
            "identifier",
            "language",
            "version",
            "revision",
            "created",
        ),
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_part_names(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        return sorted(archive.namelist())


def workbook_fidelity_signature(workbook, allowed_value_cells: dict[str, set[str]] | None = None) -> dict[str, Any]:
    allowed_value_cells = allowed_value_cells or {}
    sheets: dict[str, Any] = {}
    for sheet in workbook.worksheets:
        allowed = allowed_value_cells.get(sheet.title, set())
        coordinates = set(map(attrgetter("coordinate"), sheet._cells.values())) | allowed
        cells = {
            coordinate: _cell_signature(sheet[coordinate], ignore_value=coordinate in allowed)
            for coordinate in sorted(coordinates)
        }
        tables = sorted(map(_table_signature, sheet.tables.values()), key=repr)
        sheets[sheet.title] = {
            "state": sheet.sheet_state,
            "cells": cells,
            "merged_ranges": sorted(map(str, sheet.merged_cells.ranges)),
            "column_dimensions": _dimension_signature(sheet.column_dimensions),
            "row_dimensions": _dimension_signature(sheet.row_dimensions),
            "freeze_panes": str(sheet.freeze_panes or ""),
            "sheet_properties": _sheet_properties_signature(sheet),
            "auto_filter": str(sheet.auto_filter.ref or ""),
            "tables": tables,
            "data_validations": _validation_signature(sheet),
            "conditional_formatting": _conditional_format_signature(sheet),
            "images": sorted(map(_image_signature, sheet._images), key=repr),
            "protection": _object_signature(
                sheet.protection,
                tuple(sheet.protection.__attrs__),
            ),
            "print_area": str(sheet.print_area or ""),
            "print_title_rows": str(sheet.print_title_rows or ""),
            "print_title_cols": str(sheet.print_title_cols or ""),
            "page_setup": _object_signature(sheet.page_setup, tuple(sheet.page_setup.__attrs__)),
            "page_margins": _object_signature(sheet.page_margins, tuple(sheet.page_margins.__attrs__)),
            "print_options": _object_signature(sheet.print_options, tuple(sheet.print_options.__attrs__)),
            "sheet_format": _object_signature(sheet.sheet_format, tuple(sheet.sheet_format.__attrs__)),
            "header_footer": _header_footer_signature(sheet),
            "sheet_view": _sheet_view_signature(sheet),
        }
    defined_names = sorted(
        (item.name, item.attr_text, item.localSheetId, item.hidden)
        for item in workbook.defined_names.values()
    )
    return {
        "sheet_order": list(workbook.sheetnames),
        "defined_names": defined_names,
        "active_sheet_index": workbook.index(workbook.active),
        "workbook_properties": _workbook_properties_signature(workbook),
        "calculation": _object_signature(workbook.calculation, tuple(workbook.calculation.__attrs__)),
        "workbook_views": tuple(
            _object_signature(view, tuple(view.__attrs__))
            for view in workbook.views
        ),
        "style_catalogs": {
            "fonts": tuple(map(repr, workbook._fonts)),
            "fills": tuple(map(repr, workbook._fills)),
            "borders": tuple(map(repr, workbook._borders)),
            "alignments": tuple(map(repr, workbook._alignments)),
            "protections": tuple(map(repr, workbook._protections)),
            "cell_styles": tuple(map(repr, workbook._cell_styles)),
            "named_styles": tuple(map(repr, workbook._named_styles)),
            "number_formats": tuple(workbook._number_formats),
            "differential_styles": tuple(map(repr, workbook._differential_styles.styles)),
        },
        "sheets": sheets,
    }


def _fidelity_differences(before: Any, after: Any, path: str = "$") -> list[str]:
    if type(before) is not type(after):
        return [f"{path}: type changed"]
    if isinstance(before, dict):
        differences: list[str] = []
        for key in sorted(set(before) | set(after)):
            if key not in before:
                differences.append(f"{path}.{key}: added")
            elif key not in after:
                differences.append(f"{path}.{key}: removed")
            else:
                differences.extend(_fidelity_differences(before[key], after[key], f"{path}.{key}"))
            if len(differences) >= 50:
                break
        return differences
    if before != after:
        return [f"{path}: changed"]
    return []


def compare_workbook_fidelity(
    template: Path,
    output: Path,
    allowed_value_cells: dict[str, set[str]],
) -> dict[str, Any]:
    before = workbook_fidelity_signature(load_client_workbook(template), allowed_value_cells)
    after = workbook_fidelity_signature(load_client_workbook(output), allowed_value_cells)
    differences = _fidelity_differences(before, after)
    package_parts_before = package_part_names(template)
    package_parts_after = package_part_names(output)
    if package_parts_before != package_parts_after:
        differences.append("$.package_parts: changed")
    return {
        "status": "passed" if not differences else "failed",
        "template_sha256": file_sha256(template),
        "output_sha256": file_sha256(output),
        "allowed_value_cells": {sheet: sorted(cells) for sheet, cells in allowed_value_cells.items()},
        "package_parts_added": sorted(set(package_parts_after) - set(package_parts_before)),
        "package_parts_removed": sorted(set(package_parts_before) - set(package_parts_after)),
        "unexpected_differences": differences,
    }


def compare_workbook_extension_fidelity(
    template: Path,
    output: Path,
    allowed_value_cells: dict[str, set[str]],
    sheet_clones: list[dict[str, Any]],
) -> dict[str, Any]:
    clone_targets = {str(item["target_sheet"]): str(item["source_sheet"]) for item in sheet_clones}
    original_allowed = {
        sheet: cells
        for sheet, cells in allowed_value_cells.items()
        if sheet not in clone_targets
    }
    before = workbook_fidelity_signature(load_client_workbook(template), original_allowed)
    after = workbook_fidelity_signature(load_client_workbook(output), allowed_value_cells)
    differences: list[str] = []

    expected_order = [*before["sheet_order"], *clone_targets]
    if after["sheet_order"] != expected_order:
        differences.append("$.sheet_order: approved clone sheets were not appended in manifest order")
    for key in ("defined_names", "active_sheet_index", "workbook_properties", "calculation", "workbook_views"):
        differences.extend(_fidelity_differences(before[key], after[key], f"$.{key}"))
    for sheet_name in before["sheet_order"]:
        differences.extend(
            _fidelity_differences(
                before["sheets"][sheet_name],
                after["sheets"].get(sheet_name),
                f"$.sheets.{sheet_name}",
            )
        )

    template_workbook = load_client_workbook(template)
    output_workbook = load_client_workbook(output)
    for target_sheet, source_sheet in clone_targets.items():
        clone_cells = allowed_value_cells.get(target_sheet, set())
        source_signature = workbook_fidelity_signature(
            template_workbook,
            {source_sheet: clone_cells},
        )["sheets"].get(source_sheet)
        target_signature = workbook_fidelity_signature(
            output_workbook,
            {target_sheet: clone_cells},
        )["sheets"].get(target_sheet)
        differences.extend(
            _fidelity_differences(
                source_signature,
                target_signature,
                f"$.approved_clones.{target_sheet}",
            )
        )

    package_parts_before = package_part_names(template)
    package_parts_after = package_part_names(output)
    return {
        "status": "passed" if not differences else "failed",
        "template_sha256": file_sha256(template),
        "output_sha256": file_sha256(output),
        "allowed_value_cells": {sheet: sorted(cells) for sheet, cells in allowed_value_cells.items()},
        "approved_sheet_clones": sheet_clones,
        "package_parts_added": sorted(set(package_parts_after) - set(package_parts_before)),
        "package_parts_removed": sorted(set(package_parts_before) - set(package_parts_after)),
        "unexpected_differences": differences[:50],
    }


def _header_candidates(sheet) -> list[list[str]]:
    candidates: list[list[str]] = []
    for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 15), values_only=True):
        values = [str(value).strip() for value in row if value not in (None, "")]
        if len(values) >= 2:
            candidates.append(values[:20])
    return candidates


def _sheet_inventory(sheet) -> dict[str, Any]:
    safety = inspect_sheet_safety(sheet)
    return {
        "sheet_name": sheet.title,
        "state": sheet.sheet_state,
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "freeze_panes": str(sheet.freeze_panes or ""),
        "merged_ranges": [str(item) for item in sheet.merged_cells.ranges],
        "column_widths": {
            key: value.width
            for key, value in sheet.column_dimensions.items()
            if value.width is not None
        },
        "row_heights": {
            str(key): value.height
            for key, value in sheet.row_dimensions.items()
            if value.height is not None
        },
        "auto_filter": str(sheet.auto_filter.ref or ""),
        "print_area": str(sheet.print_area or ""),
        "print_title_rows": str(sheet.print_title_rows or ""),
        "print_title_cols": str(sheet.print_title_cols or ""),
        "header_candidates": _header_candidates(sheet),
        **safety,
        "destructive_overwrite_hazards": hazards_from_safety(safety),
    }


def _workbook_properties(workbook) -> dict[str, str]:
    return {
        "title": workbook.properties.title or "",
        "subject": workbook.properties.subject or "",
        "creator": workbook.properties.creator or "",
        "description": workbook.properties.description or "",
        "keywords": workbook.properties.keywords or "",
        "category": workbook.properties.category or "",
    }


def inspect_workbook(path: Path) -> dict:
    workbook = load_client_workbook(path)
    sheets = [_sheet_inventory(sheet) for sheet in workbook.worksheets]
    return {
        "template_file": path.name,
        "template_sha256": file_sha256(path),
        "sheet_count": len(sheets),
        "sheet_order": list(workbook.sheetnames),
        "strict_unsupported_parts": unsupported_strict_package_parts(path),
        "workbook_properties": _workbook_properties(workbook),
        "sheets": sheets,
    }


def main() -> int:
    args = parse_args()
    inventory = inspect_workbook(args.template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
