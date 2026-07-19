from __future__ import annotations

import hashlib
import html
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tracking_plan_contract import event_parameter_bindings, event_parameter_names

RECOMMENDED_EVENTS_URL = "https://developers.google.com/analytics/devguides/collection/ga4/reference/events"
ECOMMERCE_IMPLEMENTATION_URL = "https://developers.google.com/analytics/devguides/collection/ga4/ecommerce"
AUTOMATIC_EVENTS_URL = "https://support.google.com/analytics/answer/9234069?hl=en"
ENHANCED_MEASUREMENT_URL = "https://support.google.com/analytics/answer/9216061?hl=en"
EVENT_PARAMETERS_URL = "https://support.google.com/analytics/table/13594742?hl=en"

OFFICIAL_EVENT_CLASSES = {"automatic", "enhanced_measurement", "recommended", "recommended_ecommerce"}
OFFICIAL_PARAMETER_CLASSES = {
    "ga4_auto_collected_parameter",
    "ga4_native_parameter",
    "ga4_recommended_parameter",
    "ga4_ecommerce_parameter",
    "ga4_ecommerce_item_parameter",
}

ECOMMERCE_TRIGGER_SECTIONS = {
    "view_item_list": "Implementation > Select an item from a list",
    "select_item": "Implementation > Select an item from a list",
    "view_item": "Implementation > View item details",
    "add_to_wishlist": "Implementation > Add or remove an item from a shopping cart",
    "add_to_cart": "Implementation > Add or remove an item from a shopping cart",
    "view_cart": "Implementation > Add or remove an item from a shopping cart",
    "remove_from_cart": "Implementation > Add or remove an item from a shopping cart",
    "begin_checkout": "Implementation > Initiate the checkout process",
    "add_shipping_info": "Implementation > Initiate the checkout process",
    "add_payment_info": "Implementation > Initiate the checkout process",
    "purchase": "Implementation > Make a purchase or issue a refund",
    "refund": "Implementation > Make a purchase or issue a refund",
    "view_promotion": "Implementation > Apply promotions",
    "select_promotion": "Implementation > Apply promotions",
}

ECOMMERCE_TRIGGER_GUIDANCE = {
    "view_item_list": "When a user is presented with a list of results, send a view_item_list event including an items array parameter containing the displayed items.",
    "select_item": "Once a user selects an item from the list, send the select_item event with the selected item in an items array parameter.",
    "view_item": "To measure how many times item details are viewed, send a view_item event whenever a user views an item's details screen.",
    "add_to_cart": "Measure an item being added to a shopping cart by sending an add_to_cart event with the relevant items in an items array.",
    "add_to_wishlist": "You can also measure when an item is added to a wishlist by sending an add_to_wishlist event with the relevant items in an items array.",
    "view_cart": "When a user subsequently views the cart, send the view_cart event with all items in the cart.",
    "remove_from_cart": "To measure when a user removes an item from a cart, send the remove_from_cart event.",
    "begin_checkout": "Measure the first step in a checkout process by sending a begin_checkout event with one or more items defined with the relevant fields.",
    "add_shipping_info": "When a user proceeds to the next step in the checkout process and adds shipping information, send an add_shipping_info event.",
    "add_payment_info": "Send the add_payment_info event when a user submits their payment information.",
    "purchase": "Measure a purchase by sending a purchase event with one or more items defined with the relevant fields.",
    "refund": "Measure refunds by sending a refund event with the relevant transaction_id specified and one or more items defined with item_id and quantity.",
    "view_promotion": "Promotion impressions are typically measured with the initial screen view by sending the view_promotion event with an items parameter to specify the promoted item.",
    "select_promotion": "To indicate a user clicked on a promotion, send a select_promotion event with that item as an item parameter.",
}

STANDARD_EVENT_OFFICIAL_SEMANTICS = {
    "page_view": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Page views > page_view",
        "definition": "This event signifies that the page loaded or the active site changed the browser history state.",
        "trigger": "Each time the page loads or the browser history state is changed by the active site.",
        "official_trigger": "each time the page loads or the browser history state is changed by the active site",
        "parameters": ("page_location", "page_referrer"),
    },
    "first_visit": {
        "source_url": AUTOMATIC_EVENTS_URL,
        "source_section": "Automatically collected events > first_visit",
        "definition": "This event signifies the first time a user visits a website with Analytics enabled.",
        "trigger": "The first time a user visits a website with Analytics enabled.",
        "official_trigger": "the first time a user visits a website or launches an Android instant app with Analytics enabled",
        "parameters": (
            "client_id",
            "ga_session_id",
            "ga_session_number",
            "ignore_referrer",
            "page_location",
            "page_referrer",
            "page_title",
            "traffic_type",
        ),
    },
    "session_start": {
        "source_url": AUTOMATIC_EVENTS_URL,
        "source_section": "Automatically collected events > session_start",
        "definition": "This event signifies that a user engaged with the website and GA4 started a session.",
        "trigger": "When a user engages the website and GA4 starts a session.",
        "official_trigger": "when a user engages the app or website",
        "parameters": (
            "client_id",
            "ga_session_id",
            "ga_session_number",
            "ignore_referrer",
            "page_location",
            "page_referrer",
            "page_title",
            "traffic_type",
        ),
    },
    "user_engagement": {
        "source_url": AUTOMATIC_EVENTS_URL,
        "source_section": "Automatically collected events > user_engagement",
        "definition": "This event signifies that the webpage was in focus for at least one second.",
        "trigger": "When the webpage is in focus for at least one second.",
        "official_trigger": "when the app is in the foreground or webpage is in focus for at least one second",
        "parameters": ("engagement_time_msec",),
    },
    "scroll": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Scrolls > scroll",
        "definition": "This event signifies the first time a user reaches the bottom of a page, when 90% vertical depth becomes visible.",
        "trigger": "The first time a user reaches the bottom of each page, when 90% vertical depth becomes visible.",
        "official_trigger": "the first time a user reaches the bottom of each page (i.e., when a 90% vertical depth becomes visible)",
        "parameters": ("engagement_time_msec",),
    },
    "click": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Outbound clicks > click",
        "definition": "This event signifies that a user clicked a link leading away from the current domain to another website.",
        "trigger": "Each time a user clicks a link that leads away from the current domain to another website.",
        "official_trigger": "each time a user clicks a link that leads away from the current domain and to another website",
        "parameters": ("link_classes", "link_domain", "link_id", "link_url", "outbound"),
    },
    "view_search_results": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Site search > view_search_results",
        "definition": "This event signifies that a user was presented with a search results page identified by a configured URL query parameter.",
        "trigger": "Each time a user is presented with a search results page identified by a configured URL query parameter.",
        "official_trigger": "each time a user is presented with a search results page, as indicated by the presence of a URL query parameter",
        "parameters": ("search_term",),
    },
    "video_start": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Video engagement > video_start",
        "definition": "This event signifies that a supported embedded YouTube video started playing.",
        "trigger": "When an embedded YouTube video with JavaScript API support starts playing.",
        "official_trigger": "when the video starts playing",
        "parameters": (
            "video_current_time",
            "video_duration",
            "video_percent",
            "video_provider",
            "video_title",
            "video_url",
            "visible",
        ),
    },
    "video_progress": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Video engagement > video_progress",
        "definition": "This event signifies that a supported embedded YouTube video passed 10%, 25%, 50%, or 75% of its duration.",
        "trigger": "When an embedded YouTube video with JavaScript API support passes 10%, 25%, 50%, or 75% of its duration.",
        "official_trigger": "when the video progresses past 10%, 25%, 50%, and 75% duration time",
        "parameters": (
            "video_current_time",
            "video_duration",
            "video_percent",
            "video_provider",
            "video_title",
            "video_url",
            "visible",
        ),
    },
    "video_complete": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Video engagement > video_complete",
        "definition": "This event signifies that a supported embedded YouTube video ended.",
        "trigger": "When an embedded YouTube video with JavaScript API support ends.",
        "official_trigger": "when the video ends",
        "parameters": (
            "video_current_time",
            "video_duration",
            "video_percent",
            "video_provider",
            "video_title",
            "video_url",
            "visible",
        ),
    },
    "file_download": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > File downloads > file_download",
        "definition": "This event signifies that a user clicked a link to a file with a common supported download extension.",
        "trigger": "When a user clicks a link to a file whose extension matches the enhanced-measurement download list.",
        "official_trigger": "when a user clicks a link leading to a file (with a common file extension) of the following types",
        "parameters": ("file_extension", "file_name", "link_classes", "link_id", "link_text", "link_url"),
    },
    "form_start": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Form interactions > form_start",
        "definition": "This event signifies the first time a user interacted with a form in a session.",
        "trigger": "The first time a user interacts with a form in a session.",
        "official_trigger": "the first time a user interacts with a form in a session",
        "parameters": ("form_id", "form_name", "form_destination"),
    },
    "form_submit": {
        "source_url": ENHANCED_MEASUREMENT_URL,
        "source_section": "Events measurement and parameters > Form interactions > form_submit",
        "definition": "This event signifies that a user submitted a form.",
        "trigger": "When the user submits a form.",
        "official_trigger": "when the user submits a form",
        "parameters": ("form_id", "form_name", "form_destination", "form_submit_text"),
    },
}


def clean_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value)
    value = re.sub(r"</p>|</li>|</td>|</tr>", " ", value)
    value = re.sub(r"<.*?>", "", value)
    return " ".join(html.unescape(value).split())


def _parameter_rows(fragment: str, scope: str) -> list[dict[str, str]]:
    parameters: list[dict[str, str]] = []
    for row in re.findall(r"<tr>(.*?)</tr>", fragment, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        if len(cells) < 5 or clean_html(cells[0]).lower() == "name":
            continue
        parameters.append(
            {
                "name": clean_html(cells[0]),
                "scope": scope,
                "type": clean_html(cells[1]),
                "required": clean_html(cells[2]),
                "example": clean_html(cells[3]),
                "description": clean_html(cells[4]),
            }
        )
    return parameters


def parse_catalog_html(page: str) -> tuple[list[dict[str, Any]], str]:
    sections = [(match.start(), clean_html(match.group(2))) for match in re.finditer(r'<h2[^>]*id="([^"]+)"[^>]*>(.*?)</h2>', page, re.S)]
    sections.append((len(page), "END"))
    events: list[dict[str, Any]] = []
    headings = list(re.finditer(r'<h3[^>]*id="([^"]+)"[^>]*>\s*<code[^>]*>([^<]+)</code>\s*</h3>', page, re.S))
    for index, match in enumerate(headings):
        event_name = clean_html(match.group(2))
        position = match.start()
        section_name = next((sections[i][1] for i in range(len(sections) - 1) if sections[i][0] <= position < sections[i + 1][0]), "")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(page)
        next_section = next((section[0] for section in sections if section[0] > position), end)
        block = page[match.end() : min(end, next_section)]
        description_match = re.search(r"<p>(.*?)</p>", block, re.S)
        description = clean_html(description_match.group(1)) if description_match else ""
        item_heading = re.search(r"<h4[^>]*>\s*(?:<[^>]+>\s*)*Item parameters", block, re.I | re.S)
        event_block = block[: item_heading.start()] if item_heading else block
        item_block = block[item_heading.end() :] if item_heading else ""
        parameters = _parameter_rows(event_block, "event")
        parameters.extend(_parameter_rows(item_block, "item"))
        events.append({"event": event_name, "group": section_name, "description": description, "parameters": parameters})
    updated_match = re.search(r"Last updated\s+(\d{4}-\d{2}-\d{2})\s+UTC", page)
    return events, updated_match.group(1) if updated_match else ""


def load_catalog(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_scenario_library(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_parameter_library(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def normalize_parameter_path(value: str) -> tuple[str, str]:
    if value.startswith("items[]."):
        return value.split(".", 1)[1], "item"
    return value, "event"


def normalize_type(value: Any) -> str:
    normalized = normalize_text(value)
    if normalized.startswith("array"):
        return "array"
    if normalized in {"integer", "int"}:
        return "number"
    return normalized


def normalize_requiredness(value: Any) -> str:
    normalized = normalize_text(value)
    if normalized in {"yes", "required"}:
        return "required"
    if normalized.startswith("yes") or "one of" in normalized or "required if" in normalized:
        return "conditional"
    return "optional"


def catalog_event(catalog: list[dict[str, Any]], event_name: str) -> dict[str, Any] | None:
    return next((event for event in catalog if event.get("event") == event_name), None)


def event_parameter(
    catalog: list[dict[str, Any]],
    event_name: str,
    parameter_path: str,
) -> dict[str, Any] | None:
    event = catalog_event(catalog, event_name)
    if not event:
        return None
    name, scope = normalize_parameter_path(parameter_path)
    return next(
        (
            parameter
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
            and parameter.get("name") == name
            and str(parameter.get("scope") or "event") == scope
        ),
        None,
    )


def source_url_for_event(event_name: str) -> str:
    return f"{RECOMMENDED_EVENTS_URL}#{event_name}"


def resolve_event_semantics(
    event_name: str,
    classification: str,
    recommended_catalog: list[dict[str, Any]],
    scenario_library: dict[str, Any],
) -> dict[str, str] | None:
    if classification in {"recommended", "recommended_ecommerce"}:
        event = catalog_event(recommended_catalog, event_name)
        if not event:
            return None
        trigger_section = ECOMMERCE_TRIGGER_SECTIONS.get(event_name)
        trigger_guidance = ECOMMERCE_TRIGGER_GUIDANCE.get(event_name)
        return {
            "definition": str(event.get("description", "")).strip(),
            "trigger_guidance": trigger_guidance or str(event.get("description", "")).strip(),
            "source_url": source_url_for_event(event_name),
            "source_section": f"{event.get('group', 'Recommended events')} > {event_name}",
            "source_locator": event_name,
            "trigger_source_url": ECOMMERCE_IMPLEMENTATION_URL if trigger_section else source_url_for_event(event_name),
            "trigger_source_section": trigger_section or f"{event.get('group', 'Recommended events')} > {event_name}",
            "trigger_source_locator": f"Instruction immediately preceding the {event_name} implementation example" if trigger_section else event_name,
        }

    if classification in {"automatic", "enhanced_measurement"}:
        event = next(
            (
                item
                for item in scenario_library.get("standard_events", [])
                if isinstance(item, dict) and item.get("event") == event_name
            ),
            None,
        )
        if not event:
            return None
        source_url = str(event.get("source_url", "")).strip() or (
            ENHANCED_MEASUREMENT_URL
            if classification == "enhanced_measurement" or "enhanced" in str(event.get("group", ""))
            else AUTOMATIC_EVENTS_URL
        )
        source_section = str(event.get("source_section", "")).strip() or f"Events measurement and parameters > {event_name}"
        return {
            "definition": str(event.get("description") or event.get("trigger", "")).strip(),
            "trigger_guidance": str(event.get("trigger", "")).strip(),
            "source_url": source_url,
            "source_section": source_section,
            "source_locator": event_name,
            "trigger_source_url": source_url,
            "trigger_source_section": source_section,
            "trigger_source_locator": event_name,
        }
    return None


def _native_parameter_lookup(parameter_library: dict[str, Any], parameter_path: str) -> dict[str, Any] | None:
    name, scope = normalize_parameter_path(parameter_path)
    return next(
        (
            item
            for item in parameter_library.get("official_parameter_definitions", [])
            if isinstance(item, dict)
            and item.get("parameter_name") == name
            and str(item.get("scope") or "event") == scope
        ),
        None,
    )


def resolve_parameter_semantics(
    parameter_path: str,
    classification: str,
    event_names: list[str],
    recommended_catalog: list[dict[str, Any]],
    parameter_library: dict[str, Any],
) -> list[dict[str, str]]:
    resolved: list[dict[str, str]] = []
    for event_name in event_names:
        parameter = event_parameter(recommended_catalog, event_name, parameter_path)
        event = catalog_event(recommended_catalog, event_name)
        if not parameter or not event:
            continue
        name, scope = normalize_parameter_path(parameter_path)
        resolved.append(
            {
                "event_name": event_name,
                "name": name,
                "scope": scope,
                "type": normalize_type(parameter.get("type")),
                "required": normalize_requiredness(parameter.get("required")),
                "required_raw": str(parameter.get("required", "")),
                "example": str(parameter.get("example", "")),
                "description": str(parameter.get("description", "")).strip(),
                "source_url": source_url_for_event(event_name),
                "source_section": f"{event.get('group', 'Recommended events')} > {event_name} > {'Item parameters' if scope == 'item' else 'Parameters'}",
                "source_locator": parameter_path,
            }
        )

    if resolved or classification not in OFFICIAL_PARAMETER_CLASSES:
        return resolved

    native = _native_parameter_lookup(parameter_library, parameter_path)
    if not native:
        return []
    name, scope = normalize_parameter_path(parameter_path)
    return [
        {
            "event_name": "",
            "name": name,
            "scope": scope,
            "type": normalize_type(native.get("type")),
            "required": str(native.get("required", "optional")),
            "required_raw": str(native.get("required", "optional")),
            "example": str(native.get("example", "")),
            "description": str(native.get("description", "")).strip(),
            "source_url": str(native.get("source_url") or EVENT_PARAMETERS_URL),
            "source_section": str(native.get("source_section") or "Analytics event parameters"),
            "source_locator": name,
        }
    ]


def parameter_event_names(plan: dict[str, Any], parameter_path: str) -> list[str]:
    return [
        str(event.get("event_name", ""))
        for event in plan.get("events", [])
        if isinstance(event, dict)
        and parameter_path in event_parameter_names(event)
        and event.get("classification") in OFFICIAL_EVENT_CLASSES
    ]


def source_id_for_url(url: str) -> str:
    parsed = urlparse(url)
    path = re.sub(r"[^a-z0-9]+", "_", parsed.path.lower()).strip("_")
    host = parsed.netloc.lower().replace("www.", "").split(".")[0]
    value = f"{host}_{path}".strip("_")
    return value[:80] or "official_source"


def ensure_documentation_source(
    plan: dict[str, Any],
    *,
    url: str,
    name: str,
    checked_for: str,
) -> str:
    parsed_url = urlparse(url)
    canonical_url = parsed_url._replace(fragment="").geturl()
    source_id = source_id_for_url(canonical_url)
    sources = plan.setdefault("documentation_sources_checked", [])
    existing = next(
        (
            source
            for source in sources
            if isinstance(source, dict)
            and (source.get("source_id") == source_id or str(source.get("url", "")) == canonical_url)
        ),
        None,
    )
    if existing is None:
        sources.append(
            {
                "source_id": source_id,
                "name": name,
                "url": canonical_url,
                "source_type": "official",
                "checked_for": checked_for,
                "checked_date": None,
                "language": "fr" if "hl=fr" in canonical_url.lower() else "en",
                "content_signature": "",
            }
        )
    else:
        existing.setdefault("source_id", source_id)
        existing.setdefault("checked_date", None)
        existing.setdefault("language", "fr" if "hl=fr" in canonical_url.lower() else "en")
        existing.setdefault("content_signature", "")
        checked_items = {
            item.strip()
            for item in str(existing.get("checked_for", "")).split(" | ")
            if item.strip()
        }
        checked_items.add(checked_for)
        existing["checked_for"] = " | ".join(sorted(checked_items))
    return source_id


def official_requirement_condition(parameter_record: dict[str, Any]) -> str:
    required = " ".join(str(parameter_record.get("required", "")).split()).strip()
    if "one of" in normalize_text(required):
        return required.rstrip(".") + "."
    description = " ".join(str(parameter_record.get("description", "")).split()).strip()
    clauses = [part.strip(" *") for part in re.split(r"\s+\*\s+|(?<=[.!?])\s+", description) if part.strip(" *")]
    conditions = [
        clause
        for clause in clauses
        if re.search(r"\b(?:required if|if .+ required|typically required|one of .+ required)\b", clause, re.I)
    ]
    return " ".join(clause.rstrip(".") + "." for clause in conditions)


def _translation_status(workbook_language: str, verification: dict[str, Any]) -> str:
    if workbook_language == "en":
        return "not_needed"
    return str(verification.get("translation_status", "analyst_translation"))


def _enrich_event_binding(
    event: dict[str, Any],
    binding: dict[str, Any],
    parameter_record: dict[str, Any],
    source_id: str,
    *,
    overwrite_official: bool,
) -> None:
    requirement = normalize_requiredness(parameter_record.get("required"))
    if overwrite_official or not binding.get("requirement"):
        binding["requirement"] = requirement
    if requirement == "conditional" and (overwrite_official or not str(binding.get("condition", "")).strip()):
        condition = official_requirement_condition(parameter_record)
        if condition:
            binding["condition"] = condition
    elif requirement != "conditional":
        binding.setdefault("condition", "")
    binding["official_source_id"] = source_id
    binding["official_source_locator"] = str(binding.get("parameter_name", ""))


def _enrich_official_event(
    result: dict[str, Any],
    event: dict[str, Any],
    resolution: dict[str, str],
    recommended_catalog: list[dict[str, Any]],
    workbook_language: str,
    *,
    overwrite_official: bool,
) -> None:
    if overwrite_official or not str(event.get("event_summary", "")).strip():
        event["event_summary"] = resolution["definition"]
    source_id = ensure_documentation_source(
        result,
        url=resolution["source_url"],
        name=f"GA4 event reference: {event.get('event_name', '')}",
        checked_for=f"Definition and parameters for {event.get('event_name', '')}",
    )
    trigger_source_id = ensure_documentation_source(
        result,
        url=resolution["trigger_source_url"],
        name=f"GA4 implementation guidance: {event.get('event_name', '')}",
        checked_for=f"Trigger guidance for {event.get('event_name', '')}",
    )
    verification = event.setdefault("official_verification", {})
    verification.update(
        {
            "source_id": source_id,
            "canonical_wording": resolution["definition"],
            "canonical_trigger_wording": resolution["trigger_guidance"],
            "source_section": resolution["source_section"],
            "source_locator": resolution["source_locator"],
            "trigger_source_id": trigger_source_id,
            "trigger_source_section": resolution["trigger_source_section"],
            "trigger_source_locator": resolution["trigger_source_locator"],
            "translation_status": _translation_status(workbook_language, verification),
        }
    )
    for key in ("source_url", "checked_date", "source_language", "trigger_source_url"):
        verification.pop(key, None)

    event_name = str(event.get("event_name", ""))
    for binding in event_parameter_bindings(event):
        parameter_record = event_parameter(
            recommended_catalog,
            event_name,
            str(binding.get("parameter_name", "")),
        )
        if parameter_record:
            _enrich_event_binding(
                event,
                binding,
                parameter_record,
                source_id,
                overwrite_official=overwrite_official,
            )


def _enrich_event(
    result: dict[str, Any],
    event: dict[str, Any],
    recommended_catalog: list[dict[str, Any]],
    scenario_library: dict[str, Any],
    workbook_language: str,
    *,
    overwrite_official: bool,
) -> None:
    resolution = resolve_event_semantics(
        str(event.get("event_name", "")),
        str(event.get("classification", "")),
        recommended_catalog,
        scenario_library,
    )
    if resolution:
        _enrich_official_event(
            result,
            event,
            resolution,
            recommended_catalog,
            workbook_language,
            overwrite_official=overwrite_official,
        )


def _enrich_official_parameter(
    result: dict[str, Any],
    parameter: dict[str, Any],
    resolution: dict[str, str],
    workbook_language: str,
    *,
    overwrite_official: bool,
) -> None:
    parameter_path = str(parameter.get("parameter_name", ""))
    if overwrite_official or not str(parameter.get("description", "")).strip():
        parameter["description"] = resolution["description"]
    if overwrite_official and resolution.get("type"):
        parameter["type"] = resolution["type"]
    parameter.pop("required", None)
    if not str(parameter.get("example_value", "")).strip() and resolution.get("example"):
        parameter["example_value"] = resolution["example"]

    source_id = ensure_documentation_source(
        result,
        url=resolution["source_url"],
        name=f"GA4 parameter reference: {parameter_path}",
        checked_for=f"Definition, type, and conditions for {parameter_path}",
    )
    verification = parameter.setdefault("official_verification", {})
    verification.update(
        {
            "source_id": source_id,
            "canonical_wording": resolution["description"],
            "source_section": resolution["source_section"],
            "source_locator": resolution["source_locator"],
            "translation_status": _translation_status(workbook_language, verification),
        }
    )
    for key in ("source_url", "checked_date", "source_language", "trigger_source_url"):
        verification.pop(key, None)


def enrich_plan_official_semantics(
    plan: dict[str, Any],
    recommended_catalog: list[dict[str, Any]],
    scenario_library: dict[str, Any],
    parameter_library: dict[str, Any],
    *,
    overwrite_official: bool = True,
) -> dict[str, Any]:
    result = deepcopy(plan)
    workbook_language = str(result.get("language_policy", {}).get("workbook_language", "en"))
    for event in result.get("events", []):
        if isinstance(event, dict):
            _enrich_event(
                result,
                event,
                recommended_catalog,
                scenario_library,
                workbook_language,
                overwrite_official=overwrite_official,
            )

    for parameter in result.get("parameters", []):
        if not isinstance(parameter, dict):
            continue
        classification = str(parameter.get("classification", ""))
        if classification not in OFFICIAL_PARAMETER_CLASSES:
            continue
        parameter_path = str(parameter.get("parameter_name", ""))
        resolutions = resolve_parameter_semantics(
            parameter_path,
            classification,
            parameter_event_names(result, parameter_path),
            recommended_catalog,
            parameter_library,
        )
        if not resolutions:
            continue
        _enrich_official_parameter(
            result,
            parameter,
            resolutions[0],
            workbook_language,
            overwrite_official=overwrite_official,
        )
    return result


def event_parameter_order(catalog: list[dict[str, Any]], event_name: str) -> list[str]:
    event = next((item for item in catalog if item.get("event") == event_name), None)
    if not event:
        return []
    parameters = event.get("parameters", [])
    if any(parameter.get("scope") for parameter in parameters if isinstance(parameter, dict)):
        return [str(parameter["name"]) for parameter in parameters if isinstance(parameter, dict) and parameter.get("scope") == "event"]
    result: list[str] = []
    for parameter in parameters:
        if not isinstance(parameter, dict) or not parameter.get("name"):
            continue
        result.append(str(parameter["name"]))
        if parameter.get("name") == "items":
            break
    return result


def catalog_signature(catalog: list[dict[str, Any]]) -> dict[str, tuple[tuple[str, str, str, str], ...]]:
    signature: dict[str, tuple[tuple[str, str, str, str], ...]] = {}
    for event in catalog:
        name = str(event.get("event", ""))
        if not name:
            continue
        signature[name] = tuple(
            (
                str(parameter.get("name", "")),
                str(parameter.get("scope", "")),
                str(parameter.get("type", "")),
                str(parameter.get("required", "")),
            )
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
        )
    return signature


def catalog_semantic_signature(catalog: list[dict[str, Any]]) -> dict[str, tuple[Any, ...]]:
    """Include human wording so live drift checks catch semantic changes, not only schema changes."""
    signature: dict[str, tuple[Any, ...]] = {}
    for event in catalog:
        name = str(event.get("event", ""))
        if not name:
            continue
        parameters = tuple(
            (
                str(parameter.get("name", "")),
                str(parameter.get("scope", "")),
                str(parameter.get("type", "")),
                str(parameter.get("required", "")),
                str(parameter.get("example", "")),
                str(parameter.get("description", "")),
            )
            for parameter in event.get("parameters", [])
            if isinstance(parameter, dict)
        )
        signature[name] = (
            str(event.get("group", "")),
            str(event.get("description", "")),
            parameters,
        )
    return signature


def catalog_receipt_signature(catalog: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        {
            "shape": catalog_signature(catalog),
            "semantics": catalog_semantic_signature(catalog),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
