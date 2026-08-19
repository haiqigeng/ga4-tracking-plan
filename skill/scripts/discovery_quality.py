from __future__ import annotations

import hashlib
import json
import re
from typing import Any

FORM_PURPOSE_TERMS: dict[str, tuple[str, ...]] = {
    "lead_form": ("devis", "quote", "estimate", "project", "projet", "simulation"),
    "appointment": ("appointment", "booking", "rendez vous", "reservation"),
    "catalogue": ("catalogue", "catalog", "brochure"),
    "newsletter": ("newsletter", "infolettre"),
    "support_or_contact": ("contact", "support", "message", "help", "aide"),
    "account": ("login", "connexion", "account", "compte", "password", "mot de passe"),
    "search_results": ("search", "recherche"),
    "listing": ("filter", "filtre", "sort", "trier", "tri", "category", "categorie"),
    "product_detail": ("product", "produit", "variant", "taille", "size", "color", "couleur"),
    "cart": ("cart", "panier", "coupon", "promo"),
    "checkout": ("checkout", "livraison", "shipping", "paiement", "payment"),
}

UNRELATED_FORM_TERMS: dict[str, tuple[str, ...]] = {
    "newsletter": ("newsletter", "infolettre"),
    "search_results": ("search", "recherche"),
    "account": ("login", "connexion", "password", "mot de passe"),
}


def _form_corpus(form: dict[str, Any]) -> str:
    reveal_control = form.get("reveal_control", {})
    parts = [
        str(form.get("action", "")),
        str(form.get("id", "")),
        str(form.get("name", "")),
        str(form.get("context_label", "")),
        str(reveal_control.get("label", "")) if isinstance(reveal_control, dict) else "",
        *[
            " ".join(str(field.get(key, "")) for key in ("name", "id", "label", "autocomplete"))
            for field in form.get("fields", [])
            if isinstance(field, dict)
        ],
        *[
            str(control.get("label", ""))
            for control in form.get("submit_controls", [])
            if isinstance(control, dict)
        ],
    ]
    return re.sub(r"[^a-z0-9]+", " ", " ".join(parts).casefold()).strip()


def _corpus_has_term(corpus: str, term: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip()
    return bool(normalized and re.search(rf"(?:^| ){re.escape(normalized)}(?: |$)", corpus))


def form_relevance_score(page: dict[str, Any], form: dict[str, Any]) -> int:
    visible = bool(form.get("visible", True))
    inside_main = bool(form.get("inside_main", True))
    reveal_control = form.get("reveal_control", {})
    has_local_reveal = bool(
        isinstance(reveal_control, dict)
        and reveal_control.get("selector")
        and reveal_control.get("relationship")
        and reveal_control.get("local") is True
    )
    if not visible and not inside_main and not has_local_reveal:
        return -100
    score = 30 if visible else 0
    score += 50 if inside_main else 0
    score += 55 if has_local_reveal else 0
    fields = [field for field in form.get("fields", []) if isinstance(field, dict) and not field.get("disabled")]
    controls = [control for control in form.get("submit_controls", []) if isinstance(control, dict) and not control.get("disabled")]
    score += min(10, len(fields) * 2)
    score += 5 if controls else -20
    template = str(page.get("template", ""))
    corpus = _form_corpus(form)
    if any(_corpus_has_term(corpus, term) for term in FORM_PURPOSE_TERMS.get(template, ())):
        score += 30
    for purpose, terms in UNRELATED_FORM_TERMS.items():
        if purpose != template and any(_corpus_has_term(corpus, term) for term in terms):
            score -= 55
    return score


def relevant_forms(
    page: dict[str, Any],
    *,
    visible_only: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    scored = []
    for form in page.get("forms", []):
        if not isinstance(form, dict) or (visible_only and not form.get("visible", True)):
            continue
        score = form_relevance_score(page, form)
        if score < 40:
            continue
        scored.append((score, str(form.get("selector", "")), form))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [form for _, _, form in scored]
    return selected if limit is None else selected[: max(0, limit)]


def aggregate_coverage_statuses(statuses: list[str]) -> str:
    values = [value for value in statuses if value]
    if not values:
        return "partial"
    unique = set(values)
    if unique == {"observed"}:
        return "observed"
    if unique == {"externally_blocked"}:
        return "externally_blocked"
    if unique == {"not_tested"}:
        return "not_tested"
    if unique == {"blocked"}:
        return "blocked"
    return "partial"


def merge_evidence_coverage_statuses(statuses: list[str]) -> str:
    """Merge repeated evidence for the same coverage unit across reports."""
    values = {value for value in statuses if value}
    if not values:
        return "partial"
    for status in ("observed", "partial", "externally_blocked", "blocked", "not_tested"):
        if status in values:
            return status
    return "partial"


def _union(records: list[dict[str, Any]], key: str) -> list[Any]:
    return sorted(
        {
            value
            for record in records
            for value in record.get(key, [])
        },
        key=str,
    )


def _longest(values: list[str]) -> str:
    ordered = sorted((value for value in values if value), key=lambda value: (-len(value), value))
    return ordered[0] if ordered else ""


def _group_records(
    reports: list[dict[str, Any]],
    collection: str,
    identity: str,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        for record in report.get(collection, []):
            if isinstance(record, dict) and record.get(identity):
                grouped.setdefault(str(record[identity]), []).append(record)
    return grouped


def _representative(records: list[dict[str, Any]]) -> dict[str, Any]:
    return dict(
        sorted(
            records,
            key=lambda record: json.dumps(record, ensure_ascii=False, sort_keys=True),
        )[0]
    )


def _require_consistent(
    records: list[dict[str, Any]],
    *,
    identity: str,
    keys: tuple[str, ...],
) -> None:
    for key in keys:
        values = {str(record.get(key, "")) for record in records}
        if len(values) > 1:
            raise ValueError(f"{identity} conflicts on {key}.")


def _merge_hints(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    grouped = _group_records(reports, "measurement_opportunity_hints", "hint_id")
    for hint_id, records in sorted(grouped.items()):
        _require_consistent(
            records,
            identity=f"Discovery hint '{hint_id}'",
            keys=("hint_key", "journey_id", "variant_id", "category"),
        )
        representative = _representative(records)
        representative.update(
            {
                "materiality": (
                    "material"
                    if any(record.get("materiality") == "material" for record in records)
                    else "candidate"
                ),
                "evidence_urls": _union(records, "evidence_urls"),
                "evidence_structure_hashes": _union(records, "evidence_structure_hashes"),
                "capability_ids": _union(records, "capability_ids"),
                "reason": _longest([str(record.get("reason", "")) for record in records]),
            }
        )
        merged.append(representative)
    return merged


def _merge_variants(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        for variant in record.get("variant_coverage", []):
            if isinstance(variant, dict) and variant.get("variant_id"):
                grouped.setdefault(str(variant["variant_id"]), []).append(variant)
    return [
        {
            "variant_id": variant_id,
            "access_profile_id": str(_representative(variant_records).get("access_profile_id", "public")),
            "role": str(_representative(variant_records).get("role", "public")),
            "state_id": str(_representative(variant_records).get("state_id", "entry")),
            "material": any(record.get("material") is True for record in variant_records),
            "status": merge_evidence_coverage_statuses(
                [str(record.get("status", "")) for record in variant_records]
            ),
            "entry_points": _union(variant_records, "entry_points"),
            "states_covered": _union(variant_records, "states_covered"),
            "evidence_urls": _union(variant_records, "evidence_urls"),
            "unvisited_material_candidates": _union(
                variant_records,
                "unvisited_material_candidates",
            ),
        }
        for variant_id, variant_records in sorted(grouped.items())
    ]


def _merge_ledger(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    grouped = _group_records(reports, "journey_coverage_ledger", "journey_id")
    for journey_id, records in sorted(grouped.items()):
        variants = _merge_variants(records)
        material_statuses = [
            str(record["status"])
            for record in variants
            if record.get("material") is True
        ]
        merged.append(
            {
                "journey_id": journey_id,
                "material": any(record.get("material") is True for record in records),
                "status": aggregate_coverage_statuses(
                    material_statuses
                    or [str(record.get("status", "")) for record in records]
                ),
                "entry_points": _union(records, "entry_points"),
                "states_covered": _union(records, "states_covered"),
                "variants": _union(records, "variants"),
                "evidence_urls": _union(records, "evidence_urls"),
                "unvisited_material_candidates": _union(records, "unvisited_material_candidates"),
                "variant_coverage": variants,
            }
        )
    return merged


def _observed_units(ledger: list[dict[str, Any]]) -> tuple[set[str], set[tuple[str, str]]]:
    journeys = {
        str(record["journey_id"])
        for record in ledger
        if record.get("status") == "observed"
    }
    variants = {
        (str(record["journey_id"]), str(variant["variant_id"]))
        for record in ledger
        for variant in record.get("variant_coverage", [])
        if variant.get("status") == "observed"
    }
    return journeys, variants


INTERACTION_GAP_ID = re.compile(
    r"^interaction_(?:not_executed|incomplete|boundary)_.+_([a-f0-9]{10})$"
)


def coverage_gap_identity(record: dict[str, Any]) -> tuple[str, ...]:
    """Return the stable coverage unit represented by a gap or interaction run."""
    recipe_id = str(record.get("recipe_id", ""))
    digest = hashlib.sha256(recipe_id.encode("utf-8")).hexdigest()[:10] if recipe_id else ""
    if not digest:
        match = INTERACTION_GAP_ID.fullmatch(str(record.get("gap_id", "")))
        digest = match.group(1) if match else ""
    if digest:
        return (
            "interaction_recipe",
            str(record.get("journey_id", "")),
            str(record.get("variant_id", "")),
            digest,
        )
    return ("coverage_gap", str(record.get("gap_id", "")))


def _group_gaps(reports: list[dict[str, Any]]) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for report in reports:
        for record in report.get("coverage_gaps", []):
            if isinstance(record, dict) and record.get("gap_id"):
                grouped.setdefault(coverage_gap_identity(record), []).append(record)
    return grouped


def _completed_interaction_identities(reports: list[dict[str, Any]]) -> set[tuple[str, ...]]:
    return {
        coverage_gap_identity(run)
        for report in reports
        for run in report.get("automatic_interaction_runs", [])
        if isinstance(run, dict)
        and run.get("recipe_id")
        and run.get("outcome") == "completed"
    }


def _merge_gaps(
    reports: list[dict[str, Any]],
    ledger: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    grouped = _group_gaps(reports)
    completed_interactions = _completed_interaction_identities(reports)
    observed_journeys, observed_variants = _observed_units(ledger)
    for identity, records in sorted(grouped.items()):
        gap_id = str(records[0].get("gap_id", ""))
        interaction_gap = identity[0] == "interaction_recipe"
        _require_consistent(
            records,
            identity=f"Coverage gap '{gap_id}'",
            keys=(
                ("journey_id", "variant_id")
                if interaction_gap
                else ("journey_id", "variant_id", "evidence_state")
            ),
        )
        evidence_states = [
            str(record.get("evidence_state", ""))
            for record in records
            if record.get("evidence_state")
        ]
        evidence_state = (
            merge_evidence_coverage_statuses(evidence_states)
            if evidence_states
            else ""
        )
        matching_state = [
            record
            for record in records
            if str(record.get("evidence_state", "")) == evidence_state
        ]
        representative = _representative(matching_state or records)
        journey_id = str(representative.get("journey_id", ""))
        variant_id = str(representative.get("variant_id", ""))
        if interaction_gap and identity in completed_interactions:
            continue
        if not interaction_gap and (
            (variant_id and (journey_id, variant_id) in observed_variants)
            or (not variant_id and journey_id in observed_journeys)
        ):
            continue
        representative.update(
            {
                "material": any(record.get("material") is True for record in records),
                "description": _longest([str(record.get("description", "")) for record in records]),
                "candidate_urls": _union(records, "candidate_urls"),
            }
        )
        if evidence_state:
            representative["evidence_state"] = evidence_state
        merged.append(representative)
    return merged


def _merged_outcome(reports: list[dict[str, Any]]) -> str:
    outcomes = {str(report.get("outcome", "partial")) for report in reports}
    if outcomes == {"completed"}:
        return "completed"
    if outcomes == {"blocked"}:
        return "blocked"
    return "partial"


def merge_discovery_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge same-site discovery evidence conservatively and deterministically."""
    if not reports:
        raise ValueError("At least one discovery report is required.")
    ordered = sorted(reports, key=lambda report: str(report.get("report_id", "")))
    roots = {str(report.get("root_url", "")).rstrip("/").casefold() for report in ordered}
    if len(roots) != 1:
        raise ValueError("One analysis context cannot seed discovery reports from different root sites.")
    run_ids = {str(report.get("run_id")) for report in ordered if report.get("run_id")}
    if len(run_ids) > 1:
        raise ValueError("Discovery reports from different run IDs cannot be merged as one fresh run.")

    merged_ledger = _merge_ledger(ordered)
    report_ids = [str(report["report_id"]) for report in ordered]
    digest = hashlib.sha256("|".join(report_ids).encode("utf-8")).hexdigest()[:16]
    primary_languages = [str(report["language_summary"]["primary_language"]) for report in ordered]
    access_profiles_by_id: dict[str, dict[str, Any]] = {}
    for report in ordered:
        for profile in report.get("access_profile_runs", []):
            if not isinstance(profile, dict) or not profile.get("profile_id"):
                continue
            profile_id = str(profile["profile_id"])
            existing = access_profiles_by_id.get(profile_id)
            if existing and (
                str(existing.get("role", "")) != str(profile.get("role", ""))
                or sorted(existing.get("allowed_hosts", [])) != sorted(profile.get("allowed_hosts", []))
            ):
                raise ValueError(f"Access profile '{profile_id}' conflicts across discovery reports.")
            access_profiles_by_id[profile_id] = dict(profile)
    return {
        "report_id": f"discovery_merged_{digest}",
        **({"run_id": next(iter(run_ids))} if run_ids else {}),
        "generated_at": max(str(report.get("generated_at", "")) for report in ordered),
        "root_url": str(ordered[0]["root_url"]),
        "outcome": _merged_outcome(ordered),
        "language_summary": {
            "primary_language": sorted(primary_languages)[0],
            "observed_languages": sorted(
                {
                    language
                    for report in ordered
                    for language in report["language_summary"].get("observed_languages", [])
                }
            ),
        },
        "measurement_opportunity_hints": _merge_hints(ordered),
        "journey_coverage_ledger": merged_ledger,
        "coverage_gaps": _merge_gaps(ordered, merged_ledger),
        "access_profile_runs": [
            access_profiles_by_id[key]
            for key in sorted(access_profiles_by_id)
        ],
        "interaction_probe_runs": [
            item
            for report in ordered
            for item in report.get("interaction_probe_runs", [])
            if isinstance(item, dict)
        ],
        "side_effect_log": [
            item
            for report in ordered
            for item in report.get("side_effect_log", [])
            if isinstance(item, dict)
        ],
    }
