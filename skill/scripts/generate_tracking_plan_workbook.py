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
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from tracking_plan_contract import (
    event_ga4_payload,
    event_parameter_bindings,
    parameter_allowed_values,
    primary_journey_id,
)
from tracking_plan_screenshots import (
    PREVIEW_HEIGHT,
    PREVIEW_WIDTH,
    create_screenshot_preview,
    resolve_screenshot,
    screenshot_digest,
    screenshot_files,
)
from tracking_plan_workbook_layout import (
    CENTER,
    EVENT_SLOT_COUNT,
    GRAY,
    GREEN,
    RED,
    SCREENSHOT_ROW_HEIGHT,
    SCREENSHOT_STATUS_OPTIONS,
    TEAL_LIGHT,
    apply_workbook_settings,
    header,
    matrix_max_col,
    matrix_value_columns,
    section,
    set_internal_link,
    set_widths,
    style_cells,
    style_event_matrix_rows,
    style_overview,
    title,
)
from validate_tracking_plan import render_text, validate_plan_data


def workbook_language(plan: dict[str, Any]) -> str:
    return "fr" if plan.get("language_policy", {}).get("workbook_language") == "fr" else "en"


def localized(plan: dict[str, Any], english: str, french: str) -> str:
    return french if workbook_language(plan) == "fr" else english


def localized_enum(plan: dict[str, Any], value: Any) -> str:
    if workbook_language(plan) != "fr":
        return str(value)
    translations = {
        "event": "événement",
        "item": "article",
        "user": "utilisateur",
        "implementation": "implémentation",
        "observed": "observé",
        "confirmed_available": "disponible confirmé",
        "requires_development": "développement requis",
        "requires_backend": "source back-end requise",
        "to_confirm": "à confirmer",
        "unavailable": "indisponible",
        "not_applicable": "non applicable",
        "planned": "prévu",
        "confirmed": "confirmé",
    }
    return translations.get(str(value), str(value))


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
    ga4_payload = event_ga4_payload(event)
    if isinstance(ga4_payload, dict) and ga4_payload.get("event_name"):
        return str(ga4_payload["event_name"])
    return str(event.get("event_name", ""))


def parameter_value(event: dict[str, Any], parameter: str) -> str:
    if event.get("classification") == "recommended_ecommerce":
        if parameter == "items":
            return "Array<Item>; see items[] rows below"
        return parameter_matrix_value(event, parameter)

    payload = event_ga4_payload(event)
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


def parameter_value_rules(parameter: dict[str, Any]) -> str:
    allowed = parameter_allowed_values(parameter)
    if allowed:
        return " | ".join(allowed)
    return str(parameter.get("value_rules", ""))


def binding_for_parameter(event: dict[str, Any], parameter_name: str) -> dict[str, Any] | None:
    return next(
        (
            binding
            for binding in event_parameter_bindings(event)
            if binding.get("parameter_name") == parameter_name
        ),
        None,
    )


def binding_status(plan: dict[str, Any], binding: dict[str, Any] | None) -> str:
    if binding is None:
        return localized(plan, "Not applicable", "Non applicable")
    requirement = localized_enum(plan, binding.get("requirement", ""))
    availability = localized_enum(plan, binding.get("availability", ""))
    return " | ".join(value for value in (requirement, availability) if value)


def parameter_binding_summary(
    plan: dict[str, Any],
    parameter_name: str,
) -> tuple[str, str]:
    availability: list[str] = []
    owners: list[str] = []
    for event in sorted(plan["events"], key=lambda item: item.get("display_order", 0)):
        binding = binding_for_parameter(event, parameter_name)
        if binding is None:
            continue
        event_name = str(event.get("event_name", ""))
        availability.append(
            f"{event_name}: {localized_enum(plan, binding.get('availability', ''))}"
        )
        owner = str(binding.get("data_owner", "")).strip()
        if owner and owner not in owners:
            owners.append(owner)
    return "\n".join(availability), " | ".join(owners)


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


def datalayer_parameter_path(push: dict[str, Any], parameter: str) -> str:
    for wrapper in ("page", "event_data", "ecommerce", "user"):
        wrapped = push.get(wrapper)
        if isinstance(wrapped, dict) and parameter in wrapped:
            return f"{wrapper}.{parameter}"
    return ""


def gtm_mapping(event: dict[str, Any]) -> str:
    name = str(event.get("event_name", ""))
    classification = str(event.get("classification", ""))
    collection_source = str(event.get("collection_strategy", {}).get("collection_source", ""))
    if classification == "enhanced_measurement" and collection_source == "ga4_enhanced_measurement" and not event.get("data_layer"):
        return "Enable in the GA4 web stream; do not create a duplicate manual event tag."

    payload = event_ga4_payload(event)
    parameters = payload.get("parameters", {}) if isinstance(payload, dict) else {}
    data_layer = event.get("data_layer", {})
    push = data_layer.get("push", {}) if isinstance(data_layer, dict) else {}
    native_collection = (
        (classification == "automatic" and collection_source == "ga4_automatic")
        or (classification == "enhanced_measurement" and collection_source == "ga4_enhanced_measurement")
    )
    mappings = (
        ["GA4 native collection; do not create a duplicate manual event tag.", "The dataLayer example supplies reusable context only."]
        if native_collection
        else [f"Custom Event trigger: {name}", f"GA4 event name: {name}"]
    )
    for parameter in parameters if isinstance(parameters, dict) else []:
        source_path = datalayer_parameter_path(push, str(parameter)) if isinstance(push, dict) else ""
        if native_collection and source_path:
            mappings.append(f"{source_path} -> {parameter} through Google tag settings when an explicit mapping is required")
        else:
            mappings.append(f"{source_path} -> {parameter}" if source_path else f"Automatically collected or configured -> {parameter}")
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
    title(ws, doc["title"], localized(plan, "Document details and workbook navigation.", "Informations du document et navigation dans le classeur."), max_col)

    document_summary = localized(plan, "Document Summary", "Informations du document")
    sheet_contents = localized(plan, "Sheet Contents", "Contenu des onglets")
    version_history = localized(plan, "Version History", "Historique des versions")

    rows = [
        [document_summary, "", "", "", "", "", "", "", ""],
        [localized(plan, "Document", "Document"), doc["title"], localized(plan, "Owner / contact", "Responsable / contact"), doc["owner"], localized(plan, "Publish date", "Date de publication"), doc["publish_date"], "", ""],
        ["Version", doc["version"], "", "", "", "", "", ""],
        [],
        [sheet_contents, "", "", "", "", "", "", "", ""],
        ["#", localized(plan, "Sheet", "Onglet"), localized(plan, "What it is for", "Utilité"), "", "", "", "", ""],
        ["1", "00 Overview", localized(plan, "Document information and version history.", "Informations du document et historique des versions."), "", "", "", "", ""],
        ["2", "01 GTM Protocol", localized(plan, "Shared GTM/dataLayer rules and official references.", "Règles GTM/dataLayer communes et références officielles."), "", "", "", "", ""],
        ["3", "02 Parameter Reference", localized(plan, "Variable dictionary and value rules.", "Dictionnaire des variables et règles de valeur."), "", "", "", "", ""],
        ["4", "03 Event Matrix", localized(plan, "Main tracking plan: events, parameters, and value rules.", "Plan de marquage principal : événements, paramètres et règles de valeur."), "", "", "", "", ""],
        ["5", "04 DataLayer Examples", localized(plan, "Complete per-event GTM and dataLayer implementation examples.", "Exemples complets d'implémentation GTM et dataLayer par événement."), "", "", "", "", ""],
        ["6", "05 Screenshot Register", localized(plan, "Page and interaction evidence supporting implementation.", "Captures de pages et d'interactions utiles à l'implémentation."), "", "", "", "", ""],
        [],
        [version_history, "", "", "", "", "", "", "", ""],
        ["Version", "Date", localized(plan, "Owner", "Responsable"), localized(plan, "Summary", "Résumé"), localized(plan, "Publish date", "Date de publication"), "", "", "", ""],
        [doc["version"], doc["publish_date"], doc["owner"], localized(plan, "GA4 tracking plan prepared for review.", "Plan de marquage GA4 préparé pour revue."), doc["publish_date"], "", "", "", ""],
    ]
    include_screenshots = plan.get("screenshot_capture", {}).get("requirement") != "not_requested"
    if not include_screenshots:
        rows = [row for row in rows if len(row) < 2 or row[1] != "05 Screenshot Register"]
    for row in rows:
        ws.append((row + [""] * max_col)[:max_col])

    workbook_tabs = {
        "00 Overview",
        "01 GTM Protocol",
        "02 Parameter Reference",
        "03 Event Matrix",
        "04 DataLayer Examples",
    }
    if include_screenshots:
        workbook_tabs.add("05 Screenshot Register")
    for row in range(1, ws.max_row + 1):
        label = ws.cell(row, 1).value
        if label in {document_summary, sheet_contents, version_history}:
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
    title(ws, localized(plan, "GTM Protocol", "Protocole GTM"), localized(plan, "Essential GTM and dataLayer rules for implementing the Event Matrix.", "Règles GTM et dataLayer essentielles pour implémenter la matrice des événements."), 4)
    user_context = plan.get("user_context", {})
    language_policy = plan.get("language_policy", {})
    french_values = language_policy.get("controlled_value_language") == "fr"
    login_value = "connecte" if french_values else "logged_in"
    customer_value = "existant" if french_values else "returning"
    controlled_value_example = "pret_a_porter_femme" if french_values else "women_ready_to_wear"
    user_context_example = (
        "dataLayer.push({\n"
        "  user: {\n"
        "    user_id: \"%opaque_user_id%\",\n"
        f"    login_status: \"{login_value}\",\n"
        f"    customer_status: \"{customer_value}\",\n"
        "    account_type: \"standard\"\n"
        "  }\n"
        "});"
    )
    user_properties = "\n".join(
        f"{item.get('source_path')} -> GA4 user property {item.get('parameter_name')}"
        for item in user_context.get("user_properties", [])
        if isinstance(item, dict)
    ) or localized(plan, "No custom GA4 user properties planned.", "Aucune propriété utilisateur GA4 personnalisée prévue.")
    ads = user_context.get("advertising_user_data", {})
    ads_rule = str(ads.get("handling_rule", "Direct identifiers are not sent to GA4.")) if isinstance(ads, dict) else "Direct identifiers are not sent to GA4."
    rows = [
        [localized(plan, "Topic", "Sujet"), localized(plan, "Rule", "Règle"), localized(plan, "Example", "Exemple"), "Notes"],
        [localized(plan, "Workbook and value language", "Langue du document et des valeurs"), localized(plan, "Use English across multilingual sites. French-only sites may use French human wording and French semantic values; all technical names stay in English.", "Utiliser l'anglais pour les sites multilingues. Un site uniquement français peut utiliser un texte et des valeurs sémantiques en français ; les noms techniques restent en anglais."), f"workbook_language: {language_policy.get('workbook_language', 'en')}\ncontrolled_value_language: {language_policy.get('controlled_value_language', 'en')}", str(language_policy.get("decision_basis", ""))],
        [localized(plan, "GTM base script", "Script GTM de base"), localized(plan, "Load the GTM container once on every page. Replace GTM-XXXX with the project container ID.", "Charger le conteneur GTM une seule fois sur chaque page. Remplacer GTM-XXXX par l'identifiant du projet."), "<!-- Google Tag Manager -->\n<script>/* GTM base script with GTM-XXXX */</script>\n<!-- End Google Tag Manager -->", localized(plan, "For SPA websites, keep the container in the root HTML shell.", "Pour une SPA, conserver le conteneur dans le shell HTML racine.")],
        [localized(plan, "Project dataLayer contract", "Convention dataLayer du projet"), localized(plan, "For manual events, keep the final GA4 event name in the top-level event string. Put page context in page, ordinary interaction parameters in event_data, ecommerce data in ecommerce, and connected-user state in user. A native page/core context push omits event.", "Pour les événements manuels, conserver le nom final de l'événement GA4 dans la chaîne event à la racine. Placer le contexte de page dans page, les paramètres d'interaction dans event_data, les données ecommerce dans ecommerce et l'état connecté dans user. Un push de contexte page/core natif omet event."), "dataLayer.push({\n  event: \"search\",\n  event_data: { search_term: \"summer_dresses\" }\n});", localized(plan, "The page, event_data, and user wrappers are project conventions. Each inner key must match the final GA4 parameter or user-property name; GTM unwraps but does not rename it.", "Les wrappers page, event_data et user sont des conventions du projet. Chaque clé interne doit correspondre au nom final du paramètre ou de la propriété utilisateur GA4 ; GTM retire le wrapper sans renommer la clé.")],
        [localized(plan, "CMP sequence", "Séquence CMP"), localized(plan, "Page/core context may be prepared before CMP readiness. Push every other manual event only after the CMP has established the applicable consent state.", "Le contexte page/core peut être préparé avant que la CMP soit prête. Pousser tout autre événement manuel uniquement après l'établissement de l'état de consentement applicable."), "core_context_before_cmp_ready\nafter_cmp_ready", localized(plan, "An early dataLayer push does not authorize a tag to fire before its consent requirements are satisfied.", "Un push dataLayer anticipé n'autorise pas un tag à se déclencher avant que ses exigences de consentement soient satisfaites.")],
        [localized(plan, "Flush reusable objects", "Réinitialisation des objets"), localized(plan, "Flush page, ecommerce, event_data, or user before replacement when previous values could persist.", "Réinitialiser page, ecommerce, event_data ou user avant remplacement lorsque des valeurs précédentes peuvent persister."), "dataLayer.push({ event_data: null });", localized(plan, "Use a separate push for flushing.", "Utiliser un push distinct pour la réinitialisation.")],
        [localized(plan, "Controlled values", "Valeurs contrôlées"), localized(plan, "Use lowercase ASCII snake_case, replace spaces with underscores, and remove accents for controlled analytics values.", "Utiliser le snake_case ASCII en minuscules, remplacer les espaces par des underscores et supprimer les accents."), controlled_value_example, localized(plan, "Keep product IDs, ISO codes, numeric values, URLs, and safe raw terms when required.", "Conserver les identifiants produit, codes ISO, nombres, URL et valeurs brutes sûres lorsque nécessaire.")],
        ["GA4 ecommerce", localized(plan, "Use official GA4 ecommerce event names and parameters. Keep ecommerce event blocks separate from interaction events.", "Utiliser les noms et paramètres ecommerce GA4 officiels. Séparer les blocs ecommerce des événements d'interaction."), "items[].item_id\nitems[].item_name\ncurrency\nvalue", localized(plan, "Map GTM wrapper paths in implementation notes, not as replacements for GA4 names.", "Documenter les chemins des wrappers GTM sans remplacer les noms GA4.")],
        [localized(plan, "Connected user context", "Contexte utilisateur connecté"), localized(plan, "Push user independently when authentication state is known, after successful login, and after logout. Do not repeat these fields inside every event push.", "Pousser user lorsque l'état d'authentification est connu, après une connexion réussie et après la déconnexion. Ne pas répéter ces champs dans chaque événement."), user_context_example, localized(plan, f"Plan status: {localized_enum(plan, user_context.get('status', 'not_applicable'))}. Keep the object available before dependent GA4 events.", f"Statut du plan : {localized_enum(plan, user_context.get('status', 'not_applicable'))}. Rendre l'objet disponible avant les événements GA4 dépendants.")],
        ["GA4 User-ID", localized(plan, "Map user.user_id only to the Google tag user_id setting. Omit before first sign-in and set null after logout.", "Mapper user.user_id uniquement vers le paramètre user_id du Google tag. L'omettre avant la première connexion et envoyer null après déconnexion."), "user.user_id -> Google tag user_id", localized(plan, "Never send user_id as an event parameter or user property, and never register it as a custom dimension.", "Ne jamais envoyer user_id comme paramètre d'événement ou propriété utilisateur, ni l'enregistrer comme dimension personnalisée.")],
        [localized(plan, "GA4 user properties", "Propriétés utilisateur GA4"), localized(plan, "Map only approved low-cardinality connected-user fields as GA4 user properties.", "Mapper uniquement les champs utilisateur connecté approuvés et à faible cardinalité comme propriétés utilisateur GA4."), user_properties, localized(plan, "Register planned custom user properties in GA4. Do not include direct identifiers.", "Enregistrer les propriétés utilisateur personnalisées prévues dans GA4. Ne pas inclure d'identifiants directs.")],
        [localized(plan, "Advertising user data", "Données utilisateur publicitaires"), localized(plan, "Keep direct identifiers in a separately governed non-GA4 object only when another approved advertising implementation explicitly requires them.", "Conserver les identifiants directs dans un objet non-GA4 gouverné séparément uniquement si une implémentation publicitaire approuvée les exige."), str(ads.get("data_layer_object", "")) or localized(plan, "Not applicable", "Non applicable"), ads_rule],
        [localized(plan, "Official references", "Références officielles"), localized(plan, "GA4 recommended events", "Événements GA4 recommandés"), "https://developers.google.com/analytics/devguides/collection/ga4/reference/events", localized(plan, "Check current official documentation before approval. Keep external references here, not on the Overview tab.", "Vérifier la documentation officielle actuelle avant approbation. Conserver les références externes ici, pas dans l'onglet Overview.")],
        ["", "GA4 ecommerce", "https://developers.google.com/analytics/devguides/collection/ga4/ecommerce", ""],
        ["", localized(plan, "GA4 item parameters", "Paramètres d'article GA4"), "https://developers.google.com/analytics/devguides/collection/ga4/item-scoped-ecommerce", ""],
        ["", "GA4 User-ID", "https://developers.google.com/analytics/devguides/collection/ga4/user-id", ""],
        ["", localized(plan, "GA4 user properties", "Propriétés utilisateur GA4"), "https://developers.google.com/analytics/devguides/collection/protocol/ga4/user-properties", ""],
        ["", "GTM dataLayer", "https://developers.google.com/tag-platform/tag-manager/datalayer", ""],
        ["", localized(plan, "Consent mode", "Mode Consentement"), "https://developers.google.com/tag-platform/security/guides/consent", ""],
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
    title(ws, localized(plan, "Parameter Reference", "Référence des paramètres"), localized(plan, "Variable dictionary for parameters used in the Event Matrix.", "Dictionnaire des variables utilisées dans la matrice des événements."), 11)
    headers = [
        localized(plan, "Variable name", "Nom de la variable"),
        localized(plan, "Display name", "Nom affiché"),
        localized(plan, "Scope", "Portée"),
        "Type",
        localized(plan, "Description", "Définition"),
        localized(plan, "Value rules", "Règles de valeur"),
        localized(plan, "Example value", "Exemple de valeur"),
        localized(plan, "Availability by event", "Disponibilité par événement"),
        localized(plan, "Data owner(s)", "Responsable(s) de la donnée"),
        localized(plan, "Register in GA4", "Enregistrer dans GA4"),
        localized(plan, "Privacy / consent", "Vie privée / consentement"),
    ]
    ws.append(headers)
    header(ws, 3, len(headers))
    for param in plan["parameters"]:
        availability, data_owners = parameter_binding_summary(plan, param["parameter_name"])
        privacy = []
        if param.get("cardinality_risk") != "low":
            privacy.append(localized(plan, f"Cardinality risk: {param.get('cardinality_risk')}", f"Risque de cardinalité : {param.get('cardinality_risk')}"))
        if param.get("pii_risk") != "low":
            privacy.append(localized(plan, f"PII risk: {param.get('pii_risk')}", f"Risque de données personnelles : {param.get('pii_risk')}"))
        if param.get("consent_dependency"):
            privacy.append(localized(plan, f"Consent: {param.get('consent_dependency')}", f"Consentement : {param.get('consent_dependency')}"))
        if param.get("scope") == "implementation" and param.get("pii_risk") in {"medium", "high"}:
            privacy.append(localized(plan, "Implementation-only: do not map to ordinary GA4 parameters", "Implémentation uniquement : ne pas mapper vers les paramètres GA4 ordinaires"))
        register = localized(plan, "Yes", "Oui") if param.get("register_custom_definition") else localized(plan, "No", "Non")
        ws.append([
            param["parameter_name"],
            param["display_name"],
            localized_enum(plan, param["scope"]),
            param["type"],
            param["description"],
            parameter_value_rules(param),
            param.get("example_value", ""),
            availability or localized(plan, "Not used by an event", "Non utilisé par un événement"),
            data_owners or localized(plan, "Not assigned", "Non attribué"),
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
    title(ws, localized(plan, "Event Matrix", "Matrice des événements"), localized(plan, "Main tracking plan. One event slot is one reusable event definition; ecommerce blocks stay separate.", "Plan de marquage principal. Chaque emplacement décrit un événement réutilisable ; les blocs ecommerce restent séparés."), max_col)
    for slot_index, start_col in enumerate(matrix_value_columns(), 1):
        ws.merge_cells(start_row=4, start_column=start_col, end_row=4, end_column=start_col + 1)
        ws.cell(4, start_col, localized(plan, f"Event slot {slot_index}", f"Événement {slot_index}"))
        for column in (start_col, start_col + 1):
            slot_cell = ws.cell(4, column)
            slot_cell.fill = PatternFill("solid", fgColor=GREEN)
            slot_cell.font = Font(bold=True)
            slot_cell.alignment = CENTER
    slot_headers: list[str] = []
    for _ in range(EVENT_SLOT_COUNT):
        slot_headers.extend([
            localized(plan, "Expected value / rule", "Valeur attendue / règle"),
            localized(plan, "Requirement / availability", "Exigence / disponibilité"),
        ])
    ws.append([localized(plan, "Field / parameter path", "Champ / chemin du paramètre"), "Type", *slot_headers])
    header(ws, 5, max_col)

    parameter_types = {param["parameter_name"]: param["type"] for param in plan["parameters"]}
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in plan["events"]:
        grouped[(primary_journey_id(event), event_family(event))].append(event)

    block_index = 1
    for (journey_id, family), events in grouped.items():
        events.sort(key=lambda event: (event.get("display_order", 0), event.get("event_name", "")))
        for chunk_index in range(0, len(events), EVENT_SLOT_COUNT):
            chunk = events[chunk_index:chunk_index + EVENT_SLOT_COUNT]
            block_title = f"J-{block_index:03d} - {journey_names.get(journey_id, journey_id)} - {family}"
            row = [block_title, ""]
            for event in chunk:
                row.extend([event["event_name"], ""])
            row.extend([""] * (max_col - len(row)))
            ws.append(row)

            standard_rows = [
                ("event_classification", "string", lambda event: event["classification"]),
                ("specification_status", "string", lambda event: event.get("evidence_basis", {}).get("status", "")),
                ("journeys", "string", lambda event: " | ".join(
                    journey_names.get(event_journey_id, event_journey_id)
                    for event_journey_id in event.get("journey_ids", [])
                )),
                ("journey_stage", "string", lambda event: event.get("journey_stage", "")),
                ("event_summary", "string", lambda event: event.get("event_summary", "")),
                ("trigger", "string", lambda event: event["trigger"]),
                ("event", "string", transport_event_name),
            ]
            for variable, value_type, resolver in standard_rows:
                matrix_row = [variable, value_type]
                for event in chunk:
                    matrix_row.extend([resolver(event), ""])
                matrix_row.extend([""] * (max_col - len(matrix_row)))
                ws.append(matrix_row)

            parameters = ordered_parameters_for_events(chunk)
            for parameter in parameters:
                matrix_row = [parameter, parameter_types.get(parameter, parameter_type(parameter))]
                for event in chunk:
                    binding = binding_for_parameter(event, parameter)
                    value = parameter_value(event, parameter) if binding is not None else "-"
                    matrix_row.extend([value, binding_status(plan, binding)])
                matrix_row.extend([""] * (max_col - len(matrix_row)))
                ws.append(matrix_row)
            block_index += 1

    widths = [34, 18] + ([38, 22] * EVENT_SLOT_COUNT)
    set_widths(ws, widths)
    ws.freeze_panes = "C6"
    ws.auto_filter.ref = f"A5:{get_column_letter(max_col)}{ws.max_row}"
    style_cells(ws)
    style_event_matrix_rows(ws)


def build_datalayer_examples(wb: Workbook, plan: dict[str, Any]) -> None:
    ws = wb.create_sheet("04 DataLayer Examples")
    title(ws, localized(plan, "DataLayer Examples", "Exemples dataLayer"), localized(plan, "Complete developer examples aligned with the Event Matrix and final GA4 payload.", "Exemples complets pour les développeurs, alignés avec la matrice et le payload GA4 final."), 7)
    headers = [localized(plan, "Journey", "Parcours"), "Event", localized(plan, "Evidence", "Preuve"), localized(plan, "Trigger", "Déclencheur"), localized(plan, "dataLayer.push example", "Exemple dataLayer.push"), localized(plan, "GTM and GA4 mapping", "Mapping GTM et GA4"), localized(plan, "Implementation notes", "Notes d'implémentation")]
    ws.append(headers)
    header(ws, 3, len(headers))
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}

    for event in plan["events"]:
        notes = str(event.get("implementation_notes", ""))
        if event.get("classification") == "recommended_ecommerce":
            notes = f"{localized(plan, 'Official GA4 ecommerce event.', 'Événement ecommerce GA4 officiel.')} {notes}".strip()
        elif event.get("classification") == "custom":
            notes = f"{localized(plan, 'Custom GA4 event using the project dataLayer convention.', 'Événement GA4 personnalisé utilisant la convention dataLayer du projet.')} {notes}".strip()
        timing = str(event.get("data_layer", {}).get("consent_timing", ""))
        if timing:
            notes = f"{localized(plan, 'CMP sequence', 'Séquence CMP')}: {timing}. {notes}".strip()
        ws.append([
            " | ".join(
                journey_names.get(journey_id, journey_id)
                for journey_id in event.get("journey_ids", [])
            ),
            event["event_name"],
            event.get("evidence_basis", {}).get("status", ""),
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
    capture = plan["screenshot_capture"]
    capture_outcome = str(capture["outcome"])
    title(ws, localized(plan, "Screenshot Register", "Registre des captures"), str(capture["delivery_notice"]), 8)
    if capture_outcome in {"blocked", "partially_captured"}:
        ws.cell(2, 1).fill = PatternFill("solid", fgColor=RED)
        ws.cell(2, 1).font = Font(color="9C1C1C", bold=True, size=11)
    ws.append([localized(plan, "Journey", "Parcours"), "Event(s)", localized(plan, "Screenshot preview", "Aperçu de la capture"), localized(plan, "Page / component", "Page / composant"), "URL / route", localized(plan, "Capture objective", "Objectif de la capture"), localized(plan, "Status", "Statut"), "Notes"])
    header(ws, 3, 8)
    journey_names = {brief["journey_id"]: brief["journey_name"] for brief in plan["measurement_brief"]}
    events_by_id = {event["event_id"]: event for event in plan["events"]}
    files_by_name = screenshot_files(screenshot_dir)
    preview_dir = preview_dir or (screenshot_dir / "_workbook_previews" if screenshot_dir else None)

    image_rows: list[tuple[int, Path, dict[str, Any]]] = []
    for evidence in plan["screenshot_evidence"]:
        related_events = [events_by_id[event_id] for event_id in evidence["event_ids"] if event_id in events_by_id]
        event_names = [event["event_name"] for event in related_events]
        journeys = list(dict.fromkeys(
            journey_names.get(journey_id, journey_id)
            for event in related_events
            for journey_id in event.get("journey_ids", [])
        ))
        screenshot_path = resolve_screenshot(evidence, files_by_name)
        notes = str(evidence.get("notes", ""))
        status = str(evidence.get("status", ""))
        if status in {"captured", "shared_evidence"} and not screenshot_path:
            raise ValueError(
                f"Screenshot evidence '{evidence['evidence_id']}' is marked as {status}, but its file "
                f"'{evidence.get('file_name', '')}' was not found. Capture or supply the image before delivery, "
                "or mark the capture outcome and affected evidence as blocked."
            )
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
        if status in {"captured", "shared_evidence"} and screenshot_path and preview_dir:
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
    if plan.get("screenshot_capture", {}).get("requirement") != "not_requested":
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
