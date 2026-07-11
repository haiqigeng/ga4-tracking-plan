from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from generate_tracking_plan_workbook import build_workbook
from openpyxl import load_workbook
from validate_tracking_plan import render_text, validate_plan_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a GA4 tracking plan into mapped client workbook sheets.")
    parser.add_argument("plan", type=Path, help="Validated tracking-plan JSON.")
    parser.add_argument("template", type=Path, help="Client XLSX template.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Adapted XLSX output.")
    parser.add_argument("--mapping", type=Path, help="Optional JSON object mapping canonical sheet names to client sheet names.")
    parser.add_argument("--screenshot-dir", type=Path, help="Optional screenshot folder.")
    return parser.parse_args()


def load_mapping(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ValueError("Template mapping must be a JSON object of canonical sheet name to client sheet name.")
    return value


def copy_sheet(source, target, preserve_existing_style: bool) -> None:
    existing_style_coordinates = {
        cell.coordinate
        for row in target.iter_rows()
        for cell in row
        if cell.has_style
    }
    existing_widths = {key: copy.copy(value) for key, value in target.column_dimensions.items()}
    existing_heights = {key: copy.copy(value) for key, value in target.row_dimensions.items()}
    existing_freeze = target.freeze_panes
    existing_tab_color = copy.copy(target.sheet_properties.tabColor)

    for merged in list(target.merged_cells.ranges):
        target.unmerge_cells(str(merged))
    for row in target.iter_rows():
        for cell in row:
            cell.value = None
            cell.hyperlink = None
            cell.comment = None

    for row in source.iter_rows():
        for source_cell in row:
            target_cell = target[source_cell.coordinate]
            target_cell.value = source_cell.value
            target_cell.hyperlink = copy.copy(source_cell.hyperlink)
            target_cell.comment = copy.copy(source_cell.comment)
            keep_style = preserve_existing_style and source_cell.coordinate in existing_style_coordinates
            if not keep_style:
                target_cell.font = copy.copy(source_cell.font)
                target_cell.fill = copy.copy(source_cell.fill)
                target_cell.border = copy.copy(source_cell.border)
                target_cell.number_format = source_cell.number_format
                target_cell.alignment = copy.copy(source_cell.alignment)
                target_cell.protection = copy.copy(source_cell.protection)
    for merged in source.merged_cells.ranges:
        target.merge_cells(str(merged))

    if preserve_existing_style:
        target.freeze_panes = existing_freeze or source.freeze_panes
        target.sheet_properties.tabColor = existing_tab_color or copy.copy(source.sheet_properties.tabColor)
        if not existing_widths:
            for key, value in source.column_dimensions.items():
                target.column_dimensions[key] = copy.copy(value)
        if not existing_heights:
            for key, value in source.row_dimensions.items():
                target.row_dimensions[key] = copy.copy(value)
    else:
        target.freeze_panes = source.freeze_panes
        target.sheet_properties.tabColor = copy.copy(source.sheet_properties.tabColor)
        for key, value in source.column_dimensions.items():
            target.column_dimensions[key] = copy.copy(value)
        for key, value in source.row_dimensions.items():
            target.row_dimensions[key] = copy.copy(value)
    target.auto_filter.ref = source.auto_filter.ref
    target.sheet_view.showGridLines = source.sheet_view.showGridLines
    for image in source._images:
        target.add_image(copy.copy(image), image.anchor)


def adapt_workbook(plan: dict, template: Path, mapping: dict[str, str], screenshot_dir: Path | None = None):
    client = load_workbook(template, read_only=False, data_only=False)
    with TemporaryDirectory(prefix="tracking_plan_template_previews_") as raw:
        generated = build_workbook(plan, screenshot_dir=screenshot_dir, preview_dir=Path(raw))
        for source in generated.worksheets:
            target_name = mapping.get(source.title, source.title)
            if target_name in client.sheetnames:
                target = client[target_name]
                copy_sheet(source, target, preserve_existing_style=True)
            else:
                target = client.create_sheet(target_name)
                copy_sheet(source, target, preserve_existing_style=False)
    return client


def main() -> int:
    args = parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    issues = validate_plan_data(plan)
    if issues:
        print(render_text(issues), file=sys.stderr)
    if any(issue.severity == "error" for issue in issues):
        return 1
    workbook = adapt_workbook(plan, args.template, load_mapping(args.mapping), args.screenshot_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
