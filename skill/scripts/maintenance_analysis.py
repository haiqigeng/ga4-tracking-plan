from __future__ import annotations

import re
import unicodedata
from typing import Any


def _index(values: list[Any], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): item for item in values if isinstance(item, dict) and item.get(key)}


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
    before_discovery: dict[str, Any] | None = None,
    after_discovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for entity, key, field in (
        ("source", "source_id", "sources"),
        ("journey_coverage", "journey_id", "journey_coverage"),
        ("coverage_gap", "gap_id", "coverage_gaps"),
        ("measurement_opportunity", "opportunity_id", "measurement_opportunities"),
        ("discovery_report", "report_id", "discovery_reports"),
        ("value_domain", "domain_id", "value_domains"),
    ):
        changes.extend(_collection_changes(entity, key, before.get(field, []), after.get(field, [])))
    for field in ("target_state", "scope_claim", "language_decision"):
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

    discovery_changes: list[dict[str, Any]] = []
    if before_discovery is not None or after_discovery is not None:
        previous = before_discovery or {}
        current = after_discovery or {}
        for entity, key, field in (
            ("rendered_page", "url", "pages_sampled"),
            ("discovery_hint", "hint_id", "measurement_opportunity_hints"),
            ("discovered_journey", "journey_id", "journey_coverage_ledger"),
            ("automatic_interaction", "recipe_id", "automatic_interaction_runs"),
        ):
            discovery_changes.extend(_collection_changes(entity, key, previous.get(field, []), current.get(field, [])))
        for field in ("language_summary", "coverage_gaps", "outcome"):
            if previous.get(field) != current.get(field):
                discovery_changes.append(
                    {
                        "entity": "discovery_report",
                        "action": "changed",
                        "key": field,
                        "before": previous.get(field),
                        "after": current.get(field),
                    }
                )
        changes.extend(discovery_changes)

    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    affected_events: set[str] = set()
    affected_journeys: set[str] = set()
    affected_opportunities: set[str] = set()
    domains = _index(after.get("value_domains", []), "domain_id") | _index(before.get("value_domains", []), "domain_id")
    opportunities = _index(before.get("measurement_opportunities", []), "opportunity_id") | _index(after.get("measurement_opportunities", []), "opportunity_id")

    def affect_journey(journey_id: str) -> None:
        if not journey_id:
            return
        affected_journeys.add(journey_id)
        affected_events.update(str(event.get("event_name")) for event in events if journey_id in event.get("journey_ids", []))

    def affect_opportunity(opportunity_id: str) -> None:
        if not opportunity_id:
            return
        affected_opportunities.add(opportunity_id)
        opportunity = opportunities.get(opportunity_id, {})
        affect_journey(str(opportunity.get("journey_id", "")))
        affected_events.update(str(value) for value in opportunity.get("event_names", []))
        for event in events:
            if opportunity_id in event.get("measurement_opportunity_ids", []):
                affected_events.add(str(event.get("event_name")))

    for change in changes:
        entity = str(change["entity"])
        key = str(change["key"])
        if entity in {"journey_coverage", "discovered_journey"}:
            affect_journey(key)
        elif entity == "measurement_opportunity":
            affect_opportunity(key)
        elif entity == "discovery_hint":
            for opportunity_id, opportunity in opportunities.items():
                if key in opportunity.get("discovery_hint_ids", []):
                    affect_opportunity(opportunity_id)
        elif entity == "automatic_interaction":
            record = change.get("after") or change.get("before") or {}
            affect_journey(str(record.get("journey_id", "")))
        elif entity == "rendered_page":
            record = change.get("after") or change.get("before") or {}
            url = str(record.get("url", ""))
            for event in events:
                for location in event.get("locations", []):
                    if not isinstance(location, dict):
                        continue
                    pattern = str(location.get("url_pattern", ""))
                    if url and pattern and (url == pattern or pattern in url or url in pattern):
                        affected_events.add(str(event.get("event_name")))
                        for journey_id in event.get("journey_ids", []):
                            affected_journeys.add(str(journey_id))
        elif entity == "value_domain":
            domain = domains.get(key, {})
            selected = {str(value) for value in domain.get("event_names", [])}
            for event in events:
                event_name = str(event.get("event_name"))
                if selected and event_name not in selected:
                    continue
                if any(
                    parameter.get("name") == domain.get("parameter_name") and parameter.get("scope") == domain.get("scope")
                    for parameter in event.get("parameters", [])
                    if isinstance(parameter, dict)
                ):
                    affected_events.add(event_name)
                    affected_journeys.update(str(value) for value in event.get("journey_ids", []))
        elif entity in {
            "source",
            "coverage_gap",
            "analysis_context",
            "discovery_report",
        }:
            affected_events.update(str(event.get("event_name")) for event in events)
            affected_journeys.update(str(value) for event in events for value in event.get("journey_ids", []))

    return {
        "report_version": "2.0.0",
        "status": "review_required" if changes else "unchanged",
        "changes": changes,
        "discovery_changes": discovery_changes,
        "affected_journeys": sorted(affected_journeys),
        "affected_opportunities": sorted(affected_opportunities),
        "affected_events": sorted(affected_events),
        "notes": [
            "This report compares evidence, opportunity decisions, controlled domains, rendered structures, forms, controls, and safe interaction outcomes.",
            "No tracking-plan semantic is changed automatically. An analyst must confirm and approve any update.",
        ],
    }


STOPWORDS = {
    "a",
    "add",
    "ajouter",
    "an",
    "and",
    "change",
    "changer",
    "de",
    "des",
    "du",
    "for",
    "in",
    "la",
    "le",
    "les",
    "new",
    "nouveau",
    "of",
    "on",
    "pour",
    "support",
    "the",
    "to",
    "un",
    "une",
    "with",
}
SEMANTIC_ALIASES = {
    "payment": {"payment", "paiement", "paypal", "card", "carte", "wallet"},
    "shipping": {"shipping", "livraison", "delivery", "transport", "carrier"},
    "promotion": {"promotion", "promo", "discount", "remise", "coupon"},
    "quote": {"quote", "devis", "estimate", "project", "projet"},
    "catalogue": {"catalogue", "catalog", "brochure"},
    "authentication": {"login", "connexion", "account", "compte", "auth"},
    "search": {"search", "recherche", "query", "requete"},
    "product": {"product", "produit", "item", "article", "sku"},
    "cart": {"cart", "panier", "basket"},
    "checkout": {"checkout", "commande", "purchase", "achat"},
    "lead": {"lead", "contact", "form", "formulaire", "request", "demande"},
}


def _semantic_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    return {token for token in re.findall(r"[a-z0-9]+", ascii_value) if len(token) > 1 and token not in STOPWORDS}


def _expanded_tokens(value: str) -> set[str]:
    tokens = _semantic_tokens(value)
    expanded = set(tokens)
    for canonical, aliases in SEMANTIC_ALIASES.items():
        if tokens & aliases:
            expanded.add(canonical)
            expanded.update(aliases)
    return expanded


def _entity_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_entity_text(child)}" for key, child in value.items())
    if isinstance(value, list):
        return " ".join(_entity_text(child) for child in value)
    return str(value)


def analyze_change_impact(
    plan: dict[str, Any],
    change_request: dict[str, Any],
    analysis_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = analysis_context or {}
    events = [event for event in plan.get("events", []) if isinstance(event, dict)]
    event_by_name = {str(event.get("event_name")): event for event in events}
    journeys = _index(plan.get("journeys", []), "journey_id")
    opportunities = _index(context.get("measurement_opportunities", []), "opportunity_id")
    domains = _index(context.get("value_domains", []), "domain_id")
    selectors = change_request.get("selectors", {})
    selected_events: set[str] = set()
    selected_opportunities: set[str] = set()
    reasons: dict[str, set[str]] = {}
    affected_parameter_keys: set[tuple[str, str, str]] = set()
    unresolved: list[str] = []
    inference_matches: list[dict[str, Any]] = []

    def select_event(event_name: str, reason: str) -> None:
        if event_name in event_by_name:
            selected_events.add(event_name)
            reasons.setdefault(event_name, set()).add(reason)
        else:
            unresolved.append(f"event:{event_name}")

    def select_opportunity(opportunity_id: str, reason: str) -> None:
        opportunity = opportunities.get(opportunity_id)
        if opportunity is None:
            unresolved.append(f"opportunity:{opportunity_id}")
            return
        selected_opportunities.add(opportunity_id)
        for event_name in opportunity.get("event_names", []):
            select_event(str(event_name), reason)

    explicit_count = sum(
        len(selectors.get(field, []))
        for field in (
            "event_names",
            "journey_ids",
            "opportunity_ids",
            "parameters",
            "value_domain_ids",
        )
    )
    for event_name in selectors.get("event_names", []):
        select_event(str(event_name), "explicit event selector")
    for opportunity_id in selectors.get("opportunity_ids", []):
        select_opportunity(str(opportunity_id), "explicit opportunity selector")
    for journey_id in selectors.get("journey_ids", []):
        matches = [str(event.get("event_name")) for event in events if journey_id in event.get("journey_ids", [])]
        if not matches:
            unresolved.append(f"journey:{journey_id}")
        for event_name in matches:
            select_event(event_name, f"journey {journey_id}")
        for opportunity_id, opportunity in opportunities.items():
            if opportunity.get("journey_id") == journey_id:
                selected_opportunities.add(opportunity_id)
    for selector in selectors.get("parameters", []):
        name = str(selector.get("name", ""))
        scope = str(selector.get("scope", ""))
        restricted = {str(value) for value in selector.get("event_names", [])}
        matches = 0
        for event in events:
            event_name = str(event.get("event_name"))
            if restricted and event_name not in restricted:
                continue
            if any(
                parameter.get("name") == name and parameter.get("scope") == scope for parameter in event.get("parameters", []) if isinstance(parameter, dict)
            ):
                matches += 1
                select_event(event_name, f"parameter {name} ({scope})")
                affected_parameter_keys.add((event_name, name, scope))
        if not matches:
            unresolved.append(f"parameter:{name}|{scope}")
    for domain_id in selectors.get("value_domain_ids", []):
        domain = domains.get(str(domain_id))
        if domain is None:
            unresolved.append(f"value_domain:{domain_id}")
            continue
        restricted = {str(value) for value in domain.get("event_names", [])}
        matched = False
        for event in events:
            event_name = str(event.get("event_name"))
            if restricted and event_name not in restricted:
                continue
            for parameter in event.get("parameters", []):
                if not isinstance(parameter, dict):
                    continue
                if parameter.get("name") == domain.get("parameter_name") and parameter.get("scope") == domain.get("scope"):
                    matched = True
                    select_event(event_name, f"value domain {domain_id}")
                    affected_parameter_keys.add(
                        (
                            event_name,
                            str(parameter.get("name")),
                            str(parameter.get("scope")),
                        )
                    )
        if not matched:
            unresolved.append(f"value_domain:{domain_id}")

    inference_used = explicit_count == 0
    query_tokens = _expanded_tokens(str(change_request.get("description", "")))
    if inference_used:
        candidates: list[tuple[int, str, str, set[str]]] = []
        for key, value in opportunities.items():
            matched = query_tokens & _expanded_tokens(_entity_text(value))
            if matched:
                candidates.append((len(matched), "opportunity", key, matched))
        for key, value in domains.items():
            matched = query_tokens & _expanded_tokens(_entity_text(value))
            if matched:
                candidates.append((len(matched), "value_domain", key, matched))
        for key, value in journeys.items():
            matched = query_tokens & _expanded_tokens(_entity_text(value))
            if matched:
                candidates.append((len(matched), "journey", key, matched))
        for key, value in event_by_name.items():
            matched = query_tokens & _expanded_tokens(_entity_text(value))
            if matched:
                candidates.append((len(matched), "event", key, matched))
        best = max((score for score, _entity, _key, _matched in candidates), default=0)
        retained = [item for item in candidates if item[0] >= max(1, best - 1)]
        for score, entity, key, matched in retained:
            inference_matches.append(
                {
                    "entity": entity,
                    "key": key,
                    "score": score,
                    "matched_terms": sorted(matched),
                }
            )
            reason = "description inference: " + ", ".join(sorted(matched))
            if entity == "event":
                select_event(key, reason)
            elif entity == "journey":
                for event in events:
                    if key in event.get("journey_ids", []):
                        select_event(str(event.get("event_name")), reason)
            elif entity == "opportunity":
                select_opportunity(key, reason)
            elif entity == "value_domain":
                domain = domains[key]
                for event in events:
                    event_name = str(event.get("event_name"))
                    if domain.get("event_names") and event_name not in domain.get("event_names", []):
                        continue
                    for parameter in event.get("parameters", []):
                        if not isinstance(parameter, dict):
                            continue
                        if parameter.get("name") == domain.get("parameter_name") and parameter.get("scope") == domain.get("scope"):
                            select_event(event_name, reason)
                            affected_parameter_keys.add(
                                (
                                    event_name,
                                    str(parameter.get("name")),
                                    str(parameter.get("scope")),
                                )
                            )
        if not selected_events and not selected_opportunities:
            unresolved.append("description:no_semantic_match")

    if change_request.get("change_type") == "datalayer_convention":
        for event_name in event_by_name:
            select_event(event_name, "dataLayer convention change")

    affected_journeys = sorted(
        {str(journey_id) for event_name in selected_events for journey_id in event_by_name[event_name].get("journey_ids", [])}
        | {str(opportunities[item].get("journey_id")) for item in selected_opportunities if opportunities[item].get("journey_id")}
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
    affected_parameters = [{"event_name": event_name, "name": name, "scope": scope} for event_name, name, scope in sorted(affected_parameter_keys)]
    artifacts = ["plan.json", "tracking-plan.xlsx", "expected-events.json", "handoff.json"]
    artifacts.extend(f"schemas/{event_name}.schema.json" for event_name in sorted(selected_events))
    best_score = max((item["score"] for item in inference_matches), default=0)
    confidence = "high" if best_score >= 3 else "medium" if best_score >= 2 else "low"
    return {
        "report_version": "2.0.0",
        "change_id": str(change_request.get("change_id", "")),
        "description": str(change_request.get("description", "")),
        "inference": {
            "used": inference_used,
            "description_tokens": sorted(query_tokens),
            "confidence": confidence if inference_used and inference_matches else "none",
            "matches": inference_matches,
        },
        "affected_journeys": affected_journeys,
        "affected_opportunities": sorted(selected_opportunities),
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
