import json
from pathlib import Path
from urllib.request import Request, urlopen
import html
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL_REFS = ROOT / "skill" / "references" / "03-rules"
OFFICIAL_JSON = SKILL_REFS / "library-ga4-recommended-events.json"
LIBRARY_JSON = SKILL_REFS / "library-ga4-event-scenarios.json"
LIBRARY_MD = SKILL_REFS / "library-ga4-event-scenarios.md"

SOURCES = [
    {
        "name": "GA4 automatically collected events",
        "type": "official",
        "url": "https://support.google.com/analytics/answer/9234069?hl=en",
        "used_for": "Automatic and enhanced-measurement web events and default parameters.",
    },
    {
        "name": "GA4 enhanced measurement events",
        "type": "official",
        "url": "https://support.google.com/analytics/answer/9216061?hl=en",
        "used_for": "Enhanced-measurement event triggers and parameters.",
    },
    {
        "name": "GA4 recommended events",
        "type": "official",
        "url": "https://developers.google.com/analytics/devguides/collection/ga4/reference/events",
        "used_for": "Full recommended event catalog and event-level parameters.",
    },
    {
        "name": "GA4 ecommerce measurement",
        "type": "official",
        "url": "https://developers.google.com/analytics/devguides/collection/ga4/ecommerce",
        "used_for": "Ecommerce dataLayer/gtag examples and items array structure.",
    },
    {
        "name": "GA4 event parameters",
        "type": "official",
        "url": "https://support.google.com/analytics/table/13594742?hl=en",
        "used_for": "Parameter reporting behavior for automatic, enhanced, and recommended events.",
    },
    {
        "name": "GA4 event setup",
        "type": "official",
        "url": "https://developers.google.com/analytics/devguides/collection/ga4/events",
        "used_for": "How recommended/custom events are configured with gtag.js or GTM.",
    },
    {
        "name": "GTM data layer",
        "type": "official",
        "url": "https://developers.google.com/tag-platform/tag-manager/datalayer",
        "used_for": "dataLayer purpose and dataLayer.push implementation rules.",
    },
    {
        "name": "GA4 custom events",
        "type": "official",
        "url": "https://support.google.com/analytics/answer/12229021?hl=en",
        "used_for": "Rule to prefer automatic/enhanced/recommended events before custom events.",
    },
    {
        "name": "GA4 event collection limits",
        "type": "official",
        "url": "https://support.google.com/analytics/answer/9267744?hl=en",
        "used_for": "Event naming length and event-parameter limits.",
    },
    {
        "name": "Simo Ahava GA4 ecommerce guide",
        "type": "trusted_practitioner",
        "url": "https://www.simoahava.com/analytics/google-analytics-4-ecommerce-guide-google-tag-manager/",
        "used_for": "Implementation judgement for GA4 ecommerce with GTM.",
    },
    {
        "name": "Simo Ahava GA4 events implementation guide",
        "type": "trusted_practitioner",
        "url": "https://www.simoahava.com/analytics/implementation-guide-events-google-analytics-4/",
        "used_for": "Custom-event design judgement and GA4 implementation considerations.",
    },
    {
        "name": "Analytics Mania GA4 custom events",
        "type": "trusted_practitioner",
        "url": "https://www.analyticsmania.com/post/how-to-track-custom-events-with-google-analytics-4/",
        "used_for": "Typical GTM custom-event patterns and reporting considerations.",
    },
    {
        "name": "Analytics Mania GTM data layer tutorial",
        "type": "trusted_practitioner",
        "url": "https://www.analyticsmania.com/post/ultimate-google-tag-manager-data-layer-tutorial/",
        "used_for": "Human explanation and practical dataLayer examples.",
    },
]


def clean(value):
    value = re.sub(r"<br\s*/?>", " ", value)
    value = re.sub(r"</p>|</li>|</td>|</tr>", " ", value)
    value = re.sub(r"<.*?>", "", value)
    value = html.unescape(value)
    return " ".join(value.split())


def fetch_recommended_events():
    url = "https://developers.google.com/analytics/devguides/collection/ga4/reference/events"
    text = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8", "ignore")
    sections = []
    for match in re.finditer(r'<h2[^>]*id="([^"]+)"[^>]*>(.*?)</h2>', text, re.S):
        sections.append((match.start(), clean(match.group(2))))
    sections.append((len(text), "END"))

    events = []
    for match in re.finditer(r'<h3[^>]*id="([^"]+)"[^>]*>\s*<code[^>]*>([^<]+)</code></h3>', text, re.S):
        event_name = clean(match.group(2))
        pos = match.start()
        section_name = ""
        for i in range(len(sections) - 1):
            if sections[i][0] <= pos < sections[i + 1][0]:
                section_name = sections[i][1]
                break
        next_positions = []
        for pattern in [r'<h3[^>]*id="', r'<h2[^>]*id="']:
            next_match = re.search(pattern, text[match.end() :], re.S)
            if next_match:
                next_positions.append(match.end() + next_match.start())
        end = min(next_positions) if next_positions else len(text)
        block = text[match.end() : end]
        description_match = re.search(r"<p>(.*?)</p>", block, re.S)
        description = clean(description_match.group(1)) if description_match else ""
        params = []
        for row in re.findall(r"<tr>(.*?)</tr>", block, re.S):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
            if len(cells) >= 5 and clean(cells[0]).lower() != "name":
                params.append(
                    {
                        "name": clean(cells[0]),
                        "type": clean(cells[1]),
                        "required": clean(cells[2]),
                        "example": clean(cells[3]),
                        "description": clean(cells[4]),
                    }
                )
        events.append({"event": event_name, "group": section_name, "description": description, "parameters": params})
    return events


STANDARD_EVENTS = [
    {
        "event": "page_view",
        "group": "automatic / enhanced measurement",
        "scenario": "page view, SPA route change",
        "trigger": "Page load or browser history state change.",
        "parameters": "page_location, page_referrer, page_title, engagement_time_msec",
        "implementation": "Usually automatic. Manually control only when SPA/infinite-scroll behavior requires it.",
    },
    {
        "event": "first_visit",
        "group": "automatic",
        "scenario": "new user acquisition",
        "trigger": "First visit from a user/client.",
        "parameters": "client_id, ga_session_id, ga_session_number, page_location, page_referrer, page_title",
        "implementation": "Automatic; do not implement manually.",
    },
    {
        "event": "session_start",
        "group": "automatic",
        "scenario": "session analysis",
        "trigger": "User starts or resumes a session.",
        "parameters": "client_id, ga_session_id, ga_session_number, page_location, page_referrer, page_title",
        "implementation": "Automatic; do not implement manually.",
    },
    {
        "event": "user_engagement",
        "group": "automatic",
        "scenario": "engagement time",
        "trigger": "Webpage is in focus for at least one second.",
        "parameters": "engagement_time_msec",
        "implementation": "Automatic; do not implement manually.",
    },
    {
        "event": "scroll",
        "group": "enhanced measurement",
        "scenario": "content engagement",
        "trigger": "First time a user reaches 90% vertical depth.",
        "parameters": "engagement_time_msec",
        "implementation": "Enhanced measurement. Custom scroll_depth event only if 25/50/75 thresholds are needed.",
    },
    {
        "event": "click",
        "group": "enhanced measurement",
        "scenario": "outbound link click",
        "trigger": "User clicks a link leading away from the current domain.",
        "parameters": "link_classes, link_domain, link_id, link_url, outbound",
        "implementation": "Enhanced measurement. Avoid duplicating with custom outbound_click unless needed.",
    },
    {
        "event": "view_search_results",
        "group": "enhanced measurement",
        "scenario": "search results page",
        "trigger": "Search results page is shown based on configured query parameter.",
        "parameters": "search_term, q_<additional key>",
        "implementation": "Enhanced measurement. Use recommended search for explicit submitted-search tracking.",
    },
    {
        "event": "video_start",
        "group": "enhanced measurement",
        "scenario": "YouTube embedded video",
        "trigger": "Supported YouTube video starts.",
        "parameters": "video_current_time, video_duration, video_percent, video_provider, video_title, video_url, visible",
        "implementation": "Enhanced measurement when YouTube JS API support exists.",
    },
    {
        "event": "video_progress",
        "group": "enhanced measurement",
        "scenario": "YouTube embedded video",
        "trigger": "Supported video passes 10%, 25%, 50%, or 75%.",
        "parameters": "video_current_time, video_duration, video_percent, video_provider, video_title, video_url, visible",
        "implementation": "Enhanced measurement when YouTube JS API support exists.",
    },
    {
        "event": "video_complete",
        "group": "enhanced measurement",
        "scenario": "YouTube embedded video",
        "trigger": "Supported video completes.",
        "parameters": "video_current_time, video_duration, video_percent, video_provider, video_title, video_url, visible",
        "implementation": "Enhanced measurement when YouTube JS API support exists.",
    },
    {
        "event": "file_download",
        "group": "enhanced measurement",
        "scenario": "downloadable file click",
        "trigger": "User clicks a common downloadable file extension.",
        "parameters": "file_extension, file_name, link_classes, link_id, link_text, link_url",
        "implementation": "Enhanced measurement. Custom file events only for gated downloads or special classifications.",
    },
    {
        "event": "form_start",
        "group": "enhanced measurement",
        "scenario": "form engagement",
        "trigger": "First time a user interacts with a form in a session.",
        "parameters": "form_id, form_name, form_destination",
        "implementation": "Enhanced measurement. Custom form_step events when multi-step funnel detail is required.",
    },
    {
        "event": "form_submit",
        "group": "enhanced measurement",
        "scenario": "form submission",
        "trigger": "User submits a form.",
        "parameters": "form_id, form_name, form_destination, form_submit_text",
        "implementation": "Enhanced measurement. Use generate_lead for validated lead success.",
    },
]


TYPICAL_CUSTOM_EVENTS = [
    {
        "event": "begin_quote",
        "scenario": "insurance, banking, telco, services quote funnels",
        "use_when": "User starts a quote flow but no lead has been generated yet.",
        "prefer_official_if": "Use generate_lead after a successful lead/quote submission.",
        "parameters": "quote_type, product_type, quote_entry_point, cta_location, cta_text",
    },
    {
        "event": "form_step_view",
        "scenario": "multi-step lead, signup, booking, checkout-like forms",
        "use_when": "A form step is displayed and enhanced measurement is too coarse.",
        "prefer_official_if": "Use form_start/form_submit when only generic form engagement is needed.",
        "parameters": "form_name, form_step, form_step_name, page_location",
    },
    {
        "event": "form_step_submit",
        "scenario": "multi-step forms and funnels",
        "use_when": "A step is completed before final submission.",
        "prefer_official_if": "Use generate_lead/sign_up/purchase when the final business outcome occurs.",
        "parameters": "form_name, form_step, form_step_name, validation_status",
    },
    {
        "event": "form_error",
        "scenario": "forms, checkout, quote funnels",
        "use_when": "User sees a validation or system error that affects conversion.",
        "prefer_official_if": "No direct GA4 recommended event fits. Avoid raw error text if it may contain PII.",
        "parameters": "form_name, form_step, error_type, field_name, error_code",
    },
    {
        "event": "filter_apply",
        "scenario": "listing pages, search results, catalogs, real estate, jobs",
        "use_when": "A filter materially changes the displayed results.",
        "prefer_official_if": "Use view_search_results/search if the interaction is a search query.",
        "parameters": "filter_category, filter_value, result_count, listing_type",
    },
    {
        "event": "sort_apply",
        "scenario": "listing pages, catalogs, search results",
        "use_when": "User changes result ordering.",
        "prefer_official_if": "No direct recommended event fits.",
        "parameters": "sort_type, previous_sort_type, result_count, listing_type",
    },
    {
        "event": "contact_intent",
        "scenario": "lead generation, support, local business",
        "use_when": "User clicks a contact CTA but does not submit a lead form.",
        "prefer_official_if": "Use generate_lead once a valid lead/contact form is submitted.",
        "parameters": "contact_method, cta_location, link_url, business_unit",
    },
    {
        "event": "account_access_intent",
        "scenario": "customer portals, insurance, banking, SaaS",
        "use_when": "User clicks account/login entry point before authentication.",
        "prefer_official_if": "Use login after successful authentication.",
        "parameters": "entry_point, cta_location, destination_url",
    },
    {
        "event": "chat_start",
        "scenario": "support and sales chat",
        "use_when": "User starts a live chat or bot conversation.",
        "prefer_official_if": "Use generate_lead if chat creates a qualified lead.",
        "parameters": "chat_type, chat_entry_point, business_unit",
    },
    {
        "event": "calculator_start",
        "scenario": "loan, mortgage, insurance, savings calculators",
        "use_when": "User begins using a calculator/tool.",
        "prefer_official_if": "No direct recommended event fits.",
        "parameters": "tool_name, tool_category, entry_point",
    },
    {
        "event": "calculator_complete",
        "scenario": "calculators and simulators",
        "use_when": "User reaches a calculated result.",
        "prefer_official_if": "Use generate_lead if result submission creates a lead.",
        "parameters": "tool_name, result_type, value_band",
    },
    {
        "event": "pricing_plan_select",
        "scenario": "SaaS, subscription, memberships",
        "use_when": "User selects a plan before checkout/signup.",
        "prefer_official_if": "Use begin_checkout/purchase if the plan selection enters a checkout.",
        "parameters": "plan_id, plan_name, billing_period, cta_location",
    },
    {
        "event": "feature_use",
        "scenario": "SaaS/product-led growth",
        "use_when": "A key product feature is used and no recommended event fits.",
        "prefer_official_if": "Use select_content/share/join_group when semantics fit.",
        "parameters": "feature_name, feature_area, user_role",
    },
    {
        "event": "appointment_start",
        "scenario": "healthcare, services, local business, real estate",
        "use_when": "User starts an appointment booking flow.",
        "prefer_official_if": "Use generate_lead when appointment request is submitted.",
        "parameters": "appointment_type, entry_point, location_id",
    },
    {
        "event": "appointment_booked",
        "scenario": "appointment booking",
        "use_when": "Appointment booking is confirmed.",
        "prefer_official_if": "Use generate_lead if booked appointment is modeled as a lead.",
        "parameters": "appointment_type, location_id, lead_source",
    },
    {
        "event": "modal_open",
        "scenario": "important overlays/popins",
        "use_when": "A modal materially changes the journey or blocks/provides conversion path.",
        "prefer_official_if": "Use select_content if it is simply content selection.",
        "parameters": "modal_id, modal_name, trigger_source",
    },
    {
        "event": "accordion_open",
        "scenario": "FAQ and support content",
        "use_when": "FAQ interaction is a real support/reassurance KPI.",
        "prefer_official_if": "Use select_content if treating FAQ selection as content selection is sufficient.",
        "parameters": "content_id, content_name, content_type",
    },
]


SCENARIOS = [
    {
        "scenario": "Content / publisher / blog",
        "website_examples": "media site, blog, documentation, editorial brand",
        "official_events": "page_view, scroll, select_content, share, file_download, video_start, video_progress, video_complete",
        "typical_custom_events": "newsletter_signup_intent, accordion_open, modal_open",
        "primary_parameters": "page_data.template, content_type, content_id, content_name, link_url, video_title",
        "notes": "Prefer enhanced measurement for scroll/video/download when it is sufficient; use select_content for content card/article selections.",
    },
    {
        "scenario": "Lead generation",
        "website_examples": "insurance, banking, B2B services, SaaS demo, contact forms",
        "official_events": "page_view, search, form_start, form_submit, generate_lead, qualify_lead, disqualify_lead, working_lead, close_convert_lead, close_unconvert_lead",
        "typical_custom_events": "begin_quote, form_step_view, form_step_submit, form_error, contact_intent, calculator_start, calculator_complete",
        "primary_parameters": "lead_source, form_name, form_step, product_type, quote_entry_point, cta_location",
        "notes": "Use generate_lead only after a valid submission or qualified lead action, not on CTA click.",
    },
    {
        "scenario": "Retail ecommerce",
        "website_examples": "DTC store, marketplace, merchandising site",
        "official_events": "view_item_list, select_item, view_item, add_to_wishlist, add_to_cart, remove_from_cart, view_cart, begin_checkout, add_shipping_info, add_payment_info, purchase, refund",
        "typical_custom_events": "filter_apply, sort_apply, size_guide_open, stock_alert_signup",
        "primary_parameters": "currency, value, transaction_id, items, items[].item_id, items[].item_name, items[].item_category, items[].price, items[].quantity",
        "notes": "Use official ecommerce event names and items array. Clear ecommerce object before ecommerce pushes when using GTM/dataLayer.",
    },
    {
        "scenario": "Internal promotions / offer cards",
        "website_examples": "home page offers, banners, campaign modules, cross-sell modules",
        "official_events": "view_promotion, select_promotion",
        "typical_custom_events": "promotion_expand, offer_terms_open",
        "primary_parameters": "promotion_id, promotion_name, creative_name, creative_slot, items, items[].item_id, items[].item_name",
        "notes": "Use promotion events only for real promotions/offers, not every generic content card.",
    },
    {
        "scenario": "SaaS / product-led growth",
        "website_examples": "trial signup, dashboard, product app",
        "official_events": "sign_up, login, tutorial_begin, tutorial_complete, join_group, share, select_content, purchase",
        "typical_custom_events": "feature_use, pricing_plan_select, upgrade_intent, workspace_created",
        "primary_parameters": "method, group_id, plan_id, feature_name, user_role",
        "notes": "Use login/sign_up for successful actions; use intent custom events for pre-auth clicks or plan exploration.",
    },
    {
        "scenario": "Search, listings, and filters",
        "website_examples": "site search, real estate, jobs, product/category listings",
        "official_events": "search, view_search_results, view_item_list, select_item, select_content",
        "typical_custom_events": "filter_apply, sort_apply, listing_map_interaction",
        "primary_parameters": "search_term, result_count, filter_category, filter_value, sort_type, item_list_id",
        "notes": "Use search for submitted queries and view_search_results when results page detection via query parameter is enough.",
    },
    {
        "scenario": "Booking / reservation / travel",
        "website_examples": "hotels, flights, activities, appointments",
        "official_events": "search, view_item_list, select_item, view_item, begin_checkout, add_payment_info, purchase, generate_lead",
        "typical_custom_events": "booking_start, booking_step_view, booking_step_submit, appointment_booked",
        "primary_parameters": "destination, dates, guests_count, item_id, item_name, value, currency, transaction_id",
        "notes": "Model paid bookings as ecommerce when money is transacted; model appointment requests as leads.",
    },
    {
        "scenario": "Support / customer service",
        "website_examples": "help center, claims, account support, chat",
        "official_events": "page_view, search, select_content, file_download, login",
        "typical_custom_events": "contact_intent, chat_start, claim_intent, account_access_intent, support_article_helpful",
        "primary_parameters": "support_topic, contact_method, entry_point, content_id, content_name",
        "notes": "Do not send claim descriptions, policy numbers, email, phone, or chat text to GA4.",
    },
    {
        "scenario": "Education / courses",
        "website_examples": "course catalog, LMS, training marketplace",
        "official_events": "view_item_list, select_item, view_item, sign_up, begin_checkout, purchase, tutorial_begin, tutorial_complete",
        "typical_custom_events": "course_progress, lesson_complete, certificate_download",
        "primary_parameters": "course_id, course_name, content_type, progress_percent, value, currency",
        "notes": "Paid enrollment can use ecommerce. Learning engagement may need custom events.",
    },
    {
        "scenario": "Games",
        "website_examples": "web game, mobile game, gamified platform",
        "official_events": "earn_virtual_currency, spend_virtual_currency, level_start, level_end, level_up, post_score, unlock_achievement, tutorial_begin, tutorial_complete",
        "typical_custom_events": "mission_start, mission_complete, item_equipped",
        "primary_parameters": "level_name, success, score, character, virtual_currency_name, value, achievement_id",
        "notes": "Use official game recommended events wherever possible.",
    },
]


DATALAYER_PATTERNS = [
    {
        "name": "Generic interaction event",
        "use_for": "Custom interactions that are not ecommerce.",
        "format": "dataLayer.push({'event_data': null});\ndataLayer.push({\n  'event': 'custom_event_name',\n  'event_data': {\n    'parameter_name': 'value'\n  }\n});",
        "gtm_mapping": "Custom Event trigger = custom_event_name. GA4 Event tag event name = {{Event}} or fixed event name. Map event_data.* as event parameters.",
    },
    {
        "name": "Manual page_view with page_data",
        "use_for": "SPA route changes or explicit pageview control.",
        "format": "dataLayer.push({'page_data': null});\ndataLayer.push({\n  'event': 'page_view',\n  'page_data': {\n    'location': 'https://example.com/page',\n    'title': 'Page title',\n    'template': 'homepage',\n    'language': 'fr'\n  }\n});",
        "gtm_mapping": "Trigger on page_view. Map page_data.location/title/template/language into GA4 parameters when needed.",
    },
    {
        "name": "Recommended search event",
        "use_for": "Submitted internal site search.",
        "format": "dataLayer.push({'event_data': null});\ndataLayer.push({\n  'event': 'search',\n  'event_data': {\n    'search_term': 'insurance quote',\n    'result_count': 12\n  }\n});",
        "gtm_mapping": "GA4 Event name = search. Map search_term and optional custom result_count.",
    },
    {
        "name": "Lead success event",
        "use_for": "Successful lead/contact/quote form submission.",
        "format": "dataLayer.push({'event_data': null});\ndataLayer.push({\n  'event': 'generate_lead',\n  'event_data': {\n    'lead_source': 'homepage',\n    'form_name': 'quote_form',\n    'product_type': 'auto'\n  }\n});",
        "gtm_mapping": "GA4 Event name = generate_lead. Map lead_source and business parameters. Mark as key event if appropriate.",
    },
    {
        "name": "Custom quote start event",
        "use_for": "User starts quote flow before a lead exists.",
        "format": "dataLayer.push({'event_data': null});\ndataLayer.push({\n  'event': 'begin_quote',\n  'event_data': {\n    'quote_type': 'insurance',\n    'product_type': 'auto',\n    'quote_entry_point': 'hero_auto',\n    'cta_location': 'hero'\n  }\n});",
        "gtm_mapping": "GA4 Event name = begin_quote. Register key dimensions only if needed for reporting.",
    },
    {
        "name": "Ecommerce add_to_cart",
        "use_for": "User adds item to cart.",
        "format": "dataLayer.push({'ecommerce': null});\ndataLayer.push({\n  'event': 'add_to_cart',\n  'ecommerce': {\n    'currency': 'EUR',\n    'value': 99.99,\n    'items': [{\n      'item_id': 'SKU_123',\n      'item_name': 'Product name',\n      'item_category': 'Category',\n      'price': 99.99,\n      'quantity': 1\n    }]\n  }\n});",
        "gtm_mapping": "GA4 Event name = add_to_cart. Map official GA4 parameters from the GTM ecommerce dataLayer object, for example currency from ecommerce.currency and items from ecommerce.items.",
    },
    {
        "name": "Ecommerce purchase",
        "use_for": "Order confirmation / purchase success.",
        "format": "dataLayer.push({'ecommerce': null});\ndataLayer.push({\n  'event': 'purchase',\n  'ecommerce': {\n    'transaction_id': 'T12345',\n    'currency': 'EUR',\n    'value': 149.99,\n    'tax': 20.00,\n    'shipping': 4.99,\n    'items': [{\n      'item_id': 'SKU_123',\n      'item_name': 'Product name',\n      'price': 149.99,\n      'quantity': 1\n    }]\n  }\n});",
        "gtm_mapping": "GA4 Event name = purchase. transaction_id is required for deduplication/reporting quality. Map official GA4 parameters from the GTM ecommerce dataLayer object.",
    },
    {
        "name": "Promotion impression/click",
        "use_for": "Internal promotions and offer cards.",
        "format": "dataLayer.push({'ecommerce': null});\ndataLayer.push({\n  'event': 'view_promotion',\n  'ecommerce': {\n    'promotion_id': 'promo_2026_01',\n    'promotion_name': 'homepage_offer',\n    'creative_slot': 'homepage_hero_1',\n    'items': [{\n      'item_id': 'offer_1',\n      'item_name': 'homepage_offer'\n    }]\n  }\n});",
        "gtm_mapping": "Use view_promotion for exposure and select_promotion for click, keeping promotion IDs stable across both. Map official GA4 parameters from the GTM ecommerce dataLayer object.",
    },
]


def build_library():
    SKILL_REFS.mkdir(parents=True, exist_ok=True)
    try:
        recommended = fetch_recommended_events()
    except Exception:
        recommended = json.loads(OFFICIAL_JSON.read_text(encoding="utf-8")) if OFFICIAL_JSON.exists() else []
    OFFICIAL_JSON.write_text(json.dumps(recommended, indent=2, ensure_ascii=False), encoding="utf-8")
    library = {
        "version": "2026-06-26",
        "scope": "GA4 web tracking-plan scenario library for human analysts and Codex-assisted tracking plan generation.",
        "source_priority": "Official Google documentation first. Trusted practitioner sources only for custom-event patterns and implementation judgement.",
        "value_convention": "For controlled analytics values, use lowercase ASCII snake_case, remove accents/diacritics, and list finite options with pipes. Preserve official IDs, ISO codes, numeric values, URLs, and raw native/user-entered fields only when required and privacy-safe.",
        "sources": SOURCES,
        "standard_events": STANDARD_EVENTS,
        "official_recommended_events": recommended,
        "typical_custom_events": TYPICAL_CUSTOM_EVENTS,
        "scenario_playbooks": SCENARIOS,
        "datalayer_patterns": DATALAYER_PATTERNS,
    }
    LIBRARY_JSON.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8")
    LIBRARY_MD.write_text(render_markdown(library), encoding="utf-8")
    print(LIBRARY_JSON)
    print(LIBRARY_MD)


def render_markdown(library):
    lines = [
        "# GA4 Event Scenario Library",
        "",
        "Use this reference when creating a GA4 tracking plan from a website, page, or journey.",
        "",
        "Decision order:",
        "",
        "1. Use automatic or enhanced-measurement events when they already answer the need.",
        "2. Use GA4 recommended events when the semantics match.",
        "3. Use ecommerce recommended events for product, cart, checkout, purchase, refund, and promotion flows.",
        "4. Use custom events only when the interaction is business-specific and no official event fits.",
        "5. Keep custom events stable, low-noise, and tied to a business question.",
        "6. Consolidate repeated same-name events when possible and normalize controlled values to lowercase ASCII snake_case with accents removed.",
        "",
        "## Contents",
        "",
        "- [Standard Web Events](#standard-web-events)",
        "- [Official Recommended Events](#official-recommended-events)",
        "- [Scenario Playbooks](#scenario-playbooks)",
        "- [Typical Custom Events](#typical-custom-events)",
        "- [DataLayer Patterns](#datalayer-patterns)",
        "- [Sources](#sources)",
        "",
        "## Standard Web Events",
        "",
        "| Event | Group | Scenario | Parameters | Implementation note |",
        "|---|---|---|---|---|",
    ]
    for event in library["standard_events"]:
        lines.append(
            f"| `{event['event']}` | {event['group']} | {event['scenario']} | {event['parameters']} | {event['implementation']} |"
        )
    lines += ["", "## Official Recommended Events", ""]
    by_group = {}
    for event in library["official_recommended_events"]:
        by_group.setdefault(event["group"], []).append(event)
    for group, events in by_group.items():
        lines += [f"### {group}", "", "| Event | Main parameters | Use |", "|---|---|---|"]
        for event in events:
            params = ", ".join(p["name"] for p in event["parameters"]) or "-"
            lines.append(f"| `{event['event']}` | {params} | {event['description']} |")
        lines.append("")
    lines += ["## Scenario Playbooks", "", "| Scenario | Official events | Typical custom events | Primary parameters | Notes |", "|---|---|---|---|---|"]
    for scenario in library["scenario_playbooks"]:
        lines.append(
            f"| {scenario['scenario']} | {scenario['official_events']} | {scenario['typical_custom_events']} | {scenario['primary_parameters']} | {scenario['notes']} |"
        )
    lines += ["", "## Typical Custom Events", "", "| Event | Scenario | Use when | Prefer official if | Parameters |", "|---|---|---|---|---|"]
    for event in library["typical_custom_events"]:
        lines.append(
            f"| `{event['event']}` | {event['scenario']} | {event['use_when']} | {event['prefer_official_if']} | {event['parameters']} |"
        )
    lines += ["", "## DataLayer Patterns", ""]
    for pattern in library["datalayer_patterns"]:
        lines += [
            f"### {pattern['name']}",
            "",
            f"Use for: {pattern['use_for']}",
            "",
            "```js",
            pattern["format"],
            "```",
            "",
            f"GTM mapping: {pattern['gtm_mapping']}",
            "",
        ]
    lines += ["## Sources", "", "| Source | Type | URL | Used for |", "|---|---|---|---|"]
    for source in library["sources"]:
        lines.append(f"| {source['name']} | {source['type']} | {source['url']} | {source['used_for']} |")
    return "\n".join(lines)


if __name__ == "__main__":
    build_library()
