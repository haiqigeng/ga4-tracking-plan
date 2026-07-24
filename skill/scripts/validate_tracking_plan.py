from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from tracking_plan_model import (
    flatten_push_paths,
    journey_lookup,
    load_json,
    path_exists,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "references" / "schema-tracking-plan.json"
CATALOG_PATH = ROOT / "references" / "library-ga4-recommended-events.json"

GENERIC_TEXT = re.compile(
    r"(?:use|utiliser)\s+(?:the|la)\s+(?:official|officielle?)\s+definition|"
    r"value associated with|valeur associ[eé]e|"
    r"variable (?:used|utilis[eé]e) (?:for|pour) (?:the )?track|"
    r"when applicable|lorsque applicable|"
    r"to confirm|[àa] confirmer|"
    r"^tbd$",
    re.I,
)

GENERIC_TRIGGER = re.compile(
    r"^(?:on click|au clic|on page view|[àa] la vue|when the event occurs|"
    r"lorsque l['’]événement se produit|when applicable|lorsque applicable)$",
    re.I,
)


@dataclass
class Issue:
    severity: str
    code: str
    path: str
    message: str


def issue(issues: list[Issue], severity: str, code: str, path: str, message: str) -> None:
    issues.append(Issue(severity, code, path, message))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the lean human-first GA4 tracking-plan model.")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--warnings-as-errors", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def load_catalog() -> dict[str, dict[str, Any]]:
    records = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    return {
        str(record.get("event")): record
        for record in records
        if isinstance(record, dict) and record.get("event")
    }


def normalize(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def normalize_type(value: Any) -> str:
    text = normalize(value)
    if text.startswith("array"):
        return "array"
    if text in {"float", "double"}:
        return "number"
    return text


def validate_schema(plan: dict[str, Any], schema_path: Path, issues: list[Issue]) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.absolute_path)):
        path = "$" + "".join(f"[{part!r}]" if isinstance(part, str) else f"[{part}]" for part in error.absolute_path)
        issue(issues, "error", "SCHEMA", path, error.message)


def check_unique_ids(plan: dict[str, Any], issues: list[Issue]) -> None:
    journey_ids = [str(item.get("journey_id", "")) for item in plan.get("journeys", []) if isinstance(item, dict)]
    if len(journey_ids) != len(set(journey_ids)):
        issue(issues, "error", "DUPLICATE_JOURNEY", "$.journeys", "Journey IDs must be unique.")
    event_names = [str(item.get("event_name", "")) for item in plan.get("events", []) if isinstance(item, dict)]
    if len(event_names) != len(set(event_names)):
        issue(issues, "error", "DUPLICATE_EVENT", "$.events", "Event names must be unique.")


def check_human_text(value: Any, path: str, label: str, issues: list[Issue]) -> None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        issue(issues, "error", f"{label}_MISSING", path, f"{label.replace('_', ' ').title()} is required.")
    elif GENERIC_TEXT.search(text):
        issue(issues, "error", f"{label}_GENERIC", path, "Replace generic filler with concrete official or official-like wording.")


def check_custom_decision(
    value: Any,
    path: str,
    issues: list[Issue],
) -> None:
    if not isinstance(value, dict):
        return
    for field in ("business_need", "official_candidate", "why_not_fit"):
        check_human_text(
            value.get(field),
            f"{path}.{field}",
            f"custom_{field}",
            issues,
        )


def catalog_parameters(record: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(parameter.get("name")), str(parameter.get("scope", "event"))): parameter
        for parameter in record.get("parameters", [])
        if isinstance(parameter, dict) and parameter.get("name")
    }


def check_official_event(
    plan: dict[str, Any],
    event: dict[str, Any],
    event_index: int,
    catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    base = f"$.events[{event_index}]"
    record = catalog.get(name)
    if classification == "custom" and record:
        issue(
            issues,
            "error",
            "CUSTOM_EVENT_IS_OFFICIAL",
            f"{base}.classification",
            f"'{name}' exists in the official recommended-event catalog; classify and assess it as official first.",
        )
    if classification not in {"official", "official_ecommerce"}:
        return
    source = event.get("official_source", {})
    if "google.com" not in str(source.get("url", "")).lower():
        issue(issues, "error", "OFFICIAL_EVENT_SOURCE", f"{base}.official_source.url", "Use a current official Google source.")
    if not record:
        issue(
            issues,
            "warning",
            "OFFICIAL_EVENT_NOT_IN_LOCAL_CATALOG",
            f"{base}.event_name",
            "The event is not in the bundled recommended-event catalog; verify the supplied official source live.",
        )
        return
    if source.get("wording_origin") == "exact" and normalize(event.get("definition")) != normalize(record.get("description")):
        issue(
            issues,
            "error",
            "OFFICIAL_EVENT_WORDING",
            f"{base}.definition",
            "Exact official wording must match the selected event's current official definition.",
        )
    selected = {(str(item.get("name")), str(item.get("scope", "event"))) for item in event.get("parameters", []) if isinstance(item, dict)}
    prescribed = catalog_parameters(record)
    for key, parameter in prescribed.items():
        required = normalize(parameter.get("required"))
        if required == "yes" and key not in selected:
            issue(
                issues,
                "error",
                "OFFICIAL_REQUIRED_PARAMETER_MISSING",
                f"{base}.parameters",
                f"Required official parameter '{key[0]}' ({key[1]} scope) is missing.",
            )
    selected_names = {name for name, _scope in selected}
    if "value" in selected_names and ("currency", "event") in prescribed and ("currency", "event") not in selected:
        issue(issues, "error", "CURRENCY_REQUIRED_WITH_VALUE", f"{base}.parameters", "Include event-level currency when value is sent.")
    if ("items", "event") in selected:
        item_names = {name for name, scope in selected if scope == "item"}
        if not {"item_id", "item_name"}.intersection(item_names):
            issue(issues, "error", "ITEM_IDENTITY_MISSING", f"{base}.parameters", "Items require item_id or item_name at item scope.")


def check_parameter(
    event: dict[str, Any],
    event_index: int,
    parameter: dict[str, Any],
    parameter_index: int,
    catalog_record: dict[str, Any] | None,
    issues: list[Issue],
) -> None:
    base = f"$.events[{event_index}].parameters[{parameter_index}]"
    name = str(parameter.get("name", ""))
    scope = str(parameter.get("scope", "event"))
    classification = str(parameter.get("classification", ""))
    path = str(parameter.get("data_layer_path", ""))
    final_key = path.rsplit(".", 1)[-1].replace("[]", "")
    if name and final_key and name != final_key:
        issue(
            issues,
            "error",
            "PARAMETER_PATH_NAME_MISMATCH",
            f"{base}.data_layer_path",
            f"The final dataLayer key '{final_key}' must match parameter name '{name}'.",
        )
    check_human_text(parameter.get("definition"), f"{base}.definition", "parameter_definition", issues)
    check_human_text(parameter.get("value_rule"), f"{base}.value_rule", "value_rule", issues)
    if parameter.get("requirement") == "conditional" and not str(parameter.get("condition", "")).strip():
        issue(issues, "error", "CONDITION_MISSING", f"{base}.condition", "A conditional parameter needs a separate concrete condition.")
    allowed = parameter.get("allowed_values")
    example = parameter.get("example")
    if isinstance(allowed, list) and allowed and not isinstance(example, (dict, list)) and example not in allowed:
        issue(issues, "error", "EXAMPLE_OUTSIDE_ALLOWED_VALUES", f"{base}.example", "The example must belong to the exhaustive allowed values.")
    if not path_exists(event.get("data_layer", {}).get("push", {}), path):
        issue(
            issues,
            "error",
            "PARAMETER_NOT_IN_DATALAYER",
            f"{base}.data_layer_path",
            "Every selected parameter must appear in the event's complete dataLayer example.",
        )
    prescribed = catalog_parameters(catalog_record) if catalog_record else {}
    official = prescribed.get((name, scope))
    if classification == "official":
        if catalog_record and not official:
            issue(
                issues,
                "error",
                "OFFICIAL_PARAMETER_NOT_PRESCRIBED",
                f"{base}.classification",
                f"'{name}' is not an official {scope}-scope parameter for this selected event; classify it as custom if justified.",
            )
        if official:
            if normalize_type(parameter.get("type")) != normalize_type(official.get("type")):
                issue(
                    issues,
                    "error",
                    "OFFICIAL_PARAMETER_TYPE",
                    f"{base}.type",
                    f"Use official type '{official.get('type')}'.",
                )
            source = parameter.get("official_source", {})
            if source.get("wording_origin") == "exact" and normalize(parameter.get("definition")) != normalize(official.get("description")):
                issue(
                    issues,
                    "error",
                    "OFFICIAL_PARAMETER_WORDING",
                    f"{base}.definition",
                    "Exact official wording must match the selected event's current parameter-row definition.",
                )
    elif classification == "custom" and official:
        issue(
            issues,
            "error",
            "CUSTOM_PARAMETER_IS_OFFICIAL",
            f"{base}.classification",
            f"'{name}' is already an official {scope}-scope parameter for this event.",
        )
    if classification == "custom":
        check_custom_decision(parameter.get("custom_decision"), f"{base}.custom_decision", issues)
    if classification == "implementation" and parameter.get("destination") != "implementation_only":
        issue(
            issues,
            "error",
            "IMPLEMENTATION_DESTINATION",
            f"{base}.destination",
            "An implementation parameter must remain implementation_only.",
        )


def check_event(
    plan: dict[str, Any],
    event: dict[str, Any],
    index: int,
    catalog: dict[str, dict[str, Any]],
    issues: list[Issue],
) -> None:
    base = f"$.events[{index}]"
    name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    if classification in {"automatic", "enhanced_measurement"}:
        issue(issues, "error", "NON_MANUAL_CLASSIFICATION", f"{base}.classification", "The tracking plan contains manually implemented measurement only.")
    if classification == "custom":
        check_custom_decision(event.get("custom_decision"), f"{base}.custom_decision", issues)
    check_human_text(event.get("definition"), f"{base}.definition", "event_definition", issues)
    trigger = " ".join(str(event.get("trigger", "")).split()).strip()
    check_human_text(trigger, f"{base}.trigger", "trigger", issues)
    if GENERIC_TRIGGER.fullmatch(trigger):
        issue(issues, "error", "TRIGGER_GENERIC", f"{base}.trigger", "State the concrete action or state and firing moment.")
    known_journeys = journey_lookup(plan)
    for journey_id in event.get("journey_ids", []):
        if str(journey_id) not in known_journeys:
            issue(issues, "error", "UNKNOWN_JOURNEY", f"{base}.journey_ids", f"Unknown journey '{journey_id}'.")
    push = event.get("data_layer", {}).get("push", {})
    if classification == "context":
        if "event" in push:
            issue(issues, "error", "CONTEXT_HAS_EVENT", f"{base}.data_layer.push.event", "A context push must not create a GTM Custom Event trigger.")
    elif push.get("event") != name:
        issue(
            issues,
            "error",
            "EVENT_PUSH_MISMATCH",
            f"{base}.data_layer.push.event",
            f'Top-level "event" must equal "{name}".',
        )
    paths = [str(item.get("data_layer_path", "")) for item in event.get("parameters", []) if isinstance(item, dict)]
    if len(paths) != len(set(paths)):
        issue(issues, "error", "DUPLICATE_PARAMETER_PATH", f"{base}.parameters", "Parameter dataLayer paths must be unique inside an event.")
    bound_paths = set(paths)
    unbound = sorted(flatten_push_paths(push) - bound_paths)
    if unbound:
        issue(
            issues,
            "error",
            "UNBOUND_DATALAYER_FIELDS",
            f"{base}.data_layer.push",
            "Every pushed field must belong to this event specification. Missing bindings: " + ", ".join(unbound),
        )
    check_official_event(plan, event, index, catalog, issues)
    record = catalog.get(name)
    for parameter_index, parameter in enumerate(event.get("parameters", [])):
        if isinstance(parameter, dict):
            check_parameter(event, index, parameter, parameter_index, record, issues)


def validate_plan(plan: dict[str, Any], schema_path: Path = DEFAULT_SCHEMA) -> list[Issue]:
    issues: list[Issue] = []
    validate_schema(plan, schema_path, issues)
    if any(item.code == "SCHEMA" for item in issues):
        return issues
    check_unique_ids(plan, issues)
    catalog = load_catalog()
    for index, event in enumerate(plan.get("events", [])):
        if isinstance(event, dict):
            check_event(plan, event, index, catalog, issues)
    return issues


def render_text(issues: list[Issue]) -> str:
    return "\n".join(f"{item.severity.upper()} {item.code} {item.path}: {item.message}" for item in issues)


def main() -> int:
    args = parse_args()
    try:
        plan = load_json(args.plan)
        issues = validate_plan(plan, args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(item) for item in issues], indent=2, ensure_ascii=False))
    elif issues:
        print(render_text(issues))
    else:
        print("Tracking plan is valid.")
    has_error = any(item.severity == "error" for item in issues)
    has_warning = any(item.severity == "warning" for item in issues)
    return int(has_error or (args.warnings_as_errors and has_warning))


if __name__ == "__main__":
    raise SystemExit(main())
