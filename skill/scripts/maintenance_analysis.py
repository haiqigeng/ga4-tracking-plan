from __future__ import annotations

from typing import Any


def _index(values: list[Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get(key)): item
        for item in values
        if isinstance(item, dict) and item.get(key)
    }


def _collection_changes(
    entity: str,
    key_field: str,
    before: list[Any],
    after: list[Any],
) -> list[dict[str, Any]]:
    previous = _index(before, key_field)
    current = _index(after, key_field)
    changes: list[dict[str, Any]] = []
    for key in sorted(current.keys() - previous.keys()):
        changes.append({"entity": entity, "action": "added", "key": key, "after": current[key]})
    for key in sorted(previous.keys() - current.keys()):
        changes.append({"entity": entity, "action": "removed", "key": key, "before": previous[key]})
    for key in sorted(previous.keys() & current.keys()):
        if previous[key] != current[key]:
            changes.append(
                {
                    "entity": entity,
                    "action": "changed",
                    "key": key,
                    "before": previous[key],
                    "after": current[key],
                }
            )
    return changes


def detect_context_drift(
    before: dict[str, Any],
    after: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for entity, key, field in (
        ("source", "source_id", "sources"),
        ("journey_coverage", "journey_id", "journey_coverage"),
        ("coverage_gap", "gap_id", "coverage_gaps"),
        ("value_domain", "domain_id", "value_domains"),
    ):
        changes.extend(
            _collection_changes(
                entity,
                key,
                before.get(field, []),
                after.get(field, []),
            )
        )
    for field in ("target_state", "scope_claim"):
        if before.get(field) != after.get(field):
            changes.append(
                {
                    "entity": "analysis_context",
                    "action": "changed",
                    "key": field,
                    "before": before.get(field),
                    "after": after.get(field),
                }
            )

    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    affected: set[str] = set()
    domains = _index(after.get("value_domains", []), "domain_id") | _index(
        before.get("value_domains", []), "domain_id"
    )
    for change in changes:
        if change["entity"] == "journey_coverage":
            journey_id = change["key"]
            affected.update(
                str(event.get("event_name"))
                for event in events
                if journey_id in event.get("journey_ids", [])
            )
        elif change["entity"] == "value_domain":
            domain = domains.get(str(change["key"]), {})
            selected_events = set(str(value) for value in domain.get("event_names", []))
            for event in events:
                if selected_events and str(event.get("event_name")) not in selected_events:
                    continue
                if any(
                    parameter.get("name") == domain.get("parameter_name")
                    and parameter.get("scope") == domain.get("scope")
                    for parameter in event.get("parameters", [])
                    if isinstance(parameter, dict)
                ):
                    affected.add(str(event.get("event_name")))
        elif change["entity"] in {"source", "coverage_gap", "analysis_context"}:
            affected.update(str(event.get("event_name")) for event in events)
    return {
        "report_version": "1.0.0",
        "status": "review_required" if changes else "unchanged",
        "changes": changes,
        "affected_events": sorted(affected),
        "notes": [
            "This report identifies potential semantic drift in evidence and coverage; it does not certify deployed tracking.",
            "No tracking-plan semantic is changed automatically. An analyst must confirm and approve any update.",
        ],
    }


def analyze_change_impact(
    plan: dict[str, Any],
    change_request: dict[str, Any],
    analysis_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    event_by_name = {str(event.get("event_name")): event for event in events}
    selectors = change_request.get("selectors", {})
    selected_events: set[str] = set()
    reasons: dict[str, set[str]] = {}
    affected_parameter_keys: set[tuple[str, str, str]] = set()
    unresolved: list[str] = []

    def select(event_name: str, reason: str) -> None:
        if event_name in event_by_name:
            selected_events.add(event_name)
            reasons.setdefault(event_name, set()).add(reason)
        else:
            unresolved.append(f"event:{event_name}")

    for event_name in selectors.get("event_names", []):
        select(str(event_name), "explicit event selector")
    for journey_id in selectors.get("journey_ids", []):
        matches = [
            str(event.get("event_name"))
            for event in events
            if journey_id in event.get("journey_ids", [])
        ]
        if not matches:
            unresolved.append(f"journey:{journey_id}")
        for event_name in matches:
            select(event_name, f"journey {journey_id}")
    for selector in selectors.get("parameters", []):
        name = str(selector.get("name", ""))
        scope = str(selector.get("scope", ""))
        restricted = set(str(value) for value in selector.get("event_names", []))
        matches = 0
        for event in events:
            event_name = str(event.get("event_name"))
            if restricted and event_name not in restricted:
                continue
            if any(
                parameter.get("name") == name and parameter.get("scope") == scope
                for parameter in event.get("parameters", [])
                if isinstance(parameter, dict)
            ):
                matches += 1
                select(event_name, f"parameter {name} ({scope})")
                affected_parameter_keys.add((event_name, name, scope))
        if not matches:
            unresolved.append(f"parameter:{name}|{scope}")

    domains = _index(
        (analysis_context or {}).get("value_domains", []),
        "domain_id",
    )
    for domain_id in selectors.get("value_domain_ids", []):
        domain = domains.get(str(domain_id))
        if domain is None:
            unresolved.append(f"value_domain:{domain_id}")
            continue
        selector = {
            "name": domain.get("parameter_name"),
            "scope": domain.get("scope"),
            "event_names": domain.get("event_names", []),
        }
        nested = analyze_change_impact(
            plan,
            {
                "change_id": change_request.get("change_id"),
                "description": change_request.get("description"),
                "change_type": "value_domain",
                "selectors": {"parameters": [selector]},
            },
            analysis_context,
        )
        for event in nested["affected_events"]:
            select(str(event["event_name"]), f"value domain {domain_id}")
        for parameter in nested["affected_parameters"]:
            affected_parameter_keys.add(
                (
                    str(parameter["event_name"]),
                    str(parameter["name"]),
                    str(parameter["scope"]),
                )
            )
        unresolved.extend(nested["unresolved_selectors"])

    if change_request.get("change_type") == "datalayer_convention":
        for event_name in event_by_name:
            select(event_name, "dataLayer convention change")

    affected_journeys = sorted(
        {
            str(journey_id)
            for event_name in selected_events
            for journey_id in event_by_name[event_name].get("journey_ids", [])
        }
    )
    affected_events = [
        {
            "event_name": event_name,
            "reasons": sorted(reasons.get(event_name, [])),
            "trigger": event_by_name[event_name].get("trigger"),
            "schema": f"schemas/{event_name}.schema.json",
        }
        for event_name in sorted(selected_events)
    ]
    if not affected_parameter_keys:
        affected_parameter_keys.update(
            (
                event_name,
                str(parameter.get("name")),
                str(parameter.get("scope")),
            )
            for event_name in selected_events
            for parameter in event_by_name[event_name].get("parameters", [])
            if isinstance(parameter, dict)
        )
    affected_parameters = [
        {"event_name": event_name, "name": name, "scope": scope}
        for event_name, name, scope in sorted(affected_parameter_keys)
    ]
    artifacts = ["plan.json", "tracking-plan.xlsx", "expected-events.json"]
    artifacts.extend(f"schemas/{event_name}.schema.json" for event_name in sorted(selected_events))
    return {
        "report_version": "1.0.0",
        "change_id": str(change_request.get("change_id", "")),
        "description": str(change_request.get("description", "")),
        "affected_journeys": affected_journeys,
        "affected_events": affected_events,
        "affected_parameters": affected_parameters,
        "artifacts_to_regenerate": sorted(dict.fromkeys(artifacts)),
        "recette_scenarios": [
            {
                "event_name": event_name,
                "trigger_to_retest": event_by_name[event_name].get("trigger"),
            }
            for event_name in sorted(selected_events)
        ],
        "unresolved_selectors": sorted(dict.fromkeys(unresolved)),
    }
