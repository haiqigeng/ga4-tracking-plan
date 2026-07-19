from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from official_source_receipt import pending_receipt
from tracking_plan_contract import event_parameter_names

FIXTURE = Path(__file__).resolve().parents[1] / "references" / "03-rules" / "example-ga4-tracking-plan.json"

FRENCH_PARAMETER_COPY = {
    "page_location": {
        "display_name": "URL de la page",
        "description": "URL complète de la page consultée par l'utilisateur sur le site.",
        "reporting_purpose": "Permet d'analyser les pages consultées après suppression des paramètres de requête sensibles.",
        "value_rules": "Utiliser l'URL courante après suppression des paramètres de requête sensibles.",
    },
    "page_title": {
        "display_name": "Titre de la page",
        "description": "Titre HTML défini pour la page ; ce paramètre peut remplacer la valeur de la balise title.",
        "reporting_purpose": "Fournit un libellé lisible pour l'analyse des pages et la validation dans DebugView.",
        "value_rules": "Utiliser le titre de page fourni par le CMS ou le navigateur.",
    },
    "page_referrer": {
        "display_name": "Page précédente",
        "description": "URL précédente de l'utilisateur, sur le même domaine ou sur un domaine externe.",
        "reporting_purpose": "Permet d'analyser le contexte de navigation et d'acquisition des pages vues.",
        "value_rules": "Utiliser le référent du navigateur après suppression des paramètres de requête sensibles.",
    },
    "page_template": {
        "display_name": "Modèle de page",
        "description": "Modèle fonctionnel utilisé pour afficher la page consultée.",
        "reporting_purpose": "Regroupe les performances et les comportements par modèle de page.",
        "value_rules": "Utiliser une valeur stable en minuscules et snake_case fournie par le CMS ou la dataLayer.",
    },
    "nav_language": {
        "display_name": "Langue de navigation",
        "description": "Langue du contenu et de la navigation présentés à l'utilisateur.",
        "reporting_purpose": "Compare les parcours et les résultats selon la langue du site.",
        "value_rules": "Utiliser le code de langue gouverné du site, par exemple fr ou en.",
    },
    "nav_environment": {
        "display_name": "Environnement de navigation",
        "description": "Environnement technique dans lequel la page est consultée.",
        "reporting_purpose": "Sépare les données de production des environnements de recette et de développement.",
        "value_rules": "Utiliser une valeur gouvernée telle que production, staging ou development.",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a focused GA4 tracking-plan JSON draft from one initial journey.")
    parser.add_argument("url", help="Representative public URL for the initial journey.")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--title", default="GA4 tracking plan draft", help="Human document title.")
    parser.add_argument("--owner", default="TBD", help="Human owner shown in the workbook.")
    parser.add_argument("--journey-name", default="Initial journey", help="Human journey name.")
    parser.add_argument("--journey-id", help="Stable lowercase journey ID. Derived from the journey name when omitted.")
    parser.add_argument("--plan-id", help="Stable lowercase plan ID. Derived from the title when omitted.")
    parser.add_argument(
        "--site-scope",
        choices=("whole_site", "selected_journeys", "selected_pages", "single_journey"),
        default="selected_pages",
        help="Intended website coverage. Live browser discovery remains required independently of screenshots.",
    )
    parser.add_argument("--workbook-language", choices=("en", "fr"), default="en", help="Human wording language for the generated workbook.")
    parser.add_argument("--site-language", action="append", dest="site_languages", help="Observed or confirmed site language code. Repeat for multilingual sites.")
    parser.add_argument(
        "--screenshots",
        choices=("required", "not_requested"),
        default="required",
        help="Use not_requested only when the requester explicitly excludes screenshots.",
    )
    return parser.parse_args()


def identifier(value: str, fallback: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return normalized or fallback


def validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The initial URL must be an absolute http:// or https:// URL.")
    return value


def no_user_context() -> dict:
    return {
        "status": "not_applicable",
        "data_layer_object": "user",
        "push_timing": [],
        "ga4_user_id": {
            "enabled": False,
            "source_path": "",
            "signed_out_behavior": "not_applicable",
            "mapping_rule": "Authenticated user context is outside this initial scaffold until website discovery confirms it.",
        },
        "user_properties": [],
        "advertising_user_data": {
            "status": "not_applicable",
            "data_layer_object": "",
            "destination": "not_applicable",
            "fields": [],
            "consent_requirements": [],
            "handling_rule": "No advertising user data is defined in this initial GA4 scaffold.",
        },
    }


def localize_french_scaffold(event: dict, parameters: list[dict], url: str, journey_name: str) -> None:
    event.update(
        {
            "page_or_component": f"Page représentative du parcours {journey_name}",
            "trigger": f"Au chargement de la page ou lors d'un changement de route SPA vers {url}.",
            "event_summary": "Cet événement indique qu'une page a été chargée ou que le site actif a modifié l'état de l'historique du navigateur.",
            "implementation_notes": "Éviter un doublon de page_view si la mesure améliorée envoie déjà l'événement attendu.",
        }
    )
    event["data_layer"]["mapping_notes"] = (
        "Ne pas envoyer un second page_view si la collecte automatique de GA4 est suffisante. "
        "Utiliser un page_view manuel uniquement pour un routage SPA contrôlé ou un contexte de page enrichi."
    )
    event["privacy"]["notes"] = (
        "Supprimer les paramètres de requête sensibles de page_location lorsque l'URL peut en contenir."
    )

    event_verification = event.get("official_verification", {})
    if event_verification.get("status") == "verified":
        event_verification["translation_status"] = "analyst_translation"

    for parameter in parameters:
        parameter.update(FRENCH_PARAMETER_COPY.get(parameter["parameter_name"], {}))
        verification = parameter.get("official_verification", {})
        if verification.get("status") == "verified":
            verification["translation_status"] = "analyst_translation"


def set_value_domain(
    parameter: dict,
    values: list[str],
    *,
    language: str,
    method: str = "normalization_only",
) -> None:
    parameter["value_domain"] = {
        "mode": "proposed_taxonomy",
        "entries": [
            {
                "raw_label": value,
                "normalized_value": value,
                "language": language,
                "source_ref": "",
                "mapping_method": method,
            }
            for value in values
        ],
        "source_refs": [],
        "notes": "Proposed controlled values; confirm the final taxonomy with the website and implementation owners.",
    }


def set_unresolved_domain(parameter: dict, note: str) -> None:
    parameter["example_value"] = ""
    parameter["value_domain"] = {
        "mode": "blocked",
        "entries": [],
        "source_refs": [],
        "notes": note,
    }


def screenshot_state(
    requirement: str,
    event_id: str,
    journey_name: str,
    url: str,
) -> tuple[dict, dict, list[dict]]:
    if requirement == "not_requested":
        coverage = {"mode": "not_needed", "scenarios": []}
        capture = {
            "requirement": "not_requested",
            "playwright_mcp_attempt": {"status": "not_required", "detail": "The requester explicitly excluded screenshots from this delivery."},
            "outcome": "not_requested",
            "delivery_notice": "Screenshots were explicitly excluded from this tracking-plan delivery.",
        }
        return coverage, capture, []
    else:
        coverage = {"mode": "representative", "scenarios": ["representative_example"]}
        capture = {
            "requirement": "required",
            "playwright_mcp_attempt": {"status": "not_recorded", "detail": "Run Playwright MCP website exploration before final delivery."},
            "outcome": "blocked",
            "delivery_notice": "Screenshot capture remains blocked until a Playwright MCP attempt is recorded.",
        }
        status = "blocked"
        notes = "Attempt Playwright MCP and replace this blocked row with captured evidence before delivery."
    evidence = {
        "evidence_id": f"EVIDENCE-{event_id}",
        "event_ids": [event_id],
        "scenario_id": "representative_example",
        "file_name": "",
        "page_or_component": f"{journey_name} representative page",
        "url_or_route": url,
        "capture_objective": f"Show the representative page state for {journey_name}.",
        "status": status,
        "shared_reason": "",
        "notes": notes,
    }
    return coverage, capture, [evidence]


def resolve_language_settings(
    workbook_language: str,
    site_languages: list[str] | None,
) -> tuple[str, list[str], str]:
    languages = list(dict.fromkeys(site_languages or []))
    scope = "multilingual" if len(languages) > 1 else "single_language" if languages else "unknown"
    return ("en" if scope == "multilingual" else workbook_language), languages, scope


def configure_scaffold_parameter(
    parameter: dict,
    *,
    url: str,
    workbook_language: str,
    site_languages: list[str],
) -> None:
    parameter_name = parameter["parameter_name"]
    if parameter_name == "page_location":
        parameter["example_value"] = url
        return
    if parameter_name == "page_template":
        set_unresolved_domain(parameter, "Resolve the functional page-template taxonomy from live website or CMS evidence.")
        return
    if parameter_name == "nav_language":
        if site_languages:
            set_value_domain(parameter, site_languages, language="zxx", method="official_or_technical_value")
        else:
            set_unresolved_domain(parameter, "Resolve page language from HTML, locale routes, a selector, or client confirmation.")
        return
    if parameter_name == "nav_environment":
        set_unresolved_domain(parameter, "Resolve the governed environment taxonomy from deployment or client evidence.")


def build_scaffold_event(
    fixture: dict,
    *,
    event_id: str,
    journey_id: str,
    journey_name: str,
    url: str,
    screenshots: str,
    workbook_language: str,
    site_languages: list[str],
) -> tuple[dict, list[dict], dict, list[dict]]:
    event = copy.deepcopy(next(item for item in fixture["events"] if item["event_name"] == "page_view"))
    selected_parameters = set(event_parameter_names(event))
    parameters = [
        copy.deepcopy(item)
        for item in fixture["parameters"]
        if item["parameter_name"] in selected_parameters
    ]
    coverage, capture, evidence = screenshot_state(screenshots, event_id, journey_name, url)
    event.update(
        {
            "event_id": event_id,
            "journey_ids": [journey_id],
            "journey_stage": "context",
            "display_order": 1,
            "page_url_pattern": url,
            "page_or_component": f"{journey_name} representative page",
            "trigger": f"Page load or SPA route change for {url}.",
            "screenshot_coverage": coverage,
            "evidence_basis": {
                "status": "inferred",
                "source_refs": [f"Initial URL supplied: {url}"],
                "confidence": "low",
                "basis_type": "analyst_judgement",
            },
        }
    )
    event["data_layer"]["consent_timing"] = "core_context_before_cmp_ready"
    event["data_layer"]["push"].setdefault("page", {}).update(
        {
            "page_location": url,
            "page_template": "%page_template_to_resolve%",
            "nav_language": site_languages[0] if site_languages else "%page_language_to_resolve%",
            "nav_environment": "%environment_to_resolve%",
        }
    )
    for derived_or_unresolved in ("priority", "page_type", "business_question", "analysis_use"):
        event.pop(derived_or_unresolved, None)
    event.pop("business_event_family", None)
    for parameter in parameters:
        configure_scaffold_parameter(
            parameter,
            url=url,
            workbook_language=workbook_language,
            site_languages=site_languages,
        )
    if workbook_language == "fr":
        localize_french_scaffold(event, parameters, url, journey_name)
    return event, parameters, capture, evidence


def attach_required_documentation_sources(
    plan: dict,
    fixture: dict,
    event: dict,
    parameters: list[dict],
) -> None:
    required_source_ids = {
        "developers_tag_platform_tag_manager_datalayer",
        str(event.get("official_verification", {}).get("source_id", "")),
        str(event.get("official_verification", {}).get("trigger_source_id", "")),
        *(str(parameter.get("official_verification", {}).get("source_id", "")) for parameter in parameters),
    }
    plan["documentation_sources_checked"] = []
    for source in fixture["documentation_sources_checked"]:
        if source.get("source_id") in required_source_ids:
            source_copy = copy.deepcopy(source)
            source_copy["checked_date"] = None
            plan["documentation_sources_checked"].append(source_copy)


def initialize_plan(
    url: str,
    *,
    title: str = "GA4 tracking plan draft",
    owner: str = "TBD",
    journey_name: str = "Initial journey",
    journey_id: str | None = None,
    plan_id: str | None = None,
    site_scope: str = "selected_pages",
    screenshots: str = "required",
    workbook_language: str = "en",
    site_languages: list[str] | None = None,
) -> dict:
    url = validate_url(url)
    journey_id = identifier(journey_id or journey_name, "initial_journey")
    plan_id = identifier(plan_id or title, "ga4_tracking_plan")
    workbook_language, site_languages, site_language_scope = resolve_language_settings(
        workbook_language,
        site_languages,
    )
    if site_language_scope == "unknown":
        language_decision_basis = (
            f"Workbook language is {workbook_language}; website language remains unresolved. "
            "Controlled values stay in English until website or client evidence is available."
        )
    elif site_language_scope == "multilingual":
        language_decision_basis = "Observed or supplied multilingual scope requires English workbook wording and controlled values."
    else:
        language_decision_basis = f"Single-language scope was supplied as {site_languages[0]}; workbook language is {workbook_language}."
    event_id = f"EVT-{journey_id.upper().replace('_', '-')}-PAGE-VIEW"
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event, parameters, capture, evidence = build_scaffold_event(
        fixture,
        event_id=event_id,
        journey_id=journey_id,
        journey_name=journey_name,
        url=url,
        screenshots=screenshots,
        workbook_language=workbook_language,
        site_languages=site_languages,
    )

    plan = {
        "schema_version": "3.0.0",
        "plan_id": plan_id,
        "execution_context": {
            "execution_mode": "greenfield_best_practice",
            "mode_reason": "Initial greenfield draft created before full website and business-journey discovery.",
            "input_artifact_inventory": [
                {
                    "artifact_type": "website_url",
                    "artifact_ref": url,
                    "role": "Seed the initial journey and website discovery.",
                    "template_relevance": "site_discovery",
                    "confidentiality_status": "public_url",
                }
            ],
            "template_policy": {
                "mode": "default_skill_template",
                "template_source": "generate_tracking_plan_workbook.py",
                "preservation_requirements": ["Keep the five core human sheets stable and include Screenshot Register only when screenshots are requested."],
                "allowed_changes": ["Replace scaffold content with observed journeys, events, parameters, and evidence."],
                "template_diff_required": False,
            },
        },
        "document": {
            "title": title,
            "version": "v0.1",
            "owner": owner,
            "notes": "Initial analyst draft. Complete website discovery, business questions, events, parameters, and evidence before publication.",
            "publish_date": date.today().isoformat(),
        },
        "language_policy": {
            "site_language_scope": site_language_scope,
            "site_languages": site_languages,
            "workbook_language": workbook_language,
            "controlled_value_language": "en" if site_language_scope in {"multilingual", "unknown"} else workbook_language,
            "technical_name_language": "en",
            "controlled_value_format": "lowercase_ascii_snake_case",
            "decision_basis": language_decision_basis,
        },
        "measurement_brief": [
            {
                "journey_id": journey_id,
                "journey_name": journey_name,
                "scope": "Initial journey seed; resolve scope through live discovery.",
                "url_or_route": url,
                "open_questions": ["Which business outcomes and interactions belong to this journey?", "Which values are available from the website or backend?"],
            }
        ],
        "measurement_strategy": {},
        "website_coverage_map": {
            "site_scope": site_scope,
            "coverage_summary": f"Initial scaffold covers only the representative URL {url}.",
            "sources_checked": [
                {"source_type": "url_list", "source_ref": url, "used_for": "Seed public website discovery.", "confidence": "low"}
            ],
            "journeys_covered": [
                {
                    "journey_id": journey_id,
                    "journey_name": journey_name,
                    "representative_urls": [url],
                    "page_templates": ["to_resolve"],
                    "key_interactions": ["page view"],
                    "coverage_status": "assumed",
                    "tracking_plan_decision": "included",
                    "evidence": [f"Initial URL supplied: {url}"],
                    "notes": "Replace assumed coverage with observed browser evidence before publication.",
                }
            ],
            "coverage_gaps": [
                {
                    "gap": "Remaining public, dynamic, transactional, and authenticated journeys have not been explored.",
                    "impact": "The scaffold is not a complete website tracking plan.",
                    "recommended_next_step": "Run browser and Playwright MCP discovery, then add only observed or client-confirmed journeys.",
                }
            ],
            "authenticated_journey": {
                "applicable": site_scope == "whole_site",
                "discovery_status": "not_attempted" if site_scope == "whole_site" else "not_applicable",
                "attempted_actions": [],
                "evidence": [],
                "gap_reason": "Whole-site authentication discovery has not been run." if site_scope == "whole_site" else "Authenticated journeys are outside the selected-page scaffold.",
            },
            "browser_exploration": {
                "requirement": "required",
                "playwright_mcp_attempt": {
                    "status": "not_recorded",
                    "detail": "Run Playwright MCP for live journey and finite-value discovery before final delivery; this is independent of screenshot delivery.",
                },
                "selected_browser": "",
                "journey_discovery_status": "blocked",
                "value_discovery_status": "blocked",
                "evidence_refs": [],
                "detail": "Browser research is pending for this initial scaffold.",
            },
            "journeys_discovered": [
                {
                    "journey_id": journey_id,
                    "journey_name": journey_name,
                    "source_refs": [f"Initial URL supplied: {url}"],
                    "representative_urls": [url],
                    "page_templates": ["to_resolve"],
                    "key_interactions": ["page view"],
                    "decision": "include_in_plan",
                    "decision_reason": "Retain as the initial journey seed until browser evidence refines the scope.",
                }
            ],
        },
        "user_context": no_user_context(),
        "events": [event],
        "parameters": parameters,
        "screenshot_capture": capture,
        "screenshot_evidence": evidence,
        "not_tracked": [
            {"interaction": "Interactions not yet observed", "reason": "The initializer creates a page-context scaffold, not an inferred event inventory.", "reason_code": "out_of_scope"}
        ],
        "assumptions": ["The supplied URL is a public representative page and requires browser discovery before the plan is complete."],
        "documentation_sources_checked": [],
        "official_source_check": pending_receipt(),
    }
    attach_required_documentation_sources(plan, fixture, event, parameters)
    return plan


def main() -> int:
    args = parse_args()
    plan = initialize_plan(
        args.url,
        title=args.title,
        owner=args.owner,
        journey_name=args.journey_name,
        journey_id=args.journey_id,
        plan_id=args.plan_id,
        site_scope=args.site_scope,
        screenshots=args.screenshots,
        workbook_language=args.workbook_language,
        site_languages=args.site_languages,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)
    if args.screenshots == "required":
        print("Draft created. Record the Playwright MCP attempt and screenshot outcome before final validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
