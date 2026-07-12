from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook


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
        "image_count": len(sheet._images),
    }


def hazards_from_safety(safety: dict) -> list[str]:
    labels = {
        "formula_count": "formula cells",
        "sheet_protected": "sheet protection",
        "table_count": "Excel tables",
        "data_validation_count": "data validations",
        "comment_count": "cell comments",
        "image_count": "embedded images",
    }
    return [labels[key] for key in labels if safety[key]]


def destructive_overwrite_hazards(sheet) -> list[str]:
    return hazards_from_safety(inspect_sheet_safety(sheet))


def inspect_workbook(path: Path) -> dict:
    workbook = load_workbook(path, read_only=False, data_only=False)
    sheets = []
    for sheet in workbook.worksheets:
        header_candidates = []
        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 15), values_only=True):
            values = [str(value).strip() for value in row if value not in (None, "")]
            if len(values) >= 2:
                header_candidates.append(values[:20])
        safety = inspect_sheet_safety(sheet)
        sheets.append(
            {
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
                "header_candidates": header_candidates,
                **safety,
                "destructive_overwrite_hazards": hazards_from_safety(safety),
            }
        )
    return {
        "template_file": path.name,
        "sheet_count": len(sheets),
        "workbook_properties": {
            "title": workbook.properties.title or "",
            "subject": workbook.properties.subject or "",
            "creator": workbook.properties.creator or "",
        },
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
