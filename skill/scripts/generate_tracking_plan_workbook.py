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

THIN = Side(style="thin", color=GRID)
MEDIUM = Side(style="medium", color=GRID_DARK)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BLOCK_BORDER = Border(top=MEDIUM, bottom=THIN, left=THIN, right=THIN)
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


def official_match(event: dict[str, Any]) -> str:
    return str(event.get("official_match") or event.get("official_ga4_match") or event.get("event_name") or "")


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


def event_type_for_matrix(event: dict[str, Any]) -> str:
    if event.get("classification") == "recommended_ecommerce":
        return "ecommerce"
    if str(event.get("classification", "")).startswith("piano_"):
        return "platform"
    if event.get("event_name") == "page_view":
        return "page"
    return "interaction"


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
    strategy = plan["measurement_strategy"]
    ws = wb.create_sheet("00 Overview")
    title(ws, doc["title"], "Generated from the canonical analytics tracking-plan JSON contract.", 11)
    rows = [
        ["Document", doc["title"], "Plan ID", plan["plan_id"], "Owner", doc["owner"], "Status", doc["status"]],
        ["Version", doc["version"], "Created date", doc["created_date"], "Template source", doc["template_source"], "Schema", plan["schema_version"]],
        ["Notes", doc.get("notes", ""), "", "", "", "", "", ""],
        ["Analytics platforms", join_values(plan.get("analytics_platforms", ["ga4"])), "", "", "", "", "", ""],
        [],
        ["Workbook Navigation", "", "", "", "", "", "", ""],
        ["Sheet", "Use for", "Primary audience", "Notes", "", "", "", ""],
        ["00 Overview", "Workbook navigation, event inventory, brief, assumptions, and official sources.", "Analyst, product owner", "Start here.", "", "", "", ""],
        ["01 GTM Protocol", "Shared dataLayer, GTM, naming, and ecommerce implementation conventions.", "Developer, analyst", "Not a tag-build document.", "", "", "", ""],
        ["02 Parameter Reference", "Custom definition/Data Model registration list and parameter/property dictionary.", "Analyst, analytics admin", "Use for GA4 custom dimensions, Piano Data Model properties, and value rules.", "", "", "", ""],
        ["03 Event Matrix", "Journey-based event definitions and official parameter rows.", "Analyst, developer", "Ecommerce families are split into compatible blocks.", "", "", "", ""],
        ["04 Screenshot Register", "Placeholder register for screenshots and visual QA evidence.", "QA, analyst", "Evidence only; keep tracking rules in matrix and QA sheets.", "", "", "", ""],
        ["05 QA Cases", "Recette-ready test cases, expected dataLayer, expected GA4 payload, and status.", "QA, recette agent", "Use during implementation validation.", "", "", "", ""],
        [],
        ["Measurement Strategy", "", "", "", "", "", "", ""],
        ["Archetype", "Confidence", "Evidence", "", "", "", "", ""],
    ]
    for archetype in strategy["detected_archetypes"]:
        rows.append([
            archetype["archetype"],
            archetype["confidence"],
            join_values(archetype["evidence"]),
            "",
            "",
            "",
            "",
            "",
        ])
    rows.extend([
        [],
        ["Journey", "Page role", "Business purpose", "Primary success signal", "", "", "", ""],
    ])
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    for page_role in strategy["page_roles"]:
        rows.append([
            journey_names.get(page_role["journey_id"], page_role["journey_id"]),
            page_role["page_role"],
            page_role["business_purpose"],
            page_role["primary_success_signal"],
            "",
            "",
            "",
            "",
        ])
    rows.extend([
        [],
        ["Family ID", "Family name", "Platform", "Events / actions", "Reason", "Official sources considered", "", ""],
    ])
    for family in strategy["selected_event_families"]:
        rows.append([
            family["family_id"],
            family["family_name"],
            family["analytics_platform"],
            join_values(family["events_or_actions"]),
            family["reason"],
            join_values(family["official_sources_considered"]),
            "",
            "",
        ])
    rows.extend([
        [],
        ["Excluded family", "Reason", "", "", "", "", "", ""],
    ])
    for excluded in strategy.get("excluded_event_families", []):
        rows.append([
            excluded["family_name"],
            excluded["reason"],
            "",
            "",
            "",
            "",
            "",
            "",
        ])
    if strategy.get("custom_event_acceptance"):
        rows.extend([
            [],
            ["Custom event", "Official alternatives considered", "Business reason", "Required parameters", "Registration notes", "", "", ""],
        ])
        for custom in strategy["custom_event_acceptance"]:
            rows.append([
                custom["event_name"],
                join_values(custom["official_alternatives_considered"]),
                custom["business_reason"],
                join_values(custom["required_parameters"]),
                custom["registration_notes"],
                "",
                "",
                "",
            ])
    rows.extend([
        [],
        ["Event Inventory", "", "", "", "", "", "", ""],
        ["Event ID", "Event name", "Classification", "Measurement role", "Family", "Journey", "Page / component", "Priority", "Key event", "Trigger summary", "QA ID"],
    ])
    for event in plan["events"]:
        rows.append([
            event["event_id"],
            event["event_name"],
            event["classification"],
            event["measurement_role"],
            event["business_event_family"],
            journey_names.get(event["journey_id"], event["journey_id"]),
            event["page_or_component"],
            event["priority"],
            "yes" if event["key_event"] else "no",
            event["trigger"],
            event["qa"]["qa_id"],
        ])
    rows.extend([
        [],
        ["Measurement Brief", "", "", "", "", "", "", ""],
        ["Journey", "Scope", "URL / route", "Page type", "Expected actions", "Analysis needs", "Priority", "Open questions"],
    ])
    for brief in plan["measurement_brief"]:
        rows.append([
            brief["journey_name"],
            brief["scope"],
            brief["url_or_route"],
            brief["page_type"],
            join_values(brief["expected_user_actions"]),
            join_values(brief["analysis_needs"]),
            brief["priority"],
            join_values(brief["open_questions"]),
        ])
    rows.extend([
        [],
        ["Version History", "", "", "", "", "", "", ""],
        ["Version", "Date", "Author", "Status", "Summary of changes", "Reviewed by", "Approval date", "Notes"],
        [doc["version"], doc["created_date"], doc["owner"], doc["status"], "Generated tracking plan draft", "TBD", "TBD", ""],
        [],
        ["Assumptions", "", "", "", "", "", "", ""],
        ["Assumption", "", "", "", "", "", "", ""],
    ])
    for assumption in plan["assumptions"]:
        rows.append([assumption, "", "", "", "", "", "", ""])
    rows.extend([
        [],
        ["Not Tracked / Avoided", "", "", "", "", "", "", ""],
        ["Interaction", "Reason", "", "", "", "", "", ""],
    ])
    for item in plan.get("not_tracked", []):
        rows.append([item["interaction"], item["reason"], "", "", "", "", "", ""])
    rows.extend([
        [],
        ["Documentation Sources Checked", "", "", "", "", "", "", ""],
        ["Name", "URL", "Source type", "Checked for", "", "", "", ""],
    ])
    for source in plan["documentation_sources_checked"]:
        rows.append([source["name"], source["url"], source["source_type"], source["checked_for"], "", "", "", ""])
    for row in rows:
        ws.append(row)

    for row in range(1, ws.max_row + 1):
        label = ws.cell(row, 1).value
        if label in {"Workbook Navigation", "Measurement Strategy", "Event Inventory", "Measurement Brief", "Version History", "Assumptions", "Not Tracked / Avoided", "Documentation Sources Checked"}:
            section(ws, row, str(label), 11)
        if label in {"Sheet", "Archetype", "Journey", "Family ID", "Excluded family", "Custom event", "Event ID", "Assumption", "Interaction", "Name"} or (label == "Version" and ws.cell(row, 2).value == "Date"):
            header(ws, row, 11)
        if label in wb.sheetnames:
            set_internal_link(ws.cell(row, 1), str(label))
    set_widths(ws, [26, 30, 24, 20, 28, 30, 34, 16, 16, 44, 30])
    ws.freeze_panes = "A9"
    style_cells(ws)


def build_gtm_protocol(wb: Workbook) -> None:
    ws = wb.create_sheet("01 GTM Protocol")
    title(ws, "Analytics Implementation Protocol", "Shared implementation contract for dataLayer, GTM, GA4, Piano SDK, and QA.", 5)
    rows = [
        ["Section", "Topic", "Protocol / instruction", "Code / example", "Notes"],
        ["1.A", "dataLayer push", "Use dataLayer.push for event and context values. Do not overwrite the dataLayer object after GTM loads.", "window.dataLayer = window.dataLayer || [];\ndataLayer.push({ event: \"event_name\" });", "The Event Matrix lists the exact values."],
        ["1.B", "Flush reusable objects", "Flush page_data, ecommerce, or event_data before a new event when values could persist.", "dataLayer.push({ ecommerce: null });", "Use a separate push for flushing."],
        ["1.C", "Controlled values", "Use lowercase ASCII snake_case, replace spaces with underscores, and remove accents for controlled analytics values.", "pret_a_porter_femme", "Keep product IDs, ISO codes, numeric values, and safe raw terms when required."],
        ["1.D", "Ecommerce", "Use official GA4 ecommerce parameters in the plan and map GTM wrapper paths only in implementation notes.", "GA4: items[].item_id\nGTM source: ecommerce.items[].item_id", "Do not mix ecommerce events with generic interaction rows."],
        ["1.E", "Ecommerce scope", "Prefer event-level list and promotion parameters when all items share the same value. Item-level values override event-level values.", "event-level item_list_name used\nitems[].item_list_name omitted", "The Event Matrix marks inherited item rows as event_level_used."],
        ["1.F", "Matrix availability values", "Use explicit placeholders so optional official parameters are not silently omitted.", "not_available\nnot_applicable\nevent_level_used\nsend_default_quantity", "These are planning values, not QA test statuses."],
        ["1.G", "Testing records", "Record test status as OK, KO, or Cannot test.", "OK / KO / Cannot test", "The QA Cases sheet provides the validation contract."],
        ["1.H", "Piano Analytics mappings", "When Piano Analytics is in scope, keep Piano event names and properties separate from GA4 parameters.", "pa.sendEvent(\"page.display\", { page: \"homepage\" });", "Do not send GA4 ecommerce item names as Piano properties unless Piano documentation defines the same property."],
    ]
    for row in rows:
        ws.append(row)
    header(ws, 3, 5)
    set_widths(ws, [12, 28, 62, 58, 42])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:E{ws.max_row}"
    style_cells(ws)


def build_parameter_reference(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("02 Parameter Reference")
    title(ws, "Parameter Reference", "Human-readable dictionary for variables and parameters used in the plan.", 11)
    ws.append(["Custom Definitions To Register", "", "", "", "", "", "", "", "", "", ""])
    section(ws, 3, "Custom Definitions To Register", 11)
    custom_headers = [
        "Parameter name",
        "Display name",
        "Scope",
        "Registration type",
        "Reason",
        "Priority",
        "",
        "",
        "",
        "",
        "",
    ]
    ws.append(custom_headers)
    header(ws, 4, len(custom_headers))
    if plan.get("custom_definitions"):
        for definition in plan["custom_definitions"]:
            ws.append([
                definition["parameter_name"],
                definition["display_name"],
                definition["scope"],
                definition["registration_type"],
                definition["reason"],
                definition["priority"],
                "",
                "",
                "",
                "",
                "",
            ])
    else:
        ws.append(["No custom definitions required in this draft.", "", "", "", "", "", "", "", "", "", ""])
    ws.append([])
    dictionary_section_row = ws.max_row + 1
    ws.append(["Parameter Dictionary", "", "", "", "", "", "", "", "", "", ""])
    section(ws, dictionary_section_row, "Parameter Dictionary", 11)
    dictionary_header_row = ws.max_row + 1
    headers = [
        "Variable name",
        "Display name",
        "Scope",
        "Type",
        "Description",
        "Reporting purpose",
        "Value rules",
        "Example values",
        "Comments",
    ]
    ws.append(headers)
    header(ws, dictionary_header_row, len(headers))
    for param in plan["parameters"]:
        comments = []
        if param.get("register_custom_definition"):
            comments.append("Register custom definition")
        if param.get("cardinality_risk") != "low":
            comments.append(f"Cardinality risk: {param.get('cardinality_risk')}")
        if param.get("pii_risk") != "low":
            comments.append(f"PII risk: {param.get('pii_risk')}")
        ws.append([
            param["parameter_name"],
            param["display_name"],
            param["scope"],
            param["type"],
            param["description"],
            param["reporting_purpose"],
            param["value_rules"],
            param["example_value"],
            "; ".join(comments),
        ])
    set_widths(ws, [32, 28, 18, 18, 52, 52, 52, 34, 42])
    ws.freeze_panes = f"A{dictionary_header_row + 1}"
    ws.auto_filter.ref = f"A{dictionary_header_row}:I{ws.max_row}"
    style_cells(ws)


def build_event_matrix(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("03 Event Matrix")
    max_col = matrix_max_col()
    title(ws, "Event Matrix", "Journey-based event matrix. Ecommerce events are kept in separate ecommerce-only blocks.", max_col)
    for slot_index, start_col in enumerate(matrix_value_columns(), 1):
        ws.merge_cells(start_row=4, start_column=start_col, end_row=4, end_column=start_col + 1)
        cell = ws.cell(4, start_col, f"Event slot {slot_index}")
        cell.fill = PatternFill("solid", fgColor=GREEN)
        cell.font = Font(bold=True)
        cell.alignment = CENTER
    slot_headers = []
    for _ in range(EVENT_SLOT_COUNT):
        slot_headers.extend(["Value / rule", "Test status"])
    ws.append(["Variable / parameter", "Type", *slot_headers])
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
                ("qa_id", "string", lambda event: event["qa"]["qa_id"]),
                ("event_name", "string", lambda event: event["event_name"]),
                ("event_type", "string", event_type_for_matrix),
                ("classification", "string", lambda event: event["classification"]),
                ("measurement_role", "string", lambda event: event["measurement_role"]),
                ("business_event_family", "string", lambda event: event["business_event_family"]),
                ("official_match", "string", official_match),
                ("primary_platform", "string", lambda event: event.get("primary_platform") or "ga4"),
                ("page_or_component", "string", lambda event: event["page_or_component"]),
                ("trigger", "string", lambda event: event["trigger"]),
                ("data_dependencies", "array", lambda event: join_values(event.get("data_dependencies", []))),
                ("business_question", "string", lambda event: event["business_question"]),
                ("key_event", "boolean", lambda event: str(event["key_event"]).lower()),
                ("event", "string", transport_event_name),
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
    title(ws, "Screenshot Register", "Attach or link screenshots for page views and interaction events.", 9)
    ws.append(["Screenshot ID", "Journey", "Event name", "Capture type", "URL / route", "What the screenshot must show", "File path or link", "Visual evidence area", "Notes"])
    header(ws, 3, 9)
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    for event in plan["events"]:
        capture_type = "Page view" if event["event_name"] == "page_view" else "Interaction"
        if event["classification"] == "recommended_ecommerce":
            capture_type = "Ecommerce interaction"
        ws.append([
            f"SCR-{event['event_id']}",
            journey_names.get(event["journey_id"], event["journey_id"]),
            event["event_name"],
            capture_type,
            event["page_url_pattern"],
            f"{event['page_or_component']} - {event['trigger']}",
            "",
            "Paste screenshot here",
            f"QA case: {event['qa']['qa_id']}",
        ])
    for row in range(4, ws.max_row + 1):
        ws.row_dimensions[row].height = 82
        ws.cell(row, 8).fill = PatternFill("solid", fgColor=GRAY)
        ws.cell(row, 8).alignment = CENTER
    set_widths(ws, [24, 30, 24, 22, 34, 54, 42, 38, 40])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:I{ws.max_row}"
    style_cells(ws)


def build_qa_cases(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("05 QA Cases")
    title(ws, "QA Cases", "Validation contract for DebugView, GTM Preview, network checks, and release sign-off.", 11)
    ws.append([
        "QA ID",
        "Journey",
        "Event name",
        "Event ID",
        "Methods",
        "Steps",
        "Expected dataLayer",
        "Expected network / platform payload",
        "DebugView expectation",
        "Status",
        "Evidence / notes",
    ])
    header(ws, 3, 11)
    events_by_id = {event["event_id"]: event for event in plan["events"]}
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    for case in plan["qa_cases"]:
        event = events_by_id.get(case["event_id"], {})
        ws.append([
            case["qa_id"],
            journey_names.get(event.get("journey_id"), event.get("journey_id", "")),
            case["event_name"],
            case["event_id"],
            join_values(case["methods"]),
            "\n".join(case["steps"]),
            "\n".join(case["expected_data_layer"]),
            "\n".join(case["expected_network"]),
            case["debugview_expectation"],
            "Cannot test" if case["status"] == "not_started" else case["status"],
            case["evidence"],
        ])
    status_dv = DataValidation(type="list", formula1=f'"{STATUS_OPTIONS}"', allow_blank=True)
    ws.add_data_validation(status_dv)
    status_dv.add(f"J4:J{ws.max_row + 200}")
    ws.conditional_formatting.add(f"J4:J{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"OK"'], fill=PatternFill("solid", fgColor=GREEN)))
    ws.conditional_formatting.add(f"J4:J{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"KO"'], fill=PatternFill("solid", fgColor=RED)))
    ws.conditional_formatting.add(f"J4:J{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"Cannot test"'], fill=PatternFill("solid", fgColor=YELLOW)))
    set_widths(ws, [20, 28, 28, 22, 28, 52, 52, 56, 44, 16, 44])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:K{ws.max_row}"
    style_cells(ws)


def build_workbook(plan: dict[str, Any]) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    build_overview(wb, plan)
    build_gtm_protocol(wb)
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
