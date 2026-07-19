import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SKILL_REFS = ROOT / "skill" / "references" / "03-rules"
OFFICIAL_JSON = SKILL_REFS / "library-ga4-recommended-events.json"
LIBRARY_JSON = SKILL_REFS / "library-ga4-event-scenarios.json"
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from official_ga4_catalog import (  # noqa: E402
    AUTOMATIC_EVENTS_URL,
    ECOMMERCE_IMPLEMENTATION_URL,
    ENHANCED_MEASUREMENT_URL,
    STANDARD_EVENT_OFFICIAL_SEMANTICS,
    clean_html,
    normalize_text,
    parse_catalog_html,
)

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


def fetch_recommended_events():
    url = "https://developers.google.com/analytics/devguides/collection/ga4/reference/events"
    text = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode("utf-8", "ignore")
    recommended, official_updated = parse_catalog_html(text)
    if not recommended or not official_updated:
        raise ValueError("Could not parse the live GA4 recommended-event catalog and its update date.")
    ecommerce_text = urlopen(
        Request(ECOMMERCE_IMPLEMENTATION_URL, headers={"User-Agent": "Mozilla/5.0"}),
        timeout=30,
    ).read().decode("utf-8", "ignore")
    ecommerce_match = re.search(r"Last updated\s+(\d{4}-\d{2}-\d{2})\s+UTC", ecommerce_text)
    if not ecommerce_match:
        raise ValueError("Could not parse the live GA4 ecommerce source update date.")
    standard_pages = {
        source_url: normalize_text(
            clean_html(
                urlopen(
                    Request(source_url, headers={"User-Agent": "Mozilla/5.0"}),
                    timeout=30,
                )
                .read()
                .decode("utf-8", "ignore")
            )
        )
        for source_url in (AUTOMATIC_EVENTS_URL, ENHANCED_MEASUREMENT_URL)
    }
    for event_name, semantics in STANDARD_EVENT_OFFICIAL_SEMANTICS.items():
        source_text = standard_pages[str(semantics["source_url"])]
        trigger_text = normalize_text(semantics["official_trigger"])
        trigger_position = source_text.find(trigger_text)
        if trigger_position < 0:
            raise ValueError(f"Could not verify the live GA4 trigger wording for {event_name}.")
        evidence_window = source_text[trigger_position : trigger_position + 3000]
        missing_parameters = [
            parameter
            for parameter in semantics["parameters"]
            if normalize_text(parameter) not in evidence_window
        ]
        if missing_parameters:
            raise ValueError(
                f"Could not verify the live GA4 parameter list for {event_name}: {', '.join(missing_parameters)}."
            )
    return recommended, official_updated, ecommerce_match.group(1), date.today().isoformat()


STANDARD_EVENT_CONTEXTS = [
    {
        "event": "page_view",
        "group": "automatic / enhanced measurement",
        "scenario": "page view, SPA route change",
        "implementation": "Usually automatic. Manually control only when SPA/infinite-scroll behavior requires it.",
    },
    {
        "event": "first_visit",
        "group": "automatic",
        "scenario": "new user acquisition",
        "implementation": "Automatic; do not implement manually.",
    },
    {
        "event": "session_start",
        "group": "automatic",
        "scenario": "session analysis",
        "implementation": "Automatic; do not implement manually.",
    },
    {
        "event": "user_engagement",
        "group": "automatic",
        "scenario": "engagement time",
        "implementation": "Automatic; do not implement manually.",
    },
    {
        "event": "scroll",
        "group": "enhanced measurement",
        "scenario": "content engagement",
        "implementation": "Enhanced measurement. Use a custom scroll-depth event only when additional thresholds answer an analysis need.",
    },
    {
        "event": "click",
        "group": "enhanced measurement",
        "scenario": "outbound link click",
        "implementation": "Enhanced measurement. Avoid duplicating it with a custom outbound-click event.",
    },
    {
        "event": "view_search_results",
        "group": "enhanced measurement",
        "scenario": "search results page",
        "implementation": "Enhanced measurement. Optional configured query keys are emitted as q_<key>; use recommended search when explicit submitted-search measurement is also needed.",
    },
    {
        "event": "video_start",
        "group": "enhanced measurement",
        "scenario": "YouTube embedded video",
        "implementation": "Enhanced measurement for embedded YouTube videos with JavaScript API support.",
    },
    {
        "event": "video_progress",
        "group": "enhanced measurement",
        "scenario": "YouTube embedded video",
        "implementation": "Enhanced measurement for embedded YouTube videos with JavaScript API support.",
    },
    {
        "event": "video_complete",
        "group": "enhanced measurement",
        "scenario": "YouTube embedded video",
        "implementation": "Enhanced measurement for embedded YouTube videos with JavaScript API support.",
    },
    {
        "event": "file_download",
        "group": "enhanced measurement",
        "scenario": "downloadable file click",
        "implementation": "Enhanced measurement. Use a custom file event only for a materially different gated or classified outcome.",
    },
    {
        "event": "form_start",
        "group": "enhanced measurement",
        "scenario": "form engagement",
        "implementation": "Enhanced measurement. Use custom form-step events only when the form funnel requires them.",
    },
    {
        "event": "form_submit",
        "group": "enhanced measurement",
        "scenario": "form submission",
        "implementation": "Enhanced measurement records submission, not confirmed lead success; use generate_lead only after a valid lead outcome.",
    },
]

STANDARD_EVENTS = [
    {
        **context,
        "description": STANDARD_EVENT_OFFICIAL_SEMANTICS[context["event"]]["definition"],
        "trigger": STANDARD_EVENT_OFFICIAL_SEMANTICS[context["event"]]["trigger"],
        "official_trigger": STANDARD_EVENT_OFFICIAL_SEMANTICS[context["event"]]["official_trigger"],
        "parameters": ", ".join(STANDARD_EVENT_OFFICIAL_SEMANTICS[context["event"]]["parameters"]),
        "source_url": STANDARD_EVENT_OFFICIAL_SEMANTICS[context["event"]]["source_url"],
        "source_section": STANDARD_EVENT_OFFICIAL_SEMANTICS[context["event"]]["source_section"],
    }
    for context in STANDARD_EVENT_CONTEXTS
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
        "use_when": "A user changes the active result sorting rule.",
        "prefer_official_if": "No direct recommended event fits.",
        "parameters": "sort_type, previous_sort_type, result_count, listing_type",
    },
    {
        "event": "header_click",
        "scenario": "whole-site header and utility navigation",
        "use_when": "Client reporting separates header navigation from menus, content, and footer links.",
        "prefer_official_if": "Use select_content only for actual content objects or an approved consolidated client convention.",
        "parameters": "link_name, link_url, navigation_group, link_position",
    },
    {
        "event": "menu_click",
        "scenario": "whole-site top-level navigation",
        "use_when": "Top-level menu choices need direct navigation reporting.",
        "prefer_official_if": "Use select_item for product tiles and select_content for actual content objects.",
        "parameters": "link_name, link_url, navigation_group, link_position",
    },
    {
        "event": "submenu_click",
        "scenario": "whole-site nested navigation",
        "use_when": "Second-level or deeper menu choices need to be distinguished from top-level navigation.",
        "prefer_official_if": "Use a consolidated client navigation convention when menu depth has no analysis value.",
        "parameters": "link_name, link_url, navigation_group, navigation_level",
    },
    {
        "event": "footer_click",
        "scenario": "whole-site footer navigation",
        "use_when": "Footer collection, service, legal, or social navigation needs separate reporting.",
        "prefer_official_if": "Use enhanced outbound click when destination-only reporting is sufficient.",
        "parameters": "link_name, link_url, navigation_group, link_position",
    },
    {
        "event": "payment_error",
        "scenario": "ecommerce or paid booking checkout",
        "use_when": "A payment attempt is refused or fails before confirmed purchase.",
        "prefer_official_if": "Use purchase only after confirmed order success; no official GA4 payment-failure event exists.",
        "parameters": "journey_step, error_type, error_code, payment_type, retry_number",
    },
    {
        "event": "newsletter_subscribe",
        "scenario": "newsletter and permissioned audience acquisition",
        "use_when": "A newsletter subscription is confirmed and the client reports it separately from commercial leads.",
        "prefer_official_if": "Use generate_lead only when newsletter and other lead outcomes intentionally share one KPI and owner.",
        "parameters": "form_name, lead_source, subscription_type",
    },
    {
        "event": "contact_submit",
        "scenario": "contact and customer-service forms",
        "use_when": "A contact request is confirmed and needs reporting separate from other lead outcomes.",
        "prefer_official_if": "Use generate_lead when the contact submission is intentionally governed as the same lead KPI.",
        "parameters": "form_name, contact_method, support_topic, lead_source",
    },
    {
        "event": "catalog_request",
        "scenario": "retail, publishing, travel, and mailed catalogue acquisition",
        "use_when": "A catalogue request is confirmed and fulfilment or acquisition reporting is distinct.",
        "prefer_official_if": "Use generate_lead when catalogue and other lead outcomes intentionally share one KPI.",
        "parameters": "form_name, lead_source, catalog_type",
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
        "event": "view_order_history",
        "scenario": "authenticated ecommerce customer space",
        "use_when": "Order-history usage is a meaningful self-service KPI and typed page_view reporting is insufficient.",
        "prefer_official_if": "Use page_view with governed page typing when it answers the same question.",
        "parameters": "account_section, order_count_bucket",
    },
    {
        "event": "view_order",
        "scenario": "authenticated ecommerce order detail",
        "use_when": "A customer views an order detail and the action needs separate self-service analysis.",
        "prefer_official_if": "Use page_view with governed page typing when separate event reporting is unnecessary.",
        "parameters": "account_section, order_status, order_age_bucket",
    },
    {
        "event": "start_return",
        "scenario": "authenticated ecommerce returns",
        "use_when": "A customer starts a return workflow before any refund is completed.",
        "prefer_official_if": "Use refund only when the financial or item refund is completed.",
        "parameters": "return_scope, order_age_bucket, eligibility_status",
    },
    {
        "event": "cancel_order",
        "scenario": "ecommerce post-purchase customer service",
        "use_when": "The commerce backend confirms cancellation of an existing order.",
        "prefer_official_if": "Use refund separately when money or items are actually refunded.",
        "parameters": "transaction_id, cancellation_stage, cancellation_reason",
    },
    {
        "event": "update_profile",
        "scenario": "authenticated customer profile",
        "use_when": "A profile update is confirmed and self-service completion is analytically useful.",
        "prefer_official_if": "Omit the event when the change has no actionable analysis need.",
        "parameters": "profile_field_group",
    },
    {
        "event": "update_preferences",
        "scenario": "authenticated communication or service preferences",
        "use_when": "A governed preference change is confirmed and approved for analytics collection.",
        "prefer_official_if": "Omit the event when consent or privacy governance does not permit collection.",
        "parameters": "preference_type, preference_state",
    },
    {
        "event": "password_reset",
        "scenario": "account recovery",
        "use_when": "Password recovery completes and access-resolution analysis is needed.",
        "prefer_official_if": "Use login when successful authentication alone sufficiently measures recovery.",
        "parameters": "method",
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
        "use_when": "A user begins a business-relevant calculator or simulator.",
        "prefer_official_if": "No direct recommended event fits.",
        "parameters": "tool_name, tool_category, entry_point",
    },
    {
        "event": "calculator_complete",
        "scenario": "calculators and simulators",
        "use_when": "A user completes a business-relevant calculator or simulator and sees a result.",
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
        "use_when": "An appointment booking is successfully confirmed for the user.",
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
        "primary_parameters": "page_template, content_type, content_id, content_name, link_url, video_title",
        "notes": "Prefer enhanced measurement for scroll/video/download when it is sufficient; use select_content for content card/article selections.",
    },
    {
        "scenario": "Lead generation",
        "website_examples": "insurance, banking, B2B services, SaaS demo, contact forms",
        "official_events": "page_view, search, form_start, form_submit, generate_lead, qualify_lead, disqualify_lead, working_lead, close_convert_lead, close_unconvert_lead",
        "typical_custom_events": "begin_quote, form_step_view, form_step_submit, form_error, newsletter_subscribe, contact_submit, catalog_request, contact_intent, calculator_start, calculator_complete",
        "primary_parameters": "lead_source, form_name, form_step, product_type, quote_entry_point, cta_location",
        "notes": "Use generate_lead only after a valid submission or qualified lead action. Prefer dedicated success events when newsletter, contact, catalogue, or other outcomes have distinct owners and reporting.",
    },
    {
        "scenario": "Retail ecommerce",
        "website_examples": "DTC store, marketplace, merchandising site",
        "official_events": "view_item_list, select_item, view_item, add_to_wishlist, add_to_cart, remove_from_cart, view_cart, begin_checkout, add_shipping_info, add_payment_info, purchase, refund",
        "typical_custom_events": "filter_apply, sort_apply, size_guide_open, stock_alert_signup, payment_error, view_order_history, view_order, start_return, cancel_order, update_profile, update_preferences, password_reset",
        "primary_parameters": "currency, value, transaction_id, items, items[].item_id, items[].item_name, items[].item_category, items[].item_variant, items[].availability_status, items[].price, items[].quantity",
        "notes": "Use official ecommerce event names and items array. Clear ecommerce before pushes. Use custom item availability on view_item when variant shortage matters, and on view_cart only for persistent carts with live inventory. Keep confirmed cancellation separate from official refund completion.",
    },
    {
        "scenario": "Account / authenticated customer space",
        "website_examples": "customer portal, member area, order self-service, profile and preferences",
        "official_events": "page_view, sign_up, login, search, select_content, add_to_wishlist, add_to_cart, begin_checkout, purchase, refund",
        "typical_custom_events": "account_access_intent, view_order_history, view_order, start_return, cancel_order, update_profile, update_preferences, password_reset",
        "primary_parameters": "account_section, entry_point, login_status, customer_status, order_status, return_scope, cancellation_stage",
        "notes": "Explore the real authenticated journey with synthetic information. Propose no gated event from labels or public navigation alone, and keep order cancellation separate from refund completion.",
    },
    {
        "scenario": "Subscription / membership",
        "website_examples": "publisher subscription, paid membership, gated content, digital service plan",
        "official_events": "page_view, select_content, sign_up, login, begin_checkout, add_payment_info, purchase, refund, generate_lead",
        "typical_custom_events": "paywall_view, subscription_offer_select, pricing_plan_select, subscription_cancel",
        "primary_parameters": "content_id, content_type, paywall_type, subscription_offer, plan_id, billing_period, access_status, cancellation_reason",
        "notes": "Use official commerce events when payment is transacted. Add paywall, offer, or cancellation events only when they support acquisition, conversion, or retention decisions.",
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
        "typical_custom_events": "contact_intent, chat_start, claim_intent, account_access_intent, view_order_history, view_order, start_return, cancel_order, update_profile, update_preferences, password_reset, support_article_helpful",
        "primary_parameters": "support_topic, contact_method, entry_point, content_id, content_name, account_section, order_status, return_scope",
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
        "name": "Manual page_view with page",
        "use_for": "SPA route changes or explicit pageview control.",
        "format": "dataLayer.push({'page': null});\ndataLayer.push({\n  'event': 'page_view',\n  'page': {\n    'page_location': 'https://example.com/page',\n    'page_title': 'Page title',\n    'page_referrer': 'https://example.com/',\n    'page_template': 'homepage',\n    'nav_language': 'fr',\n    'nav_environment': 'production'\n  },\n  'user': {\n    'login_status': 'logged_out'\n  }\n});",
        "gtm_mapping": "Trigger on page_view. Map page.page_location/page_title/page_referrer/page_template/nav_language/nav_environment to identically named GA4 parameters when needed. Map approved user fields separately.",
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
    recommended, official_updated, ecommerce_updated, automatic_enhanced_checked = fetch_recommended_events()
    OFFICIAL_JSON.write_text(json.dumps(recommended, indent=2, ensure_ascii=False), encoding="utf-8")
    library = {
        "version": official_updated or date.today().isoformat(),
        "catalog_metadata": {
            "catalog_schema_version": "1.0.0",
            "generated_date": date.today().isoformat(),
            "generator_version": "1.0.0",
            "official_source_last_updated": official_updated,
            "ecommerce_source_last_updated": ecommerce_updated,
            "automatic_enhanced_checked_date": automatic_enhanced_checked,
        },
        "scope": "GA4 web tracking-plan scenario library for human analysis and implementation planning.",
        "source_priority": "Official Google documentation first. Trusted practitioner sources only for custom-event patterns and implementation judgement.",
        "value_convention": "For controlled analytics values, use lowercase ASCII snake_case, remove accents/diacritics, and list finite options with pipes. Preserve official IDs, ISO codes, numeric values, URLs, and raw native/user-entered fields only when required and privacy-safe.",
        "sources": SOURCES,
        "standard_events": STANDARD_EVENTS,
        "typical_custom_events": TYPICAL_CUSTOM_EVENTS,
        "scenario_playbooks": SCENARIOS,
        "datalayer_patterns": DATALAYER_PATTERNS,
    }
    LIBRARY_JSON.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8")
    print(LIBRARY_JSON)


if __name__ == "__main__":
    build_library()
