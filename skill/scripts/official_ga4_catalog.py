from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


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
