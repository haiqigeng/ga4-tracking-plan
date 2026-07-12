from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from ecommerce_matrix import (
    event_family as ecommerce_event_family,
)
from ecommerce_matrix import (
    ordered_parameters_for_events,
    parameter_matrix_value,
    parameter_type,
)
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.datavalidation import DataValidation
from tracking_plan_screenshots import PREVIEW_HEIGHT, PREVIEW_WIDTH, create_screenshot_preview, resolve_screenshot, screenshot_digest, screenshot_files
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
SCREENSHOT_STATUS_OPTIONS = "capture_required,captured,shared_evidence,skip_allowed,not_needed,blocked"
SCREENSHOT_ROW_HEIGHT = 216


def matrix_max_col() -> int:
    return 2 + EVENT_SLOT_COUNT


def matrix_value_columns() -> list[int]:
    return [3 + index for index in range(EVENT_SLOT_COUNT)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a human analytics tracking-plan workbook from the canonical JSON contract.")
    parser.add_argument("plan", type=Path, help="Path to a JSON tracking plan using schema-tracking-plan.json.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output XLSX path.")
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=None,
        help="Optional screenshot evidence folder. Defaults to a screenshots folder next to the plan JSON when present.",
    )
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
    if event.get("classification") == "recommended_ecommerce":
        return ecommerce_event_family(event)
    family = str(event.get("business_event_family", "")).strip()
    return family.replace("_", " ").title() if family else "Interactions"


def transport_event_name(event: dict[str, Any]) -> str:
    data_layer = event.get("data_layer", {})
    if isinstance(data_layer, dict) and data_layer.get("event_key"):
        return str(data_layer["event_key"])
    ga4_payload = event.get("ga4_payload", {})
    if isinstance(ga4_payload, dict) and ga4_payload.get("event_name"):
        return str(ga4_payload["event_name"])
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


def parameter_value_rules(parameter: dict[str, Any]) -> str:
    allowed = [str(value) for value in parameter.get("allowed_values", []) if str(value).strip()]
    if allowed:
        return " | ".join(allowed)
    return str(parameter.get("value_rules", ""))


def javascript_object(value: dict[str, Any]) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    return re.sub(r'(?m)^(\s*)"([A-Za-z_$][A-Za-z0-9_$]*)":', r"\1\2:", text)


def datalayer_example(event: dict[str, Any]) -> str:
    data_layer = event.get("data_layer", {})
    push = data_layer.get("push", {}) if isinstance(data_layer, dict) else {}
    if not isinstance(push, dict) or not push:
        classification = str(event.get("classification", ""))
        if classification == "automatic":
            return "No manual dataLayer push. GA4 collects this event automatically when configured correctly."
        if classification == "enhanced_measurement":
            return "No manual dataLayer push when GA4 Enhanced Measurement is enabled and sufficient."
        return "No manual dataLayer example supplied; implementation source must be confirmed."

    lines = []
    for key in data_layer.get("flush_keys", []):
        lines.append(f"dataLayer.push({{ {key}: null }});")
    lines.append(f"dataLayer.push({javascript_object(push)});")
    return "\n".join(lines)


def gtm_mapping(event: dict[str, Any]) -> str:
    name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    if classification == "automatic":
        return "GA4 automatic collection; do not create a duplicate manual event tag."
    if classification == "enhanced_measurement" and not event.get("data_layer"):
        return "Enable in the GA4 web stream; do not create a duplicate manual event tag."

    payload = event.get("ga4_payload", {})
    parameters = payload.get("parameters", {}) if isinstance(payload, dict) else {}
    data_layer = event.get("data_layer", {})
    push = data_layer.get("push", {}) if isinstance(data_layer, dict) else {}
    prefix = "ecommerce" if isinstance(push, dict) and isinstance(push.get("ecommerce"), dict) else "event_data"
    mappings = [f"Custom Event trigger: {name}", f"GA4 event name: {name}"]
    for parameter in parameters if isinstance(parameters, dict) else []:
        mappings.append(f"{prefix}.{parameter} -> {parameter}")
    if isinstance(payload, dict) and payload.get("items"):
        mappings.append("ecommerce.items -> items")
    notes = str(data_layer.get("mapping_notes", "")) if isinstance(data_layer, dict) else ""
    if notes:
        mappings.append(notes)
    return "\n".join(mappings)


def build_overview(wb: Workbook, plan: dict[str, Any]) -> None:
    doc = plan["document"]
    ws = wb.create_sheet("00 Overview")
    max_col = 8
    title(ws, doc["title"], "Document details and workbook navigation.", max_col)

    rows = [
        ["Document Summary", "", "", "", "", "", "", "", ""],
        ["Document", doc["title"], "Owner / contact", doc["owner"], "Publish date", doc["publish_date"], "", ""],
        ["Version", doc["version"], "", "", "", "", "", ""],
        [],
        ["Sheet Contents", "", "", "", "", "", "", "", ""],
        ["#", "Sheet", "What it is for", "", "", "", "", ""],
        ["1", "00 Overview", "Document information and version history.", "", "", "", "", ""],
        ["2", "01 GTM Protocol", "Shared GTM/dataLayer rules and official references.", "", "", "", "", ""],
        ["3", "02 Parameter Reference", "Variable dictionary and value rules.", "", "", "", "", ""],
        ["4", "03 Event Matrix", "Main tracking plan: events, parameters, and value rules.", "", "", "", "", ""],
        ["5", "04 DataLayer Examples", "Complete per-event GTM and dataLayer implementation examples.", "", "", "", "", ""],
        ["6", "05 Screenshot Register", "Page and interaction evidence supporting implementation.", "", "", "", "", ""],
        [],
        ["Version History", "", "", "", "", "", "", "", ""],
        ["Version", "Date", "Owner", "Summary", "Publish date", "", "", "", ""],
        [doc["version"], doc["publish_date"], doc["owner"], "GA4 tracking plan prepared for review.", doc["publish_date"], "", "", "", ""],
    ]
    for row in rows:
        ws.append((row + [""] * max_col)[:max_col])

    workbook_tabs = {
        "00 Overview",
        "01 GTM Protocol",
        "02 Parameter Reference",
        "03 Event Matrix",
        "04 DataLayer Examples",
        "05 Screenshot Register",
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
    user_context = plan.get("user_context", {})
    user_context_example = (
        "dataLayer.push({\n"
        "  user_context: {\n"
        "    user_id: \"%opaque_user_id%\",\n"
        "    login_status: \"logged_in\",\n"
        "    customer_status: \"returning\",\n"
        "    account_type: \"standard\"\n"
        "  }\n"
        "});"
    )
    user_properties = "\n".join(
        f"{item.get('source_path')} -> GA4 user property {item.get('parameter_name')}"
        for item in user_context.get("user_properties", [])
        if isinstance(item, dict)
    ) or "No custom GA4 user properties planned."
    ads = user_context.get("advertising_user_data", {})
    ads_rule = str(ads.get("handling_rule", "Direct identifiers are not sent to GA4.")) if isinstance(ads, dict) else "Direct identifiers are not sent to GA4."
    rows = [
        ["Topic", "Rule", "Example", "Notes"],
        ["GTM base script", "Load the GTM container once on every page. Replace GTM-XXXX with the project container ID.", "<!-- Google Tag Manager -->\n<script>/* GTM base script with GTM-XXXX */</script>\n<!-- End Google Tag Manager -->", "For SPA websites, keep the container in the root HTML shell."],
        ["dataLayer push", "Use dataLayer.push for event and context values. Do not overwrite the dataLayer object after GTM loads.", "window.dataLayer = window.dataLayer || [];\ndataLayer.push({ event: \"add_to_cart\" });", "In the dataLayer object, the GTM trigger key is event. GA4 event_name is the GA4 tag setting/payload name."],
        ["Flush reusable objects", "Flush page_data, ecommerce, or event_data before a new event when previous values could persist.", "dataLayer.push({ ecommerce: null });", "Use a separate push for flushing."],
        ["Controlled values", "Use lowercase ASCII snake_case, replace spaces with underscores, and remove accents for controlled analytics values.", "pret_a_porter_femme", "Keep product IDs, ISO codes, numeric values, URLs, and safe raw terms when required."],
        ["GA4 ecommerce", "Use official GA4 ecommerce event names and parameters. Keep ecommerce event blocks separate from interaction events.", "items[].item_id\nitems[].item_name\ncurrency\nvalue", "Map GTM wrapper paths in implementation notes, not as replacements for GA4 names."],
        ["Consent", "Set and update consent through the CMP or GTM consent APIs before affected tags process user or event data.", "analytics_storage\nad_storage\nad_user_data\nad_personalization", "The tracking plan records dependencies but does not make the legal consent decision."],
        ["Connected user context", "Push user_context independently when authentication state is known, after successful login, and after logout. Do not repeat these fields inside every event push.", user_context_example, f"Plan status: {user_context.get('status', 'not_applicable')}. Keep the object available before dependent GA4 events."],
        ["GA4 User-ID", "Map user_context.user_id only to the Google tag user_id setting. Omit before first sign-in and set null after logout.", "user_context.user_id -> Google tag user_id", "Never send user_id as an event parameter or user property, and never register it as a custom dimension."],
        ["GA4 user properties", "Map only approved low-cardinality connected-user fields as GA4 user properties.", user_properties, "Register planned custom user properties in GA4. Do not include direct identifiers."],
        ["Advertising user data", "Keep direct identifiers in a separately governed non-GA4 object only when another approved advertising implementation explicitly requires them.", str(ads.get("data_layer_object", "")) or "Not applicable", ads_rule],
        ["Official references", "Check current official documentation before approving standard, recommended, ecommerce, connected-user, and GTM dataLayer decisions.", "GA4 recommended events: https://developers.google.com/analytics/devguides/collection/ga4/reference/events\nGA4 ecommerce: https://developers.google.com/analytics/devguides/collection/ga4/ecommerce\nGA4 item parameters: https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce\nGA4 User-ID: https://developers.google.com/analytics/devguides/collection/ga4/user-id\nGA4 user properties: https://developers.google.com/analytics/devguides/collection/protocol/ga4/user-properties\nGTM dataLayer: https://developers.google.com/tag-platform/tag-manager/datalayer\nConsent mode: https://developers.google.com/tag-platform/security/guides/consent", "Keep external references here, not on the Overview tab."],
    ]
    for row in rows:
        ws.append(row)
    header(ws, 3, 4)
    set_widths(ws, [28, 62, 58, 42])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:D{ws.max_row}"
    style_cells(ws)


def build_parameter_reference(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("02 Parameter Reference")
    title(ws, "Parameter Reference", "Variable dictionary for parameters used in the Event Matrix.", 11)
    headers = [
        "Variable name",
        "Display name",
        "Scope",
        "Type",
        "Description",
        "Value rules",
        "Example value",
        "Availability",
        "Data owner",
        "Register in GA4",
        "Privacy / consent",
    ]
    ws.append(headers)
    header(ws, 3, len(headers))
    for param in plan["parameters"]:
        privacy = []
        if param.get("cardinality_risk") != "low":
            privacy.append(f"Cardinality risk: {param.get('cardinality_risk')}")
        if param.get("pii_risk") != "low":
            privacy.append(f"PII risk: {param.get('pii_risk')}")
        if param.get("consent_dependency"):
            privacy.append(f"Consent: {param.get('consent_dependency')}")
        if param.get("scope") == "implementation" and param.get("pii_risk") in {"medium", "high"}:
            privacy.append("Implementation-only: do not map to ordinary GA4 parameters")
        register = "Yes" if param.get("register_custom_definition") else "No"
        ws.append([
            param["parameter_name"],
            param["display_name"],
            param["scope"],
            param["type"],
            param["description"],
            parameter_value_rules(param),
            param["example_value"],
            param["availability"],
            param["data_owner"],
            register,
            "; ".join(privacy),
        ])
    set_widths(ws, [32, 28, 16, 16, 48, 48, 30, 24, 30, 20, 38])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:K{ws.max_row}"
    style_cells(ws)


def build_event_matrix(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("03 Event Matrix")
    max_col = matrix_max_col()
    title(ws, "Event Matrix", "Main tracking plan. One event slot is one reusable event definition; ecommerce blocks stay separate.", max_col)
    for slot_index, start_col in enumerate(matrix_value_columns(), 1):
        cell = ws.cell(4, start_col, f"Event slot {slot_index}")
        cell.fill = PatternFill("solid", fgColor=GREEN)
        cell.font = Font(bold=True)
        cell.alignment = CENTER
    slot_headers = ["Expected value / rule"] * EVENT_SLOT_COUNT
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
                row.append(event["event_name"])
            row.extend([""] * (max_col - len(row)))
            ws.append(row)

            standard_rows = [
                ("event_classification", "string", lambda event: event["classification"]),
                ("evidence_status", "string", lambda event: f"{event.get('evidence_basis', {}).get('status', '')} | {event.get('evidence_basis', {}).get('confidence', '')}"),
                ("analysis_use", "string", lambda event: event.get("analysis_use", "")),
                ("trigger", "string", lambda event: event["trigger"]),
                ("event", "string", transport_event_name),
            ]
            for variable, value_type, resolver in standard_rows:
                matrix_row = [variable, value_type]
                for event in chunk:
                    matrix_row.append(resolver(event))
                matrix_row.extend([""] * (max_col - len(matrix_row)))
                ws.append(matrix_row)

            parameters = ordered_parameters_for_events(chunk)
            for parameter in parameters:
                matrix_row = [parameter, parameter_types.get(parameter, parameter_type(parameter))]
                for event in chunk:
                    value = parameter_value(event, parameter)
                    matrix_row.append(value)
                matrix_row.extend([""] * (max_col - len(matrix_row)))
                ws.append(matrix_row)
            block_index += 1

    widths = [34, 18] + ([44] * EVENT_SLOT_COUNT)
    set_widths(ws, widths)
    ws.freeze_panes = "C6"
    ws.auto_filter.ref = f"A5:{get_column_letter(max_col)}{ws.max_row}"
    style_cells(ws)
    style_event_matrix_rows(ws)


def build_datalayer_examples(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("04 DataLayer Examples")
    title(ws, "DataLayer Examples", "Complete developer examples aligned with the Event Matrix and final GA4 payload.", 7)
    headers = ["Journey", "Event", "Evidence", "Trigger", "dataLayer.push example", "GTM and GA4 mapping", "Implementation notes"]
    ws.append(headers)
    header(ws, 3, len(headers))
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}

    for event in plan["events"]:
        notes = str(event.get("implementation_notes", ""))
        if event.get("classification") == "recommended_ecommerce":
            notes = f"Official GA4 ecommerce event. {notes}".strip()
        elif event.get("classification") == "custom":
            notes = f"Custom GA4 event using the project dataLayer convention. {notes}".strip()
        ws.append([
            journey_names.get(event["journey_id"], event["journey_id"]),
            event["event_name"],
            f"{event.get('evidence_basis', {}).get('status', '')} | {event.get('evidence_basis', {}).get('confidence', '')}",
            event["trigger"],
            datalayer_example(event),
            gtm_mapping(event),
            notes,
        ])
        ws.row_dimensions[ws.max_row].height = 180

    set_widths(ws, [28, 24, 22, 44, 76, 54, 48])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:G{ws.max_row}"
    style_cells(ws)


def embed_screenshot_previews(ws, image_rows: list[tuple[int, Path, dict[str, Any]]], preview_dir: Path) -> None:
    rendered_previews: dict[str, int] = {}
    for row_number, screenshot_path, evidence in image_rows:
        preview_path = create_screenshot_preview(
            screenshot_path,
            preview_dir / f"{row_number:03d}_{screenshot_path.stem}.png",
            crop=evidence.get("crop"),
            annotation=evidence.get("annotation"),
        )
        if not preview_path:
            continue
        digest = screenshot_digest(preview_path)
        if digest in rendered_previews:
            raise ValueError(
                f"Screenshot rows {rendered_previews[digest]} and {row_number} render the same visual evidence. "
                "Use one shared_evidence row or capture the actual distinct scenario."
            )
        rendered_previews[digest] = row_number
        image = XLImage(str(preview_path))
        image.width = PREVIEW_WIDTH
        image.height = PREVIEW_HEIGHT
        ws.add_image(image, f"C{row_number}")


def build_screenshot_register(
    wb: Workbook,
    plan: dict[str, Any],
    screenshot_dir: Path | None = None,
    preview_dir: Path | None = None,
) -> None:
    ws = wb.create_sheet("05 Screenshot Register")
    title(ws, "Screenshot Register", "Page and interaction evidence supporting the Event Matrix.", 8)
    ws.append(["Journey", "Event(s)", "Screenshot preview", "Page / component", "URL / route", "Capture objective", "Status", "Notes"])
    header(ws, 3, 8)
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    events_by_id = {event["event_id"]: event for event in plan["events"]}
    files_by_name = screenshot_files(screenshot_dir)
    preview_dir = preview_dir or (screenshot_dir / "_workbook_previews" if screenshot_dir else None)

    image_rows: list[tuple[int, Path, dict[str, Any]]] = []
    for evidence in plan["screenshot_evidence"]:
        related_events = [events_by_id[event_id] for event_id in evidence["event_ids"] if event_id in events_by_id]
        event_names = [event["event_name"] for event in related_events]
        journeys = list(dict.fromkeys(journey_names.get(event["journey_id"], event["journey_id"]) for event in related_events))
        screenshot_path = resolve_screenshot(evidence, files_by_name)
        notes = str(evidence.get("notes", ""))
        if evidence.get("file_name") and not screenshot_path:
            notes = f"{notes} Evidence file not found in the selected screenshot folder.".strip()
        row_number = ws.max_row + 1
        ws.append([
            " | ".join(journeys),
            " | ".join(event_names),
            "",
            evidence["page_or_component"],
            evidence["url_or_route"],
            evidence["capture_objective"],
            evidence["status"],
            notes,
        ])
        if screenshot_path and preview_dir:
            image_rows.append((row_number, screenshot_path, evidence))
    for row in range(4, ws.max_row + 1):
        ws.row_dimensions[row].height = SCREENSHOT_ROW_HEIGHT
    if preview_dir:
        embed_screenshot_previews(ws, image_rows, preview_dir)
    status_dv = DataValidation(type="list", formula1=f'"{SCREENSHOT_STATUS_OPTIONS}"', allow_blank=True)
    ws.add_data_validation(status_dv)
    status_dv.add(f"G4:G{ws.max_row + 200}")
    ws.conditional_formatting.add(f"G4:G{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"captured"'], fill=PatternFill("solid", fgColor=GREEN)))
    ws.conditional_formatting.add(f"G4:G{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"shared_evidence"'], fill=PatternFill("solid", fgColor=TEAL_LIGHT)))
    ws.conditional_formatting.add(f"G4:G{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"skip_allowed"'], fill=PatternFill("solid", fgColor=NOT_AVAILABLE_FILL)))
    ws.conditional_formatting.add(f"G4:G{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"capture_required"'], fill=PatternFill("solid", fgColor=YELLOW)))
    ws.conditional_formatting.add(f"G4:G{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"blocked"'], fill=PatternFill("solid", fgColor=RED)))
    ws.conditional_formatting.add(f"G4:G{ws.max_row + 200}", CellIsRule(operator="equal", formula=['"not_needed"'], fill=PatternFill("solid", fgColor=GRAY)))
    set_widths(ws, [24, 28, 72, 26, 34, 44, 18, 46])
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:H{ws.max_row}"
    style_cells(ws)


def build_workbook(
    plan: dict[str, Any],
    screenshot_dir: Path | None = None,
    preview_dir: Path | None = None,
) -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    build_overview(wb, plan)
    build_gtm_protocol(wb, plan)
    build_parameter_reference(wb, plan)
    build_event_matrix(wb, plan)
    build_datalayer_examples(wb, plan)
    build_screenshot_register(wb, plan, screenshot_dir=screenshot_dir, preview_dir=preview_dir)
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
    screenshot_dir = args.screenshot_dir
    if screenshot_dir is None:
        default_screenshot_dir = args.plan.parent / "screenshots"
        if default_screenshot_dir.exists():
            screenshot_dir = default_screenshot_dir
    with TemporaryDirectory(prefix="tracking_plan_screenshot_previews_") as tmp_dir:
        workbook = build_workbook(plan, screenshot_dir=screenshot_dir, preview_dir=Path(tmp_dir))
        workbook.save(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
