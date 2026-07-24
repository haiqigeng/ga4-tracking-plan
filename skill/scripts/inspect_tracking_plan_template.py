from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

ALIASES = {
    "event": {
        "event", "event name", "event_name", "evenement", "nom evenement",
        "nom de levenement", "nom de l evenement",
    },
    "journey": {"journey", "parcours", "funnel", "etape du parcours"},
    "classification": {"classification", "type evenement", "event type"},
    "definition": {"definition", "description", "explication"},
    "trigger": {
        "trigger", "declencheur", "condition de declenchement",
        "regle de declenchement",
    },
    "locations": {
        "locations", "pages routes components", "emplacement", "page", "url",
        "pages routes composants",
    },
    "variables": {
        "variables", "parameters", "parametres", "variables propres a levenement",
        "event specific variables",
    },
    "variable": {
        "variable", "parameter", "parametre", "nom variable", "nom du parametre",
    },
    "scope": {"scope", "portee", "niveau"},
    "type": {"type", "format", "type format"},
    "requirement": {"requirement", "exigence", "statut", "obligation"},
    "condition": {"condition", "condition dexigence", "required when"},
    "values": {
        "possible values rule", "valeurs possibles regle", "valeurs des variables",
        "regles de valeurs", "regle de valeur", "valeurs possibles",
    },
    "example": {"example", "exemple", "example value", "valeur exemple"},
    "concerned_events": {
        "concerned events", "evenements concernes", "disponibilite par evenement",
    },
    "source_path": {
        "datalayer path source", "chemin datalayer source", "source",
        "chemin datalayer",
    },
    "notes": {"notes", "note"},
    "datalayer": {
        "datalayer specification", "specification datalayer", "datalayer",
        "exemple datalayer",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a supplied tracking-plan workbook and propose semantic regions."
    )
    parser.add_argument("template", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    return parser.parse_args()


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


NORMALIZED_ALIASES = {
    field: {normalize(value) for value in values}
    for field, values in ALIASES.items()
}


def field_for(value: Any) -> str | None:
    normalized = normalize(value)
    for field, aliases in NORMALIZED_ALIASES.items():
        if normalized in aliases:
            return field
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sheet_inventory(sheet) -> dict[str, Any]:
    formulas = []
    comments = []
    for row in sheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("=") and len(formulas) < 20:
                formulas.append(cell.coordinate)
            if cell.comment and len(comments) < 20:
                comments.append(cell.coordinate)
    return {
        "title": sheet.title,
        "state": sheet.sheet_state,
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "merged_ranges": [str(value) for value in sheet.merged_cells.ranges],
        "formula_cells": formulas,
        "comment_cells": comments,
        "table_names": sorted(sheet.tables.keys()),
        "data_validation_count": len(sheet.data_validations.dataValidation),
        "image_count": len(sheet._images),
        "freeze_panes": str(sheet.freeze_panes or ""),
    }


def header_candidates(sheet) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    max_row = min(sheet.max_row, 120)
    max_column = min(sheet.max_column, 50)
    for row in range(1, max_row + 1):
        columns: dict[str, int] = {}
        for column in range(1, max_column + 1):
            field = field_for(sheet.cell(row, column).value)
            if field and field not in columns:
                columns[field] = column
        if len(columns) >= 2:
            candidates.append(
                {
                    "sheet": sheet.title,
                    "header_row": row,
                    "data_start_row": row + 1,
                    "columns": columns,
                }
            )
    return candidates


def classify_regions(
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    event_matrix: dict[str, Any] = {}
    parameter_reference: dict[str, Any] = {}
    data_layer_table: dict[str, Any] = {}
    for candidate in candidates:
        fields = set(candidate["columns"])
        if not data_layer_table and {"event", "datalayer"} <= fields:
            data_layer_table = candidate
        if not event_matrix and "event" in fields and len(
            fields & {"journey", "definition", "trigger", "locations", "variables"}
        ) >= 2:
            event_matrix = candidate
        if not parameter_reference and "variable" in fields and len(
            fields & {"scope", "type", "definition", "values", "example", "concerned_events"}
        ) >= 3:
            parameter_reference = candidate
    return event_matrix, parameter_reference, data_layer_table


def event_tab_candidate(sheet) -> dict[str, Any] | None:
    field_cells: dict[str, str] = {}
    for row in range(1, min(sheet.max_row, 80) + 1):
        for column in range(1, min(sheet.max_column, 20) + 1):
            field = field_for(sheet.cell(row, column).value)
            if field and field not in field_cells:
                field_cells[field] = sheet.cell(row, column).coordinate
    if "event" not in field_cells or len(
        set(field_cells) & {"definition", "trigger", "locations", "datalayer"}
    ) < 2:
        return None
    field_rows = {
        sheet[coordinate].row
        for field, coordinate in field_cells.items()
        if field in {"event", "definition", "trigger", "locations", "datalayer"}
    }
    if len(field_rows) < 3:
        return None
    event_label = sheet[field_cells["event"]]
    value_cell = sheet.cell(event_label.row, event_label.column + 1).coordinate
    parameter_region = None
    for candidate in header_candidates(sheet):
        if "variable" in candidate["columns"] and len(
            set(candidate["columns"]) & {"scope", "type", "requirement", "definition", "values"}
        ) >= 3:
            parameter_region = candidate
            break
    data_layer_cell = ""
    if "datalayer" in field_cells:
        label_cell = sheet[field_cells["datalayer"]]
        for row in range(label_cell.row, min(sheet.max_row, label_cell.row + 5) + 1):
            for column in range(1, min(sheet.max_column, 15) + 1):
                value = sheet.cell(row, column).value
                if isinstance(value, str) and "window.dataLayer" in value:
                    data_layer_cell = sheet.cell(row, column).coordinate
                    break
            if data_layer_cell:
                break
        if not data_layer_cell:
            data_layer_cell = sheet.cell(label_cell.row + 1, 1).coordinate
    return {
        "sheet": sheet.title,
        "event_name_cell": value_cell,
        "field_labels": field_cells,
        "parameter_region": parameter_region,
        "data_layer_cell": data_layer_cell,
    }


def inspect(path: Path) -> dict[str, Any]:
    workbook = load_workbook(
        path,
        data_only=False,
        read_only=False,
        keep_links=True,
        keep_vba=path.suffix.lower() == ".xlsm",
    )
    candidates = [
        candidate
        for sheet in workbook.worksheets
        for candidate in header_candidates(sheet)
    ]
    event_matrix, parameter_reference, data_layer_table = classify_regions(candidates)
    event_tabs = [
        candidate
        for sheet in workbook.worksheets
        if (candidate := event_tab_candidate(sheet)) is not None
    ]
    review: list[str] = []
    if not event_matrix:
        review.append("No semantic Event Matrix region was recognized.")
    if not parameter_reference:
        review.append("No semantic Parameter Reference region was recognized.")
    if not event_tabs and not data_layer_table:
        review.append(
            "No event-tab or dataLayer-table region was recognized; do not add sections without template approval."
        )
    return {
        "mapping_version": "1.0",
        "template": {
            "path": str(path.resolve()),
            "sha256": sha256(path),
            "extension": path.suffix.lower(),
        },
        "sheets": [sheet_inventory(sheet) for sheet in workbook.worksheets],
        "regions": {
            "event_matrix": event_matrix,
            "parameter_reference": parameter_reference,
            "data_layer_table": data_layer_table,
            "event_tabs": event_tabs,
        },
        "policy": {
            "allow_new_sheets": False,
            "preserve_unmapped_content": True,
        },
        "review_required": review,
    }


def main() -> int:
    args = parse_args()
    result = inspect(args.template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
