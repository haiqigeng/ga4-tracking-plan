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


def inspect_workbook(path: Path) -> dict:
    workbook = load_workbook(path, read_only=False, data_only=False)
    sheets = []
    for sheet in workbook.worksheets:
        header_candidates = []
        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 15), values_only=True):
            values = [str(value).strip() for value in row if value not in (None, "")]
            if len(values) >= 2:
                header_candidates.append(values[:20])
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
                "formula_count": sum(
                    1
                    for row in sheet.iter_rows()
                    for cell in row
                    if isinstance(cell.value, str) and cell.value.startswith("=")
                ),
                "comment_count": sum(1 for row in sheet.iter_rows() for cell in row if cell.comment),
                "image_count": len(sheet._images),
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
