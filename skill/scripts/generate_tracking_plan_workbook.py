from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.datavalidation import DataValidation

from ecommerce_matrix import (
    event_family as ecommerce_event_family,
    ordered_parameters_for_events,
    parameter_matrix_value,
    parameter_type,
)
from validate_tracking_plan import render_text, validate_plan_data

NAVY = "263238"
BLUE = "E7EEF5"
LIGHT_BLUE = "F6F9FC"
GREEN = "EAF3EA"
YELLOW = "FFF6D8"
GRAY = "F4F6F8"
WHITE = "FFFFFF"
RED = "FBEAEA"
DARK = "404040"
MUTED_TEXT = "6E7781"
HEADER_TEXT = "1F2933"
BLOCK_FILL = "EDF6EF"
INHERITED_FILL = "EAF4FB"
DEFAULT_FILL = "F0F7F2"
NOT_AVAILABLE_FILL = "FFF2CC"
NOT_APPLICABLE_FILL = "F5F6F7"
GRID = "E7ECF2"
GRID_DARK = "BBC8D6"
TEAL = "2F6F7E"
TEAL_LIGHT = "EAF6F4"
TEAL_SECTION = "DCEFEA"
OVERVIEW_HEADER = "F3F7F8"
OVERVIEW_ALT = "FAFCFD"

THIN = Side(style="thin", color=GRID)
MEDIUM = Side(style="medium", color=GRID_DARK)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BLOCK_BORDER = Border(top=MEDIUM, bottom=THIN, left=THIN, right=THIN)
OVERVIEW_LINE = Side(style="thin", color="DDE5EA")
OVERVIEW_BORDER = Border(bottom=OVERVIEW_LINE)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")

EVENT_SLOT_COUNT = 4
STATUS_OPTIONS = "OK,KO,Cannot test"


def matrix_max_col() -> int:
    return 2 + (EVENT_SLOT_COUNT * 2)


def matrix_value_columns() -> list[int]:
    return [3 + index * 2 for index in range(EVENT_SLOT_COUNT)]


def matrix_status_columns() -> list[int]:
    return [4 + index * 2 for index in range(EVENT_SLOT_COUNT)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a human analytics tracking-plan workbook from the canonical JSON contract.")
    parser.add_argument("plan", type=Path, help="Path to a JSON tracking plan using tracking_plan_schema.json.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output XLSX path.")
    return parser.parse_args()


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def set_widths(ws, widths: list[int]) -> None:
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width


def style_cells(ws) -> None:
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = WRAP
            cell.border = BORDER
    ws.sheet_view.showGridLines = False


def style_overview(ws, max_col: int) -> None:
    style_cells(ws)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = None
    ws.sheet_properties.tabColor = "95C8C1"
    ws.sheet_view.zoomScale = 90
    ws.sheet_view.zoomScaleNormal = 90

    section_labels = {
        "Document Summary",
        "Sheet Contents",
        "Version History",
    }
    header_labels = {"#"}
    label_columns = {1, 3, 5, 7}

    for row in range(1, ws.max_row + 1):
        label = ws.cell(row, 1).value
        if row not in {1, 2}:
            ws.row_dimensions[row].height = 24
        for col in range(1, max_col + 1):
            cell = ws.cell(row, col)
            cell.alignment = WRAP
            cell.border = OVERVIEW_BORDER
            if cell.hyperlink:
                cell.font = Font(color=TEAL, bold=True, underline="single", size=10)
            elif row not in {1, 2}:
                cell.font = Font(color=DARK, size=10)

        if label in section_labels:
            ws.row_dimensions[row].height = 26
            for col in range(1, max_col + 1):
                cell = ws.cell(row, col)
                cell.fill = PatternFill("solid", fgColor=TEAL_SECTION)
                cell.font = Font(color=TEAL, bold=True, size=12)
                cell.alignment = Alignment(vertical="center")
                cell.border = Border(top=Side(style="medium", color=TEAL), bottom=OVERVIEW_LINE)
        elif label in header_labels or (label == "Version" and ws.cell(row, 2).value == "Date"):
            ws.row_dimensions[row].height = 22
            for col in range(1, max_col + 1):
                cell = ws.cell(row, col)
                cell.fill = PatternFill("solid", fgColor=OVERVIEW_HEADER)
                cell.font = Font(color=HEADER_TEXT, bold=True, size=10)
                cell.alignment = Alignment(wrap_text=True, vertical="center")
                cell.border = Border(top=OVERVIEW_LINE, bottom=OVERVIEW_LINE)
        elif row > 2 and any(ws.cell(row, col).value not in (None, "") for col in range(1, max_col + 1)):
            fill = OVERVIEW_ALT if row % 2 == 0 else WHITE
            for col in range(1, max_col + 1):
                cell = ws.cell(row, col)
                cell.fill = PatternFill("solid", fgColor=fill)
                if col in label_columns and cell.value not in (None, ""):
                    cell.font = Font(color=MUTED_TEXT, bold=True, size=10)

    for row in [4, 5]:
        if row <= ws.max_row:
            ws.row_dimensions[row].height = 30
            for col in range(1, max_col + 1):
                ws.cell(row, col).fill = PatternFill("solid", fgColor=LIGHT_BLUE if col in label_columns else WHITE)
                ws.cell(row, col).border = BORDER
                if col not in label_columns and ws.cell(row, col).value not in (None, ""):
                    ws.cell(row, col).font = Font(color=HEADER_TEXT, bold=True, size=10)

    ws.cell(1, 1).fill = PatternFill("solid", fgColor=TEAL)
    ws.cell(1, 1).font = Font(color=WHITE, bold=True, size=20)
    ws.cell(1, 1).alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 38
    ws.cell(2, 1).fill = PatternFill("solid", fgColor=TEAL_LIGHT)
    ws.cell(2, 1).font = Font(color=TEAL, size=11)
    ws.cell(2, 1).alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 30


def title(ws, text: str, subtitle: str, max_col: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_col)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_col)
    ws.cell(1, 1, text)
    ws.cell(2, 1, subtitle)
    ws.cell(1, 1).fill = PatternFill("solid", fgColor=NAVY)
    ws.cell(1, 1).font = Font(color=WHITE, bold=True, size=15)
    ws.cell(2, 1).fill = PatternFill("solid", fgColor=LIGHT_BLUE)
    ws.cell(2, 1).font = Font(color=DARK)
    ws.cell(1, 1).alignment = Alignment(vertical="center")
    ws.cell(2, 1).alignment = WRAP
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 34


def section(ws, row: int, label: str, max_col: int) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max_col)
    cell = ws.cell(row, 1, label)
    cell.fill = PatternFill("solid", fgColor=BLOCK_FILL)
    cell.font = Font(color=HEADER_TEXT, bold=True)
    cell.alignment = Alignment(vertical="center")
    for col in range(1, max_col + 1):
        ws.cell(row, col).border = BLOCK_BORDER


def header(ws, row: int, max_col: int, fill: str = NAVY) -> None:
    for col in range(1, max_col + 1):
        cell = ws.cell(row, col)
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.font = Font(color=WHITE if fill == NAVY else "000000", bold=True)
        cell.alignment = CENTER
        cell.border = BORDER


def set_internal_link(cell, sheet_name: str) -> None:
    cell.hyperlink = f"#{quote_sheetname(sheet_name)}!A1"
    cell.font = Font(color="2F6F7E", bold=True, underline="single")


def join_values(values: list[Any] | None) -> str:
    if not values:
        return ""
    return " | ".join(str(value) for value in values)


def compact_json(value: Any) -> str:
    if value in (None, "", []):
        return "-"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def event_family(event: dict[str, Any]) -> str:
    return ecommerce_event_family(event)


def transport_event_name(event: dict[str, Any]) -> str:
    data_layer = event.get("data_layer", {})
    if isinstance(data_layer, dict) and data_layer.get("event_key"):
        return str(data_layer["event_key"])
    ga4_payload = event.get("ga4_payload", {})
    if isinstance(ga4_payload, dict) and ga4_payload.get("event_name"):
        return str(ga4_payload["event_name"])
    payloads = event.get("implementation_payloads", [])
    if isinstance(payloads, list):
        for payload in payloads:
            if isinstance(payload, dict) and payload.get("event_name"):
                return str(payload["event_name"])
    mappings = event.get("platform_mappings", [])
    if isinstance(mappings, list):
        for mapping in mappings:
            if isinstance(mapping, dict) and mapping.get("event_name"):
                return str(mapping["event_name"])
    return str(event.get("event_name", ""))


def style_matrix_value_cell(cell, availability: str) -> None:
    if cell.value in (None, ""):
        return
    if availability == "not_applicable":
        cell.fill = PatternFill("solid", fgColor=NOT_APPLICABLE_FILL)
        cell.font = Font(color=MUTED_TEXT, italic=True)
    elif availability == "not_available":
        cell.fill = PatternFill("solid", fgColor=NOT_AVAILABLE_FILL)
        cell.font = Font(color=DARK)
    elif availability == "event_level_used":
        cell.fill = PatternFill("solid", fgColor=INHERITED_FILL)
        cell.font = Font(color=DARK, italic=True)
    elif availability == "send_default_quantity":
        cell.fill = PatternFill("solid", fgColor=DEFAULT_FILL)
        cell.font = Font(color=DARK)


def style_event_matrix_rows(ws) -> None:
    value_columns = matrix_value_columns()
    max_col = matrix_max_col()
    for row in range(6, ws.max_row + 1):
        is_block = str(ws.cell(row, 1).value or "").startswith("J-")
        if is_block:
            for col in range(1, max_col + 1):
                cell = ws.cell(row, col)
                cell.fill = PatternFill("solid", fgColor=BLOCK_FILL)
                cell.border = BLOCK_BORDER
                cell.font = Font(color=HEADER_TEXT, bold=True)
                cell.alignment = Alignment(wrap_text=True, vertical="center")
            ws.row_dimensions[row].height = 24
            continue

        parameter = str(ws.cell(row, 1).value or "")
        for col in range(1, max_col + 1):
            ws.cell(row, col).fill = PatternFill("solid", fgColor=WHITE)
        for col in value_columns:
            test_status = str(ws.cell(row, col).offset(column=1).value or "")
            if test_status not in {"OK", "KO", "Cannot test"}:
                continue
            value = str(ws.cell(row, col).value or "")
            if value == "not_applicable":
                style_matrix_value_cell(ws.cell(row, col), "not_applicable")
            elif value == "not_available":
                style_matrix_value_cell(ws.cell(row, col), "not_available")
            elif value.startswith("event-level "):
                style_matrix_value_cell(ws.cell(row, col), "event_level_used")
            elif parameter == "items[].quantity" and value == "1":
                style_matrix_value_cell(ws.cell(row, col), "send_default_quantity")


def parameter_value(event: dict[str, Any], parameter: str) -> str:
    if event.get("classification") == "recommended_ecommerce":
        if parameter == "items":
            return "Array<Item>; see items[] rows below"
        return parameter_matrix_value(event, parameter)

    payload = event.get("ga4_payload", {})
    params = payload.get("parameters", {})
    items = payload.get("items", [])
    data_layer = event.get("data_layer", {})

    if parameter == "event":
        return str(data_layer.get("event_key") or event.get("event_name") or "")
    if parameter in params:
        return compact_json(params[parameter])
    if parameter == "items":
        return compact_json(items or "Required when ecommerce context is sent")
    if parameter.startswith("items[].") and items:
        key = parameter.split(".", 1)[1]
        values = [item.get(key) for item in items if isinstance(item, dict) and item.get(key) not in (None, "")]
        return join_values(values) or "Required when items is sent"

    push = data_layer.get("push", {})
    lookup_path = parameter.split(".")
    current: Any = push
    for part in lookup_path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            current = None
            break
    if current is not None:
        return compact_json(current)

    for mapping in event.get("platform_mappings", []):
        if not isinstance(mapping, dict):
            continue
        props = mapping.get("parameters_or_properties", {})
        if isinstance(props, dict) and parameter in props:
            return compact_json(props[parameter])
        products = mapping.get("items_or_products", [])
        if parameter.startswith("items_or_products[].") and isinstance(products, list):
            key = parameter.split(".", 1)[1]
            values = [item.get(key) for item in products if isinstance(item, dict) and item.get(key) not in (None, "")]
            if values:
                return join_values(values)

    for payload in event.get("implementation_payloads", []):
        if not isinstance(payload, dict):
            continue
        payload_data = payload.get("payload", {})
        if isinstance(payload_data, dict) and parameter in payload_data:
            return compact_json(payload_data[parameter])
    return "-"


def apply_workbook_settings(wb: Workbook) -> None:
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and len(cell.value) > 80:
                    ws.row_dimensions[cell.row].height = max(ws.row_dimensions[cell.row].height or 15, 42)
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
    wb.active = 0


def build_overview(wb: Workbook, plan: dict[str, Any]) -> None:
    doc = plan["document"]
    ws = wb.create_sheet("00 Overview")
    max_col = 8
    title(ws, doc["title"], "Document details and workbook navigation.", max_col)

    def display_value(value: Any) -> str:
        labels = {
            "ga4": "GA4",
            "piano_analytics": "Piano Analytics",
            "other": "Other",
            "draft": "Draft",
            "ready_for_review": "Ready for review",
            "approved": "Approved",
            "deprecated": "Deprecated",
            "must": "Must",
            "should": "Should",
            "could": "Could",
        }
        return labels.get(str(value), str(value))

    def display_values(values: list[Any] | None) -> str:
        if not values:
            return ""
        return join_values([display_value(value) for value in values])

    rows = [
        ["Document Summary", "", "", "", "", "", "", "", ""],
        ["Document", doc["title"], "Owner / contact", doc["owner"], "Last update", doc["created_date"], "", ""],
        ["Version", doc["version"], "Platform", display_values(plan.get("analytics_platforms", ["ga4"])), "", "", "", ""],
        [],
        ["Sheet Contents", "", "", "", "", "", "", "", ""],
        ["#", "Sheet", "What it is for", "", "", "", "", ""],
        ["1", "00 Overview", "Document information and version history.", "", "", "", "", ""],
        ["2", "01 GTM Protocol", "Shared GTM/dataLayer rules and official references.", "", "", "", "", ""],
        ["3", "02 Parameter Reference", "Variable dictionary and value rules.", "", "", "", "", ""],
        ["4", "03 Event Matrix", "Main tracking plan: events, parameters, values, and test status.", "", "", "", "", ""],
        ["5", "04 Screenshot Register", "Screenshot links for page and interaction evidence.", "", "", "", "", ""],
        ["6", "05 QA Cases", "Manual recette checks and validation status.", "", "", "", "", ""],
        [],
        ["Version History", "", "", "", "", "", "", "", ""],
        ["Version", "Date", "Owner", "Summary", "Publish date", "", "", "", ""],
        [doc["version"], doc["created_date"], doc["owner"], "Tracking plan draft generated for review.", "TBD", "", "", "", ""],
    ]
    for row in rows:
        ws.append((row + [""] * max_col)[:max_col])

    workbook_tabs = {
        "00 Overview",
        "01 GTM Protocol",
        "02 Parameter Reference",
        "03 Event Matrix",
        "04 Screenshot Register",
        "05 QA Cases",
    }
    for row in range(1, ws.max_row + 1):
        label = ws.cell(row, 1).value
        if label in {"Document Summary", "Sheet Contents", "Version History"}:
            section(ws, row, str(label), max_col)
        if label == "#" or (label == "Version" and ws.cell(row, 2).value == "Date"):
            header(ws, row, max_col)
        if label in workbook_tabs:
            set_internal_link(ws.cell(row, 1), str(label))
        if ws.cell(row, 2).value in workbook_tabs:
            set_internal_link(ws.cell(row, 2), str(ws.cell(row, 2).value))
    set_widths(ws, [18, 30, 44, 18, 24, 18, 24, 24])
    style_overview(ws, max_col)


def build_gtm_protocol(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("01 GTM Protocol")
    title(ws, "GTM Protocol", "Essential GTM and dataLayer rules for implementing the Event Matrix.", 4)
    rows = [
        ["Topic", "Rule", "Example", "Notes"],
        ["GTM base script", "Load the GTM container once on every page. Replace GTM-XXXX with the project container ID.", "<!-- Google Tag Manager -->\n<script>/* GTM base script with GTM-XXXX */</script>\n<!-- End Google Tag Manager -->", "For SPA websites, keep the container in the root HTML shell."],
        ["dataLayer push", "Use dataLayer.push for event and context values. Do not overwrite the dataLayer object after GTM loads.", "window.dataLayer = window.dataLayer || [];\ndataLayer.push({ event: \"event_name\" });", "The Event Matrix lists the exact event and parameter values."],
        ["Flush reusable objects", "Flush page_data, ecommerce, or event_data before a new event when previous values could persist.", "dataLayer.push({ ecommerce: null });", "Use a separate push for flushing."],
        ["Controlled values", "Use lowercase ASCII snake_case, replace spaces with underscores, and remove accents for controlled analytics values.", "pret_a_porter_femme", "Keep product IDs, ISO codes, numeric values, URLs, and safe raw terms when required."],
        ["GA4 ecommerce", "Use official GA4 ecommerce event names and parameters. Keep ecommerce event blocks separate from interaction events.", "items[].item_id\nitems[].item_name\ncurrency\nvalue", "Map GTM wrapper paths in implementation notes, not as replacements for GA4 names."],
        ["Matrix status", "Record testing status as OK, KO, or Cannot test.", "OK / KO / Cannot test", "Status columns sit directly after each event value column."],
        ["Official references", "Check current official documentation before approving standard, recommended, ecommerce, and GTM dataLayer decisions.", "GA4 recommended events: https://developers.google.com/analytics/devguides/collection/ga4/reference/events\nGA4 ecommerce: https://developers.google.com/analytics/devguides/collection/ga4/ecommerce\nGA4 item parameters: https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce\nGTM dataLayer: https://developers.google.com/tag-platform/tag-manager/datalayer", "Keep external references here, not on the Overview tab."],
    ]
    if "piano_analytics" in set(plan.get("analytics_platforms", [])):
        rows.insert(-1, [
            "Piano Analytics mappings",
            "Keep Piano event names and properties separate from GA4 parameters when Piano is in scope.",
            "pa.sendEvent(\"page.display\", { page: \"homepage\" });",
            "Use Piano official names only when Piano documentation defines them.",
        ])
    for row in rows:
        ws.append(row)
    header(ws, 3, 4)
    set_widths(ws, [28, 62, 58, 42])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:D{ws.max_row}"
    style_cells(ws)


def build_parameter_reference(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("02 Parameter Reference")
    title(ws, "Parameter Reference", "Variable dictionary for parameters used in the Event Matrix.", 9)
    headers = [
        "Variable name",
        "Display name",
        "Scope",
        "Type",
        "Description",
        "Value rules",
        "Example value",
        "Register in GA4",
        "Comments",
    ]
    ws.append(headers)
    header(ws, 3, len(headers))
    custom_definitions = {
        definition["parameter_name"]: definition
        for definition in plan.get("custom_definitions", [])
    }
    for param in plan["parameters"]:
        comments = []
        if param.get("cardinality_risk") != "low":
            comments.append(f"Cardinality risk: {param.get('cardinality_risk')}")
        if param.get("pii_risk") != "low":
            comments.append(f"PII risk: {param.get('pii_risk')}")
        custom_definition = custom_definitions.get(param["parameter_name"])
        register = ""
        if custom_definition:
            register = f"Yes - {custom_definition['registration_type']}"
            if custom_definition.get("priority"):
                register = f"{register} ({custom_definition['priority']})"
        elif param.get("register_custom_definition"):
            register = "Yes"
        ws.append([
            param["parameter_name"],
            param["display_name"],
            param["scope"],
            param["type"],
            param["description"],
            param["value_rules"],
            param["example_value"],
            register,
            "; ".join(comments),
        ])
    set_widths(ws, [32, 28, 16, 16, 52, 52, 34, 24, 42])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:I{ws.max_row}"
    style_cells(ws)


def build_event_matrix(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("03 Event Matrix")
    max_col = matrix_max_col()
    title(ws, "Event Matrix", "Main tracking plan. One event slot is one reusable event definition; ecommerce blocks stay separate.", max_col)
    for slot_index, start_col in enumerate(matrix_value_columns(), 1):
        ws.merge_cells(start_row=4, start_column=start_col, end_row=4, end_column=start_col + 1)
        cell = ws.cell(4, start_col, f"Event slot {slot_index}")
        cell.fill = PatternFill("solid", fgColor=GREEN)
        cell.font = Font(bold=True)
        cell.alignment = CENTER
    slot_headers = []
    for _ in range(EVENT_SLOT_COUNT):
        slot_headers.extend(["Expected value / rule", "Test status"])
    ws.append(["Field / parameter path", "Type", *slot_headers])
    header(ws, 5, max_col)

    parameter_types = {param["parameter_name"]: param["type"] for param in plan["parameters"]}
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in plan["events"]:
        grouped[(event["journey_id"], event_family(event))].append(event)

    block_index = 1
    for (journey_id, family), events in grouped.items():
        for chunk_index in range(0, len(events), EVENT_SLOT_COUNT):
            chunk = events[chunk_index:chunk_index + EVENT_SLOT_COUNT]
            block_title = f"J-{block_index:03d} - {journey_names.get(journey_id, journey_id)} - {family}"
            row = [block_title, ""]
            for event in chunk:
                row.extend([event["event_name"], ""])
            row.extend([""] * (max_col - len(row)))
            ws.append(row)

            standard_rows = [
                ("event_id", "string", lambda event: event["event_id"]),
                ("event", "string", transport_event_name),
                ("event_classification", "string", lambda event: event["classification"]),
                ("key_event", "boolean", lambda event: "yes" if event["key_event"] else "no"),
                ("page_or_component", "string", lambda event: event["page_or_component"]),
                ("trigger", "string", lambda event: event["trigger"]),
                ("screenshot_id", "string", lambda event: f"SCR-{event['event_id']}"),
                ("qa_id", "string", lambda event: event["qa"]["qa_id"]),
            ]
            for variable, value_type, resolver in standard_rows:
                matrix_row = [variable, value_type]
                for event in chunk:
                    matrix_row.extend([resolver(event), "Cannot test"])
                matrix_row.extend([""] * (max_col - len(matrix_row)))
                ws.append(matrix_row)

            parameters = ordered_parameters_for_events(chunk)
            for parameter in parameters:
                matrix_row = [parameter, parameter_types.get(parameter, parameter_type(parameter))]
                for event in chunk:
                    value = parameter_value(event, parameter)
                    matrix_row.extend([value, "Cannot test"])
                matrix_row.extend([""] * (max_col - len(matrix_row)))
                ws.append(matrix_row)
            block_index += 1

    status_dv = DataValidation(type="list", formula1=f'"{STATUS_OPTIONS}"', allow_blank=True)
    ws.add_data_validation(status_dv)
    for col_idx in matrix_status_columns():
        col = get_column_letter(col_idx)
        status_dv.add(f"{col}6:{col}2000")
        ws.conditional_formatting.add(f"{col}6:{col}2000", CellIsRule(operator="equal", formula=['"OK"'], fill=PatternFill("solid", fgColor=GREEN)))
        ws.conditional_formatting.add(f"{col}6:{col}2000", CellIsRule(operator="equal", formula=['"KO"'], fill=PatternFill("solid", fgColor=RED)))
        ws.conditional_formatting.add(f"{col}6:{col}2000", CellIsRule(operator="equal", formula=['"Cannot test"'], fill=PatternFill("solid", fgColor=YELLOW)))
    widths = [34, 18]
    for _ in range(EVENT_SLOT_COUNT):
        widths.extend([42, 16])
    set_widths(ws, widths)
    ws.freeze_panes = "C6"
    ws.auto_filter.ref = f"A5:{get_column_letter(max_col)}{ws.max_row}"
    style_cells(ws)
    style_event_matrix_rows(ws)


def build_screenshot_register(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("04 Screenshot Register")
    title(ws, "Screenshot Register", "Attach or link screenshots used to validate Event Matrix rows.", 8)
    ws.append(["Screenshot ID", "Journey", "Event name", "Page / component", "URL / route", "What to capture", "File path or link", "Notes"])
    header(ws, 3, 8)
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    for event in plan["events"]:
        ws.append([
            f"SCR-{event['event_id']}",
            journey_names.get(event["journey_id"], event["journey_id"]),
            event["event_name"],
            event["page_or_component"],
            event["page_url_pattern"],
            f"{event['page_or_component']} - {event['trigger']}",
            "",
            f"QA case: {event['qa']['qa_id']}",
        ])
    for row in range(4, ws.max_row + 1):
        ws.row_dimensions[row].height = 56
    set_widths(ws, [24, 30, 24, 36, 34, 54, 42, 34])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:H{ws.max_row}"
    style_cells(ws)


def build_qa_cases(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("05 QA Cases")
    title(ws, "QA Cases", "Manual recette checklist for the events in the Event Matrix.", 9)
    ws.append([
        "QA ID",
        "Event name",
        "Journey",
        "Test method",
        "Test steps",
        "Expected dataLayer",
        "Expected GA4 / network",
        "Status",
        "Evidence / notes",
    ])
    header(ws, 3, 9)
    events_by_id = {event["event_id"]: event for event in plan["events"]}
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    for case in plan["qa_cases"]:
        event = events_by_id.get(case["event_id"], {})
        ws.append([
            case["qa_id"],
            case["event_name"],
            journey_names.get(event.get("journey_id"), event.get("journey_id", "")),
            join_values(case["methods"]),
            "\n".join(case["steps"]),
            "\n".join(case["expected_data_layer"]),
            "\n".join(case["expected_network"]),
            "Cannot test" if case["status"] == "not_started" else case["status"],
            join_values([case.get("debugview_expectation", ""), case["evidence"]]).strip(" | "),
        ])
    status_dv = DataValidation(type="list", formula1=f'"{STATUS_OPTIONS}"', allow_blank=True)
    ws.add_data_validation(status_dv)
    status_dv.add(f"H4:H{ws.max_row + 200}")
    ws.conditional_formatting.add(f"H4:H{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"OK"'], fill=PatternFill("solid", fgColor=GREEN)))
    ws.conditional_formatting.add(f"H4:H{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"KO"'], fill=PatternFill("solid", fgColor=RED)))
    ws.conditional_formatting.add(f"H4:H{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"Cannot test"'], fill=PatternFill("solid", fgColor=YELLOW)))
    set_widths(ws, [20, 28, 28, 28, 54, 54, 56, 16, 52])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:I{ws.max_row}"
    style_cells(ws)


def build_workbook(plan: dict[str, Any]) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    build_overview(wb, plan)
    build_gtm_protocol(wb, plan)
    build_parameter_reference(wb, plan)
    build_event_matrix(wb, plan)
    build_screenshot_register(wb, plan)
    build_qa_cases(wb, plan)
    apply_workbook_settings(wb)
    return wb


def main() -> int:
    args = parse_args()
    plan = load_plan(args.plan)
    issues = validate_plan_data(plan)
    if issues:
        print(render_text(issues), file=sys.stderr)
    if any(issue.severity == "error" for issue in issues):
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    workbook = build_workbook(plan)
    workbook.save(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
