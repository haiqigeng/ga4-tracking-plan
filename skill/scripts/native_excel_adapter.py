from __future__ import annotations

import importlib
import tempfile
from pathlib import Path
from typing import Any

from tracking_plan_model import parameter_reference_rows

XL_CALCULATION_MANUAL = -4135
XL_OPEN_XML_WORKBOOK = 51
XL_OPEN_XML_WORKBOOK_MACRO_ENABLED = 52
MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3


def _value_rows(plan: dict[str, Any], role: str) -> int:
    return len(parameter_reference_rows(plan, role))


def _event_parameter_count(
    plan: dict[str, Any],
    projection: Any,
    mapping: dict[str, Any],
) -> int:
    sheet = projection[str(mapping["sheet"])]
    event_name = str(sheet[str(mapping["event_name_cell"])].value or "").strip()
    event = next(
        (
            item
            for item in plan.get("events", [])
            if isinstance(item, dict) and str(item.get("event_name", "")) == event_name
        ),
        None,
    )
    return len(event.get("parameters", [])) if event else 0


def _copy_hyperlink(source_cell: Any, target_sheet: Any, target_cell: Any) -> None:
    try:
        target_cell.Hyperlinks.Delete()
    except Exception:
        pass
    if int(source_cell.Hyperlinks.Count) < 1:
        return
    link = source_cell.Hyperlinks.Item(1)
    target_sheet.Hyperlinks.Add(
        Anchor=target_cell,
        Address=str(link.Address or ""),
        SubAddress=str(link.SubAddress or ""),
        ScreenTip=str(link.ScreenTip or ""),
        TextToDisplay=str(target_cell.Value2 or ""),
    )


def _ensure_native_capacity(
    target_sheet: Any,
    source_sheet: Any,
    region: dict[str, Any],
    row_count: int,
) -> None:
    capacity = int(region.get("existing_capacity", 0))
    if row_count <= capacity:
        return
    policy = str(region.get("row_growth_policy", "fixed_capacity"))
    if policy == "excel_table":
        table_name = str((region.get("table") or {}).get("name", ""))
        if not table_name:
            raise ValueError("Native table growth requires a mapped Excel table name.")
        desired_address = str(source_sheet.ListObjects(table_name).Range.Address)
        target_sheet.ListObjects(table_name).Resize(target_sheet.Range(desired_address))
        return
    if policy == "prototype_row":
        prototype = int(region.get("prototype_data_row") or 0)
        if prototype < 1:
            raise ValueError("Native row growth requires an approved prototype row.")
        max_column = max(int(value) for value in region["columns"].values())
        start = int(region["data_start_row"])
        for row in range(start + capacity, start + row_count):
            source_range = target_sheet.Range(target_sheet.Cells(prototype, 1), target_sheet.Cells(prototype, max_column))
            destination = target_sheet.Range(target_sheet.Cells(row, 1), target_sheet.Cells(row, max_column))
            source_range.Copy(Destination=destination)
            destination.ClearContents()
        return
    raise ValueError(
        f"Native adaptation cannot grow {region.get('semantic_role')} beyond fixed capacity {capacity}; approve a table or prototype policy."
    )


def _sync_region(
    target_book: Any,
    source_book: Any,
    region: dict[str, Any],
    row_count: int,
    *,
    target_sheet_name: str | None = None,
    source_sheet_name: str | None = None,
) -> None:
    if not region:
        return
    target_sheet = target_book.Worksheets(target_sheet_name or str(region["sheet"]))
    source_sheet = source_book.Worksheets(source_sheet_name or str(region["sheet"]))
    _ensure_native_capacity(target_sheet, source_sheet, region, row_count)
    start = int(region["data_start_row"])
    capacity = max(int(region.get("existing_capacity", 0)), row_count, 1)
    protected = set(region.get("protected_formula_cells", []))
    for field, column_value in region["columns"].items():
        column = int(column_value)
        for row in range(start, start + capacity):
            source_cell = source_sheet.Cells(row, column)
            target_cell = target_sheet.Cells(row, column)
            coordinate = str(target_cell.Address(False, False))
            if coordinate in protected:
                continue
            target_cell.Value2 = source_cell.Value2
            if field == "event" and region.get("permitted_changes", {}).get("hyperlinks"):
                _copy_hyperlink(source_cell, target_sheet, target_cell)


def _sync_event_tab(
    target_book: Any,
    source_book: Any,
    mapping: dict[str, Any],
    parameter_count: int,
    original_sheet_names: set[str],
    claimed_originals: set[str],
    prototype_sheet_name: str,
) -> None:
    source_name = str(mapping["sheet"])
    original_name = str(mapping.get("_template_source_sheet") or source_name)
    must_clone = original_name == prototype_sheet_name or original_name in claimed_originals or original_name not in original_sheet_names
    if must_clone:
        prototype = target_book.Worksheets(prototype_sheet_name)
        prototype.Copy(After=target_book.Worksheets(target_book.Worksheets.Count))
        target_sheet = target_book.Worksheets(target_book.Worksheets.Count)
    else:
        target_sheet = target_book.Worksheets(original_name)
        claimed_originals.add(original_name)
    target_sheet.Name = source_name
    source_sheet = source_book.Worksheets(source_name)
    for coordinate in mapping.get("writable_value_cells", []):
        target_sheet.Range(str(coordinate)).Value2 = source_sheet.Range(str(coordinate)).Value2
    parameter_region = mapping.get("parameter_region") or {}
    if parameter_region:
        _sync_region(
            target_book,
            source_book,
            parameter_region,
            parameter_count,
            target_sheet_name=source_name,
            source_sheet_name=source_name,
        )
    data_layer_cell = str(mapping.get("data_layer_cell", ""))
    if data_layer_cell:
        target_sheet.Range(data_layer_cell).Value2 = source_sheet.Range(data_layer_cell).Value2
    target_sheet.Visible = source_sheet.Visible


def save_with_native_excel(
    plan: dict[str, Any],
    template: Path,
    mapping: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    """Adapt through Excel COM while using an openpyxl projection only as a value source."""
    try:
        win32 = importlib.import_module("win32com.client")
    except (ImportError, ModuleNotFoundError) as error:
        raise ValueError("The native Excel adapter requires pywin32 and Microsoft Excel.") from error

    from adapt_tracking_plan_workbook import adapt

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ga4-native-excel-") as directory:
        projection_path = Path(directory) / ("projection.xlsm" if template.suffix.lower() == ".xlsm" else "projection.xlsx")
        projection = adapt(plan, template, mapping, enforce_preflight=False)
        effective_mapping = projection._ga4_effective_mapping
        projection.save(projection_path)

        excel = None
        target_book = None
        source_book = None
        original_calculation = None
        try:
            excel = win32.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            excel.EnableEvents = False
            excel.AskToUpdateLinks = False
            excel.AutomationSecurity = MSO_AUTOMATION_SECURITY_FORCE_DISABLE
            original_calculation = excel.Calculation
            excel.Calculation = XL_CALCULATION_MANUAL
            target_book = excel.Workbooks.Open(
                str(template.resolve()),
                UpdateLinks=0,
                ReadOnly=False,
                IgnoreReadOnlyRecommended=True,
                AddToMru=False,
            )
            source_book = excel.Workbooks.Open(
                str(projection_path.resolve()),
                UpdateLinks=0,
                ReadOnly=True,
                IgnoreReadOnlyRecommended=True,
                AddToMru=False,
            )
            target_book.CheckCompatibility = False
            regions = effective_mapping["regions"]
            events = [item for item in plan.get("events", []) if isinstance(item, dict)]
            _sync_region(target_book, source_book, regions.get("event_matrix") or {}, len(events))
            reference = regions.get("parameter_reference") or {}
            if reference:
                _sync_region(
                    target_book,
                    source_book,
                    reference,
                    _value_rows(plan, str(reference.get("semantic_role", "all_used_parameters"))),
                )
            _sync_region(target_book, source_book, regions.get("data_layer_table") or {}, len(events))

            original_sheet_names = {str(sheet.Name) for sheet in target_book.Worksheets}
            claimed_originals: set[str] = set()
            prototype_sheet_name = str((regions.get("event_tab_prototype") or {}).get("sheet", ""))
            for event_mapping in regions.get("event_tabs") or []:
                _sync_event_tab(
                    target_book,
                    source_book,
                    event_mapping,
                    _event_parameter_count(plan, projection, event_mapping),
                    original_sheet_names,
                    claimed_originals,
                    prototype_sheet_name,
                )

            for internal_name in ("__tracking_plan_model", "__tracking_plan_projection"):
                for sheet in list(target_book.Worksheets):
                    if str(sheet.Name) == internal_name:
                        sheet.Delete()
                        break
                source_book.Worksheets(internal_name).Copy(After=target_book.Worksheets(target_book.Worksheets.Count))
                target_book.Worksheets(target_book.Worksheets.Count).Visible = 2

            excel.Calculation = original_calculation
            target_book.Application.CalculateBeforeSave = False
            file_format = XL_OPEN_XML_WORKBOOK_MACRO_ENABLED if output.suffix.lower() == ".xlsm" else XL_OPEN_XML_WORKBOOK
            target_book.SaveAs(str(output), FileFormat=file_format, CreateBackup=False, AddToMru=False)
        except Exception as error:
            raise ValueError(f"Native Excel adaptation failed without a reduced-fidelity fallback: {error}") from error
        finally:
            if source_book is not None:
                source_book.Close(SaveChanges=False)
            if target_book is not None:
                target_book.Close(SaveChanges=False)
            if excel is not None:
                if original_calculation is not None:
                    try:
                        excel.Calculation = original_calculation
                    except Exception:
                        pass
                excel.Quit()
        return {
            "writer": "native_excel",
            "before": projection._ga4_template_fidelity_before,
            "authorized": projection._ga4_template_fidelity_authorized,
            "effective_mapping": effective_mapping,
        }
