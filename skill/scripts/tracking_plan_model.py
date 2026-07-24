from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable

BASE_SHEETS = {
    "Guide",
    "Event Matrix",
    "Parameter Reference",
    "Change Log",
    "__EVENT_TEMPLATE",
    "__tracking_plan_model",
}


LABELS = {
    "en": {
        "guide": "Guide",
        "event_matrix": "Event Matrix",
        "parameter_reference": "Parameter Reference",
        "change_log": "Change Log",
        "title": "GA4 tracking plan",
        "document": "Document",
        "version": "Version",
        "date": "Date",
        "scope": "Scope",
        "target_state": "Target state",
        "language": "Language",
        "analyst_entry": "Analyst entry point",
        "developer_entry": "Developer entry point",
        "analyst_entry_value": "Review journeys and events in Event Matrix.",
        "developer_entry_value": "Open an event tab for the exact dataLayer specification.",
        "datalayer_convention": "dataLayer convention",
        "journeys": "Journeys",
        "journey": "Journey",
        "journey_id": "Journey ID",
        "status": "Status",
        "urls": "URLs / routes",
        "business_goal": "Business goal",
        "event": "Event",
        "classification": "Classification",
        "definition": "Definition",
        "trigger": "Trigger",
        "locations": "Pages / routes / components",
        "variables": "Event-specific variables",
        "variable": "Variable",
        "scope_label": "Scope",
        "type": "Type",
        "requirement": "Requirement",
        "condition": "Condition",
        "values": "Possible values / rule",
        "example": "Example",
        "concerned_events": "Concerned events",
        "source_path": "dataLayer path / source",
        "notes": "Notes",
        "datalayer": "dataLayer specification",
        "action": "Action",
        "entity": "Entity",
        "key": "Affected element",
        "summary": "Change",
        "before": "Before",
        "after": "After",
    },
    "fr": {
        "guide": "Guide",
        "event_matrix": "Event Matrix",
        "parameter_reference": "Valeurs des variables",
        "change_log": "Journal des modifications",
        "title": "Plan de marquage GA4",
        "document": "Document",
        "version": "Version",
        "date": "Date",
        "scope": "Périmètre",
        "target_state": "État cible",
        "language": "Langue",
        "analyst_entry": "Point d'entrée analyste",
        "developer_entry": "Point d'entrée développeur",
        "analyst_entry_value": "Vérifier les parcours et événements dans Event Matrix.",
        "developer_entry_value": "Ouvrir l'onglet d'un événement pour sa spécification dataLayer exacte.",
        "datalayer_convention": "Convention dataLayer",
        "journeys": "Parcours",
        "journey": "Parcours",
        "journey_id": "ID du parcours",
        "status": "Statut",
        "urls": "URLs / routes",
        "business_goal": "Objectif métier",
        "event": "Événement",
        "classification": "Classification",
        "definition": "Définition",
        "trigger": "Déclencheur",
        "locations": "Pages / routes / composants",
        "variables": "Variables propres à l'événement",
        "variable": "Variable",
        "scope_label": "Portée",
        "type": "Type",
        "requirement": "Exigence",
        "condition": "Condition",
        "values": "Valeurs possibles / règle",
        "example": "Exemple",
        "concerned_events": "Événements concernés",
        "source_path": "Chemin dataLayer / source",
        "notes": "Notes",
        "datalayer": "Spécification dataLayer",
        "action": "Action",
        "entity": "Élément",
        "key": "Élément concerné",
        "summary": "Modification",
        "before": "Avant",
        "after": "Après",
    },
}


CLASSIFICATION_LABELS = {
    "en": {
        "official": "official",
        "official_ecommerce": "official ecommerce",
        "custom": "custom",
        "context": "dataLayer context",
    },
    "fr": {
        "official": "officiel",
        "official_ecommerce": "ecommerce officiel",
        "custom": "personnalisé",
        "context": "contexte dataLayer",
    },
}


SCOPE_LABELS = {
    "en": {
        "event": "event",
        "item": "item",
        "user": "user",
        "implementation": "implementation",
    },
    "fr": {
        "event": "événement",
        "item": "article",
        "user": "utilisateur",
        "implementation": "implémentation",
    },
}


REQUIREMENT_LABELS = {
    "en": {
        "required": "mandatory",
        "conditional": "conditional",
        "optional": "optional",
    },
    "fr": {
        "required": "obligatoire",
        "conditional": "conditionnel",
        "optional": "facultatif",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def workbook_language(plan: dict[str, Any]) -> str:
    language = str(plan.get("document", {}).get("language", "en")).lower()
    return "fr" if language.startswith("fr") else "en"


def label(plan: dict[str, Any], key: str) -> str:
    language = workbook_language(plan)
    return LABELS.get(language, LABELS["en"]).get(key, LABELS["en"].get(key, key))


def classification_label(plan: dict[str, Any], value: str) -> str:
    language = workbook_language(plan)
    return CLASSIFICATION_LABELS.get(language, CLASSIFICATION_LABELS["en"]).get(value, value)


def scope_label(plan: dict[str, Any], value: str) -> str:
    language = workbook_language(plan)
    return SCOPE_LABELS.get(language, SCOPE_LABELS["en"]).get(value, value)


def requirement_label(plan: dict[str, Any], value: str) -> str:
    language = workbook_language(plan)
    return REQUIREMENT_LABELS.get(language, REQUIREMENT_LABELS["en"]).get(value, value)


def journey_lookup(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(journey.get("journey_id")): journey
        for journey in plan.get("journeys", [])
        if isinstance(journey, dict) and journey.get("journey_id")
    }


def event_journey_names(plan: dict[str, Any], event: dict[str, Any]) -> list[str]:
    journeys = journey_lookup(plan)
    return [
        str(journeys.get(str(journey_id), {}).get("name", journey_id))
        for journey_id in event.get("journey_ids", [])
    ]


def location_text(event: dict[str, Any]) -> str:
    lines: list[str] = []
    for location in event.get("locations", []):
        if not isinstance(location, dict):
            continue
        values = [
            str(location.get(key, "")).strip()
            for key in ("page_type", "url_pattern", "component", "state")
            if str(location.get(key, "")).strip()
        ]
        if values:
            lines.append(" | ".join(values))
    return "\n".join(lines)


def value_rule_text(
    parameter: dict[str, Any],
    plan: dict[str, Any] | None = None,
) -> str:
    values = parameter.get("allowed_values")
    rule = str(parameter.get("value_rule", "")).strip()
    if isinstance(values, list) and values:
        values_text = " | ".join(str(value) for value in values)
        prefix = (
            "Valeurs possibles"
            if plan is not None and workbook_language(plan) == "fr"
            else "Allowed values"
        )
        return f"{rule}\n{prefix}: {values_text}" if rule else f"{prefix}: {values_text}"
    return rule


def compact_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def datalayer_code(event: dict[str, Any]) -> str:
    data_layer = event.get("data_layer", {})
    lines = ["window.dataLayer = window.dataLayer || [];"]
    for key in data_layer.get("clear", []):
        lines.append(f'window.dataLayer.push({json.dumps({str(key): None}, ensure_ascii=False)});')
    push = data_layer.get("push", {})
    lines.append(
        "window.dataLayer.push("
        + json.dumps(push, ensure_ascii=False, indent=2)
        + ");"
    )
    return "\n".join(lines)


def flatten_push_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if path == "event":
                continue
            if isinstance(child, list):
                paths.add(path)
                for item in child:
                    if isinstance(item, dict):
                        paths.update(flatten_push_paths(item, f"{path}[]"))
            elif isinstance(child, dict):
                paths.update(flatten_push_paths(child, path))
            else:
                paths.add(path)
    return paths


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def path_exists(value: Any, path: str) -> bool:
    current: list[Any] = [value]
    for part in _path_parts(path):
        is_array = part.endswith("[]")
        key = part[:-2] if is_array else part
        next_values: list[Any] = []
        for candidate in current:
            if not isinstance(candidate, dict) or key not in candidate:
                continue
            child = candidate[key]
            if is_array:
                if isinstance(child, list) and child:
                    next_values.extend(child)
            else:
                next_values.append(child)
        if not next_values:
            return False
        current = next_values
    return True


def parameter_reference_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for event in plan.get("events", []):
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("event_name", ""))
        for parameter in event.get("parameters", []):
            if not isinstance(parameter, dict):
                continue
            key = (
                parameter.get("name"),
                parameter.get("scope"),
                parameter.get("type"),
                parameter.get("definition"),
                value_rule_text(parameter, plan),
                compact_value(parameter.get("example")),
            )
            if key not in grouped:
                grouped[key] = {
                    "name": parameter.get("name", ""),
                    "scope": parameter.get("scope", ""),
                    "type": parameter.get("type", ""),
                    "definition": parameter.get("definition", ""),
                    "example": compact_value(parameter.get("example")),
                    "values": value_rule_text(parameter, plan),
                    "events": [],
                }
            if event_name not in grouped[key]["events"]:
                grouped[key]["events"].append(event_name)
    return sorted(
        grouped.values(),
        key=lambda row: (str(row["name"]), str(row["scope"]), " | ".join(row["events"])),
    )


def safe_sheet_title(value: str, used: Iterable[str] = ()) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", "_", value).strip() or "event"
    cleaned = cleaned[:31]
    used_lower = {item.lower() for item in used}
    if cleaned.lower() not in used_lower:
        return cleaned
    index = 2
    while True:
        suffix = f"_{index}"
        candidate = f"{cleaned[:31-len(suffix)]}{suffix}"
        if candidate.lower() not in used_lower:
            return candidate
        index += 1


def slugify(value: str, fallback: str = "journey") -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"{fallback}_{normalized}".strip("_")
    return normalized[:80] or fallback


def deep_copy_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(plan)
