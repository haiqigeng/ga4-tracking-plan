from __future__ import annotations

import html
import re
from typing import Any


def clean_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"</p>|</li>|</td>|</tr>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<.*?>", "", value, flags=re.DOTALL)
    return " ".join(html.unescape(value).split())


def parameter_rows(fragment: str, scope: str) -> list[dict[str, str]]:
    parameters: list[dict[str, str]] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", fragment, flags=re.DOTALL | re.IGNORECASE):
        cells = re.findall(
            r"<t[dh][^>]*>(.*?)</t[dh]>",
            row,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if len(cells) < 5 or clean_html(cells[0]).casefold() == "name":
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


def parse_catalog_html(page: str) -> list[dict[str, Any]]:
    sections = [
        (match.start(), clean_html(match.group(2)))
        for match in re.finditer(
            r'<h2[^>]*id="([^"]+)"[^>]*>(.*?)</h2>',
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )
    ]
    sections.append((len(page), ""))
    headings = list(
        re.finditer(
            r'<h3[^>]*id="([^"]+)"[^>]*>\s*<code[^>]*>([^<]+)</code>\s*</h3>',
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )
    )
    events: list[dict[str, Any]] = []
    for index, match in enumerate(headings):
        position = match.start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(page)
        next_section = next(
            (section_position for section_position, _ in sections if section_position > position),
            end,
        )
        block = page[match.end() : min(end, next_section)]
        description_match = re.search(r"<p[^>]*>(.*?)</p>", block, flags=re.DOTALL | re.IGNORECASE)
        item_heading = re.search(
            r"<h4[^>]*>\s*(?:<[^>]+>\s*)*Item parameters",
            block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        event_block = block[: item_heading.start()] if item_heading else block
        item_block = block[item_heading.end() :] if item_heading else ""
        group = next(
            (
                sections[item][1]
                for item in range(len(sections) - 1)
                if sections[item][0] <= position < sections[item + 1][0]
            ),
            "",
        )
        events.append(
            {
                "event": clean_html(match.group(2)),
                "group": group,
                "description": (
                    clean_html(description_match.group(1)) if description_match else ""
                ),
                "parameters": (
                    parameter_rows(event_block, "event")
                    + parameter_rows(item_block, "item")
                ),
            }
        )
    return events


def normalize(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().casefold()


def normalize_type(value: Any) -> str:
    result = normalize(value)
    if result.startswith("array"):
        return "array"
    if result in {"float", "double"}:
        return "number"
    return result
