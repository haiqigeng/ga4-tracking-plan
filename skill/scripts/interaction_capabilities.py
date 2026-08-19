from __future__ import annotations

import hashlib
import re
from typing import Any

from discover_site_journeys import signal_contains_phrase
from discovery_quality import relevant_forms


def _identifier(value: str, maximum: int = 119) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"id_{normalized}".rstrip("_")
    return normalized[:maximum]


def _context(page: dict[str, Any]) -> dict[str, Any]:
    surfaces = page.get("page_surfaces", {}) if isinstance(page.get("page_surfaces"), dict) else {}
    counts = surfaces.get("semantic_counts", {}) if isinstance(surfaces.get("semantic_counts"), dict) else {}
    forms = relevant_forms(page)
    controls = [item for item in page.get("interactive_controls", []) if isinstance(item, dict)]
    control_parts = [
        " ".join(
            [
                str(item.get("type", "")),
                str(item.get("name", "")),
                str(item.get("id", "")),
                str(item.get("label", "")),
                " ".join(str(value) for value in item.get("option_labels", [])),
            ]
        )
        for item in controls
    ]
    form_parts = [
        " ".join(
            [
                str(form.get("id", "")),
                str(form.get("name", "")),
                *[
                    " ".join(str(field.get(key, "")) for key in ("name", "id", "label"))
                    for field in form.get("fields", [])
                    if isinstance(field, dict)
                ],
            ]
        )
        for form in forms
    ]
    return {
        "url": str(page.get("url", "")),
        "access_profile_id": str(page.get("access_profile_id", "public")),
        "role": str(page.get("role", "public")),
        "state_id": str(page.get("state_id", "entry")),
        "template": str(page.get("template", "unknown")),
        "counts": counts,
        "forms": forms,
        "controls": controls,
        "button_controls": [item for item in page.get("button_controls", []) if isinstance(item, dict)],
        "embedded_frames": [item for item in page.get("embedded_frames", []) if isinstance(item, dict)],
        "contact_handoffs": [item for item in page.get("contact_handoffs", []) if isinstance(item, dict)],
        "navigation_controls": [item for item in page.get("navigation_controls", []) if isinstance(item, dict)],
        "corpus": " ".join(
            [
                str(surfaces.get("title", "")),
                " ".join(str(value) for value in surfaces.get("headings", [])),
                str(surfaces.get("main_text", "")),
                *control_parts,
                *form_parts,
            ]
        ),
        "tab_count": int(counts.get("tab", 0) or 0)
        + sum(str(item.get("type", "")) == "tab" for item in controls),
        "tablist_count": int(counts.get("tablist", 0) or 0)
        + sum(str(item.get("type", "")) == "tablist" for item in controls),
    }


def _count(context: dict[str, Any], name: str) -> int:
    return int(context["counts"].get(name, 0) or 0)


def _has_phrase(context: dict[str, Any], *phrases: str) -> bool:
    return any(signal_contains_phrase(context["corpus"], phrase) for phrase in phrases)


def _capability(
    context: dict[str, Any],
    family: str,
    category: str,
    materiality: str,
    reason: str,
    evidence: list[str],
) -> dict[str, Any]:
    identity = f"{family}|{context['url']}"
    if context["access_profile_id"] != "public" or context["state_id"] != "entry":
        identity += f"|{context['access_profile_id']}|{context['role']}|{context['state_id']}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
    return {
        "capability_id": _identifier(f"capability_{family}_{digest}"),
        "family": family,
        "category": category,
        "materiality": materiality,
        "reason": reason,
        "evidence": sorted(set(evidence)),
    }


def _counted(
    context: dict[str, Any],
    count_name: str,
    family: str,
    category: str,
    reason: str,
    evidence_label: str,
) -> dict[str, Any] | None:
    count = _count(context, count_name)
    if not count:
        return None
    return _capability(
        context,
        family,
        category,
        "candidate",
        reason,
        [f"{evidence_label}:{count}"],
    )


def detect_interaction_capabilities(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one evidence record per family, never one event per control."""
    context = _context(page)
    capabilities: list[dict[str, Any] | None] = []

    if context["forms"] and (context["tab_count"] >= 2 or context["tablist_count"] >= 1):
        capabilities.append(
            _capability(
                context,
                "tabbed_form",
                "outcome",
                "material",
                "Distinct form tabs can represent different intents or outcomes and require an explicit shared-versus-separate measurement decision.",
                [
                    f"forms:{len(context['forms'])}",
                    f"tabs:{max(context['tab_count'], _count(context, 'tab'))}",
                ],
            )
        )

    locator_language = _has_phrase(
        context,
        "sur la carte",
        "on the map",
        "selectionnez une station",
        "select a store",
    )
    if context["template"] == "store_locator" and (
        _count(context, "map") or _count(context, "locator_result") or locator_language
    ):
        capabilities.append(
            _capability(
                context,
                "locator_selection",
                "interaction",
                "material",
                "A locator result or map selection is a distinct decision point after the search itself.",
                [
                    f"maps:{_count(context, 'map')}",
                    f"results:{_count(context, 'locator_result')}",
                ],
            )
        )

    has_accordion = _count(context, "details") or _count(context, "accordion")
    if has_accordion and (
        context["template"] == "support_or_contact" or _has_phrase(context, "faq")
    ):
        capabilities.append(
            _capability(
                context,
                "faq_accordion",
                "interaction",
                "candidate",
                "FAQ expansion may reveal unresolved support needs, but should be measured only when the resulting question is useful.",
                [
                    f"details:{_count(context, 'details')}",
                    f"accordions:{_count(context, 'accordion')}",
                ],
            )
        )

    if _has_phrase(context, "code promo", "promotion code", "coupon", "voucher"):
        capabilities.append(
            _capability(
                context,
                "coupon_application",
                "diagnostic",
                "material" if context["template"] in {"cart", "checkout"} else "candidate",
                "Coupon submission success and failure can explain conversion friction and discount use.",
                ["local control or field mentions a coupon/promotion code"],
            )
        )

    modal_openers = [
        item
        for item in context["button_controls"]
        if str(item.get("aria_haspopup", "")) == "dialog" or item.get("aria_controls")
    ]
    modal_count = max(_count(context, "dialog"), len(modal_openers))
    if modal_count:
        capabilities.append(
            _capability(
                context,
                "modal_dialog",
                "interaction",
                "candidate",
                "A modal can contain a material gated choice or form; its business purpose must be reviewed before measurement.",
                [f"dialogs_or_openers:{modal_count}"],
            )
        )

    capabilities.append(
        _counted(
            context,
            "download",
            "download",
            "outcome",
            "A download can be a meaningful outcome such as an application, brochure, or document acquisition.",
            "download_links",
        )
    )
    if _count(context, "error") or _has_phrase(
        context,
        "payment failed",
        "paiement refuse",
        "erreur de paiement",
        "une erreur est survenue",
    ):
        capabilities.append(
            _capability(
                context,
                "meaningful_error",
                "diagnostic",
                "material",
                "An observed business-process error can explain funnel loss and requires an explicit diagnostic decision.",
                [f"visible_error_regions:{_count(context, 'error')}"],
            )
        )

    if _has_phrase(context, "filter", "filtre", "sort", "trier", "tri"):
        capabilities.append(
            _capability(
                context,
                "filter_sort",
                "interaction",
                "candidate",
                "Applied filters or sorting may explain discovery behavior without requiring one event per control.",
                ["local filter or sort control"],
            )
        )

    if context["template"] == "configurator" and (context["forms"] or context["controls"]):
        capabilities.append(
            _capability(
                context,
                "configurator_progression",
                "progression",
                "material",
                "Meaningful configurator progression and completion require an explicit measurement decision.",
                [
                    f"forms:{len(context['forms'])}",
                    f"controls:{len(context['controls'])}",
                ],
            )
        )

    embedded_form_count = sum(
        int(item.get("form_count", 0) or 0)
        for item in context["embedded_frames"]
        if int(item.get("form_count", 0) or 0) > 0
    )
    if embedded_form_count:
        capabilities.append(
            _capability(
                context,
                "iframe_form",
                "progression",
                "material",
                "An embedded form or widget has its own progression and outcome states that require direct investigation.",
                [f"embedded_forms:{embedded_form_count}"],
            )
        )

    capabilities.append(
        _counted(
            context,
            "video",
            "video_media",
            "interaction",
            "Meaningful media engagement may support a content decision and needs an explicit measure-or-exclude decision.",
            "visible_media",
        )
    )
    if context["contact_handoffs"]:
        capabilities.append(
            _capability(
                context,
                "deliberate_contact_handoff",
                "outcome",
                "candidate",
                "A deliberate telephone, email, chat, or portal handoff can represent contact intent without creating a generic outbound-click inventory.",
                [f"contact_handoffs:{len(context['contact_handoffs'])}"],
            )
        )

    if context["template"] == "homepage" and context["navigation_controls"]:
        surfaces = sorted(
            {
                str(item.get("surface", ""))
                for item in context["navigation_controls"]
                if item.get("surface")
            }
        )
        capabilities.append(
            _capability(
                context,
                "navigation_surface",
                "interaction",
                "candidate",
                "Header, footer, menu, and drawer navigation need one bounded surface-level decision when navigation effectiveness is analysed.",
                [
                    f"navigation_controls:{len(context['navigation_controls'])}",
                    *[f"surface:{surface}" for surface in surfaces],
                ],
            )
        )

    if context["template"] == "search_results" and _count(context, "search_result"):
        capabilities.append(
            _capability(
                context,
                "search_result_selection",
                "outcome",
                "material",
                "Selecting a search result is a distinct discovery outcome after a submitted internal search.",
                [f"search_results:{_count(context, 'search_result')}"],
            )
        )
    if _count(context, "pagination"):
        capabilities.append(
            _capability(
                context,
                "pagination_load_more",
                "interaction",
                "candidate",
                "Pagination or load-more use may explain catalogue or content discovery depth without one event per button.",
                [f"pagination_controls:{_count(context, 'pagination')}"],
            )
        )

    aria_count = sum(
        str(item.get("type", "")) in {"combobox", "listbox", "switch"}
        for item in context["controls"]
    )
    if aria_count:
        capabilities.append(
            _capability(
                context,
                "custom_aria_control",
                "interaction",
                "candidate",
                "A custom ARIA choice control can reveal material states or value domains that native-control discovery would otherwise miss.",
                [f"custom_aria_controls:{aria_count}"],
            )
        )

    capabilities.extend(
        [
            _counted(
                context,
                "print_share",
                "print_share",
                "interaction",
                "Print or share controls are detect-only candidates unless a concrete content-distribution question makes them material.",
                "print_share_controls",
            ),
            _counted(
                context,
                "carousel",
                "carousel_selection",
                "interaction",
                "Carousel selection is a candidate only when the selected content or promotion supports a concrete decision.",
                "carousel_selection_controls",
            ),
        ]
    )
    return sorted(
        (item for item in capabilities if item is not None),
        key=lambda item: str(item["family"]),
    )
