from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from inspect_tracking_plan_template import (
    compare_workbook_extension_fidelity,
    compare_workbook_fidelity,
    file_sha256,
    load_client_workbook,
    unsupported_strict_package_parts,
)
from openpyxl.cell.cell import MergedCell
from validate_tracking_plan import render_text, validate_plan_data

STRICT_TEMPLATE_MODE = "strict_client_template"
EXTENSION_TEMPLATE_MODE = "approved_structural_extension"
TEMPLATE_MODES = {STRICT_TEMPLATE_MODE, EXTENSION_TEMPLATE_MODE}
MAPPING_KEYS = {
    "mode",
    "mapping_id",
    "template_sha256",
    "cell_writes",
    "sheet_clones",
    "notes",
}
WRITE_KEYS = {
    "sheet",
    "cell",
    "value",
    "value_path",
    "transform",
    "allow_formula_overwrite",
    "purpose",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply an explicit cell-level GA4 tracking-plan mapping to a client workbook."
    )
    parser.add_argument("plan", type=Path, help="Validated tracking-plan JSON.")
    parser.add_argument("template", type=Path, help="Client XLSX template.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Adapted XLSX output.")
    parser.add_argument(
        "--mapping",
        type=Path,
        required=True,
        help="Structured strict or explicitly approved-extension mapping JSON.",
    )
    parser.add_argument(
        "--fidelity-report",
        type=Path,
        help="JSON fidelity report. Defaults beside the output workbook.",
    )
    return parser.parse_args()


def _validate_strict_write(write: Any, index: int) -> None:
    if not isinstance(write, dict):
        raise ValueError(f"cell_writes[{index}] must be an object.")
    unknown = set(write) - WRITE_KEYS
    if unknown:
        raise ValueError(f"cell_writes[{index}] has unsupported keys: {', '.join(sorted(unknown))}.")
    sheet = str(write.get("sheet", "")).strip()
    coordinate = str(write.get("cell", ""))
    if not sheet or not re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]*", coordinate):
        raise ValueError(f"cell_writes[{index}] needs a sheet and an uppercase A1 cell reference.")
    sources = [key for key in ("value", "value_path") if key in write]
    if len(sources) != 1:
        raise ValueError(f"cell_writes[{index}] needs exactly one of value or value_path.")


def _validate_sheet_clone(clone: Any, index: int) -> None:
    if not isinstance(clone, dict):
        raise ValueError(f"sheet_clones[{index}] must be an object.")
    required = {"source_sheet", "target_sheet", "approved_reason"}
    if set(clone) != required:
        raise ValueError(
            f"sheet_clones[{index}] must contain exactly: {', '.join(sorted(required))}."
        )
    source = str(clone.get("source_sheet", "")).strip()
    target = str(clone.get("target_sheet", "")).strip()
    reason = str(clone.get("approved_reason", "")).strip()
    if not source or not target or source == target:
        raise ValueError(f"sheet_clones[{index}] needs distinct source_sheet and target_sheet values.")
    if not reason:
        raise ValueError(f"sheet_clones[{index}].approved_reason cannot be empty.")


def validate_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    unknown = set(mapping) - MAPPING_KEYS
    if unknown:
        raise ValueError(f"Template mapping has unsupported keys: {', '.join(sorted(unknown))}.")
    mode = mapping.get("mode")
    if mode not in TEMPLATE_MODES:
        raise ValueError(
            "Template mappings must use mode='strict_client_template' or "
            "mode='approved_structural_extension'."
        )
    template_hash = str(mapping.get("template_sha256", ""))
    if not re.fullmatch(r"[a-f0-9]{64}", template_hash):
        raise ValueError("Template mappings need the lowercase SHA-256 from the template inventory.")
    writes = mapping.get("cell_writes")
    if not isinstance(writes, list) or not writes:
        raise ValueError("Client-template mappings need a non-empty cell_writes list.")
    targets: set[tuple[str, str]] = set()
    for index, write in enumerate(writes):
        _validate_strict_write(write, index)
        target = (str(write["sheet"]), str(write["cell"]))
        if target in targets:
            raise ValueError(f"Duplicate cell-write target: {target[0]}!{target[1]}.")
        targets.add(target)

    clones = mapping.get("sheet_clones", [])
    if mode == STRICT_TEMPLATE_MODE and clones:
        raise ValueError("Strict client-template mappings cannot add or clone sheets.")
    if mode == EXTENSION_TEMPLATE_MODE and (not isinstance(clones, list) or not clones):
        raise ValueError("Approved structural extension mappings need at least one sheet_clones entry.")
    clone_targets: set[str] = set()
    for index, clone in enumerate(clones):
        _validate_sheet_clone(clone, index)
        target = str(clone["target_sheet"])
        if target in clone_targets:
            raise ValueError(f"Duplicate approved clone target: {target}.")
        clone_targets.add(target)
    return mapping


def load_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        raise ValueError("Client-template adaptation requires an explicit mapping JSON.")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Template mapping must be a JSON object.")
    return validate_mapping(value)


def is_strict_mapping(mapping: dict[str, Any]) -> bool:
    return mapping.get("mode") == STRICT_TEMPLATE_MODE


def _value_at_path(value: Any, path: str) -> Any:
    if path == "$":
        return value
    if not path.startswith("$."):
        raise ValueError(f"Unsupported value_path '{path}'.")
    current = value
    for part in path[2:].split("."):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[([0-9]+)\])?", part)
        if not match:
            raise ValueError(f"Unsupported value_path segment '{part}' in '{path}'.")
        key, index = match.groups()
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"value_path '{path}' does not resolve at '{key}'.")
        current = current[key]
        if index is not None:
            if not isinstance(current, list) or int(index) >= len(current):
                raise ValueError(f"value_path '{path}' does not resolve index {index}.")
            current = current[int(index)]
    return current


def _cell_value(value: Any, transform: str | None) -> Any:
    if transform == "join_pipe":
        if not isinstance(value, list):
            raise ValueError("join_pipe transform requires a list value.")
        return " | ".join(str(item) for item in value)
    if transform == "json":
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if transform not in {None, "string"}:
        raise ValueError(f"Unknown mapping transform '{transform}'.")
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if transform == "string" and value is not None:
        return str(value)
    return value


def allowed_cells(mapping: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for write in mapping["cell_writes"]:
        result.setdefault(str(write["sheet"]), set()).add(str(write["cell"]))
    return result


def _clone_approved_sheets(client: Any, mapping: dict[str, Any]) -> None:
    for index, clone in enumerate(mapping.get("sheet_clones", [])):
        source_name = str(clone["source_sheet"])
        target_name = str(clone["target_sheet"])
        if source_name not in client.sheetnames:
            raise ValueError(f"sheet_clones[{index}] targets missing source sheet '{source_name}'.")
        if target_name in client.sheetnames:
            raise ValueError(f"sheet_clones[{index}] target sheet '{target_name}' already exists.")
        source = client[source_name]
        target = client.copy_worksheet(source)
        target.title = target_name
        for image in source._images:
            target.add_image(copy.copy(image), copy.copy(image.anchor))


def _apply_cell_writes(client: Any, plan: dict[str, Any], mapping: dict[str, Any]) -> None:
    for index, write in enumerate(mapping["cell_writes"]):
        sheet_name = str(write["sheet"])
        coordinate = str(write["cell"])
        if sheet_name not in client.sheetnames:
            raise ValueError(f"cell_writes[{index}] targets missing sheet '{sheet_name}'.")
        target = client[sheet_name][coordinate]
        if isinstance(target, MergedCell):
            raise ValueError(f"cell_writes[{index}] targets non-anchor merged cell {sheet_name}!{coordinate}.")
        if isinstance(target.value, str) and target.value.startswith("=") and not write.get("allow_formula_overwrite"):
            raise ValueError(
                f"cell_writes[{index}] would replace formula {sheet_name}!{coordinate}. "
                "Approve that exact write with allow_formula_overwrite=true or choose a content cell."
            )
        source_value = write.get("value") if "value" in write else _value_at_path(plan, str(write["value_path"]))
        target.value = _cell_value(source_value, write.get("transform"))


def adapt_workbook(plan: dict[str, Any], template: Path, mapping: dict[str, Any]):
    validate_mapping(mapping)
    actual_hash = file_sha256(template)
    if actual_hash != mapping["template_sha256"]:
        raise ValueError(
            "The mapping was prepared for a different template file: "
            f"expected {mapping['template_sha256']}, received {actual_hash}."
        )
    unsupported = unsupported_strict_package_parts(template)
    if unsupported:
        raise ValueError(
            "Client-template adaptation is blocked because the approved openpyxl backend cannot preserve: "
            f"{', '.join(unsupported)}. Return the template inventory and request a simplified workbook "
            "without those features. No automatic fallback backend is defined."
        )
    client = load_client_workbook(template)
    if mapping["mode"] == EXTENSION_TEMPLATE_MODE:
        _clone_approved_sheets(client, mapping)
    _apply_cell_writes(client, plan, mapping)
    return client


def mapping_sha256(mapping: dict[str, Any]) -> str:
    payload = json.dumps(mapping, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_fidelity_report(
    template: Path,
    output: Path,
    mapping: dict[str, Any],
    mapping_path: Path,
) -> dict[str, Any]:
    cells = allowed_cells(mapping)
    if is_strict_mapping(mapping):
        report = compare_workbook_fidelity(template, output, cells)
    else:
        report = compare_workbook_extension_fidelity(
            template,
            output,
            cells,
            mapping["sheet_clones"],
        )
    report.update(
        {
            "mapping_mode": mapping["mode"],
            "mapping_id": str(mapping.get("mapping_id", "")),
            "mapping_file": mapping_path.name,
            "mapping_sha256": mapping_sha256(mapping),
        }
    )
    return report


def main() -> int:
    args = parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    mapping = load_mapping(args.mapping)
    issues = validate_plan_data(plan)
    if issues:
        print(render_text(issues), file=sys.stderr)
    if any(issue.severity == "error" for issue in issues):
        return 1

    workbook = adapt_workbook(plan, args.template, mapping)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fidelity_path = args.fidelity_report or args.output.with_name(
        f"{args.output.stem}.fidelity.json"
    )
    with TemporaryDirectory(prefix="tracking_plan_adapted_", dir=args.output.parent) as raw:
        candidate = Path(raw) / args.output.name
        workbook.save(candidate)
        report = build_fidelity_report(args.template, candidate, mapping, args.mapping)
        fidelity_path.parent.mkdir(parents=True, exist_ok=True)
        fidelity_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if report["status"] != "passed":
            print("Client-template fidelity validation failed:", file=sys.stderr)
            for difference in report["unexpected_differences"]:
                print(f"- {difference}", file=sys.stderr)
            return 1
        candidate.replace(args.output)
    print(args.output)
    print(fidelity_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
