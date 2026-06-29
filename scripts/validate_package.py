from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
REFERENCES = SKILL / "references"
SKILL_INFO = REFERENCES / "01-skill"
COMMANDS = REFERENCES / "02-commands"
RULES = REFERENCES / "03-rules"
REQUIRED_REFERENCE_FILES = [
    SKILL_INFO / "purpose.md",
    SKILL_INFO / "users-and-questions.md",
    SKILL_INFO / "inputs-outputs.md",
    SKILL_INFO / "acceptance-criteria.md",
    SKILL_INFO / "non-goals.md",
    COMMANDS / "validation-commands.md",
    COMMANDS / "workbook-generation.md",
    COMMANDS / "corpus-review-workflow.md",
    RULES / "library-ga4-event-scenarios.md",
    RULES / "library-ga4-event-scenarios.json",
    RULES / "library-ga4-recommended-events.json",
    RULES / "policy-platform-boundaries.md",
    RULES / "analysis-business-scenarios.md",
    RULES / "analysis-website-archetypes.md",
    RULES / "analysis-measurement-coherence.md",
    RULES / "analysis-website-coverage.md",
    RULES / "review-corpus-learning-policy.md",
    RULES / "decision-custom-events.md",
    RULES / "library-parameters.json",
    RULES / "platform-piano-reference.md",
    RULES / "platform-piano-official-events.json",
    RULES / "schema-tracking-plan.json",
    RULES / "example-ga4-tracking-plan.json",
    RULES / "example-piano-tracking-plan.json",
    RULES / "example-piano-ecommerce-tracking-plan.json",
    RULES / "scenario-ecommerce.md",
    RULES / "scenario-lead-generation.md",
    RULES / "scenario-search-listing.md",
    RULES / "scenario-account-support-content.md",
    RULES / "scenario-spa-routing.md",
    RULES / "policy-data-quality-privacy.md",
    RULES / "qa-readiness.md",
    RULES / "review-official-first.md",
    RULES / "review-example-comparison.md",
    RULES / "policy-ga4-ecommerce-parameters.md",
]
REQUIRED_SKILL_SCRIPTS = [
    SKILL / "scripts" / "ecommerce_matrix.py",
    SKILL / "scripts" / "tracking_plan_validation_catalogs.py",
    SKILL / "scripts" / "tracking_plan_validation_events.py",
    SKILL / "scripts" / "tracking_plan_validation_model.py",
    SKILL / "scripts" / "generate_tracking_plan_workbook.py",
    SKILL / "scripts" / "validate_tracking_plan.py",
    SKILL / "scripts" / "export_tracking_plan_csv.py",
    SKILL / "scripts" / "discover_site_journeys.py",
    SKILL / "scripts" / "discover_site_journeys_playwright.py",
    SKILL / "scripts" / "annotate_screenshot.py",
    SKILL / "scripts" / "analyze_tracking_plan_corpus.ps1",
]
REQUIRED_SKILL_FILES = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    ROOT / ".gitignore",
    ROOT / "pyproject.toml",
    ROOT / ".github" / "workflows" / "validate-skill.yml",
    ROOT / ".github" / "workflows" / "release-package.yml",
    ROOT / ".github" / "pull_request_template.md",
    ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml",
    ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml",
    ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
    ROOT / "tests" / "test_discover_site_journeys.py",
    ROOT / "tests" / "test_root_wrappers.py",
    SKILL / "SKILL.md",
    SKILL / "agents" / "openai.yaml",
    SKILL / "assets" / "ga4_tracking_plan_template.xlsx",
    ROOT / "scripts" / "_run_skill_script.py",
    ROOT / "scripts" / "create_release_package.py",
    ROOT / "scripts" / "create_event_scenario_library.py",
    ROOT / "scripts" / "generate_tracking_plan_workbook.py",
    ROOT / "scripts" / "validate_tracking_plan.py",
    ROOT / "scripts" / "export_tracking_plan_csv.py",
    ROOT / "scripts" / "discover_site_journeys.py",
    ROOT / "scripts" / "discover_site_journeys_playwright.py",
    ROOT / "scripts" / "annotate_screenshot.py",
    ROOT / "scripts" / "analyze_tracking_plan_corpus.ps1",
    ROOT / "scripts" / "validate_package.py",
    *REQUIRED_REFERENCE_FILES,
    *REQUIRED_SKILL_SCRIPTS,
]
EXPECTED_TABS = [
    "00 Overview",
    "01 GTM Protocol",
    "02 Parameter Reference",
    "03 Event Matrix",
    "04 Screenshot Register",
    "05 QA Cases",
]
WORKBOOKS_TO_VALIDATE = [
    SKILL / "assets" / "ga4_tracking_plan_template.xlsx",
]
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".toml", ".yml", ".yaml", ".json", ".txt", ".gitignore", ".gitattributes"}
BANNED_PROJECT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b" + "da" + "xon" + r"\b",
        r"\b" + "lo" + "livier" + r"\b",
        "gtm-" + "pr4" + "mq6j",
        "work" + "space283",
        "audit_" + "cleanup",
        "first-day-" + "checklist",
        "onboarding-" + "state",
    ]
]
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "slack_token": re.compile(r"xox[baprs]-[0-9A-Za-z-]{20,}"),
    "windows_user_path": re.compile(r"C:\\Users\\", re.IGNORECASE),
}
LOCAL_ARTIFACT_DIRS = [
    ROOT / "files",
    ROOT / "release",
    ROOT / "generated",
    ROOT / "tracking-plan-corpus-analysis",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def check_required_files() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_SKILL_FILES if not path.exists()]
    if missing:
        fail(f"Missing required skill files: {missing}")


def check_skill_frontmatter() -> None:
    text = read_text(SKILL / "SKILL.md")
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        fail("skill/SKILL.md must start with YAML frontmatter")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", name):
        fail("Skill name must be lowercase hyphen-case and <= 64 characters")
    if not description:
        fail("Skill description is required")
    if len(description) > 1024:
        fail("Skill description must be <= 1024 characters")
    for expected in ["web analyst", "business-context", "analysis-needs", "scalable GA4"]:
        if expected.lower() not in description.lower():
            fail(f"Skill description should mention {expected!r} to preserve web analyst positioning")


def check_repo_maintenance_docs() -> None:
    readme = read_text(ROOT / "README.md")
    openai_yaml = read_text(SKILL / "agents" / "openai.yaml")
    contributing = read_text(ROOT / "CONTRIBUTING.md")
    pr_template = read_text(ROOT / ".github" / "pull_request_template.md")
    bug_template = read_text(ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml")
    feature_template = read_text(ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml")
    gitignore = read_text(ROOT / ".gitignore")

    for expected in [
        "web analyst",
        "business context",
        "analysis needs",
        "XLSX",
        "Maintenance Checklist",
        "Universal Analytics",
        "validate_package.py",
        "create_release_package.py",
        "Screenshot Register row for each event",
    ]:
        if expected not in readme:
            fail(f"README.md is missing maintenance or positioning text: {expected}")
    for expected in ["GA4 Web Analyst", "web analyst", "$ga4-tracking-plan"]:
        if expected not in openai_yaml:
            fail(f"skill/agents/openai.yaml is missing UI metadata text: {expected}")
    for expected in ["web analyst", "business context", "skill/references", "validate_package.py"]:
        if expected not in contributing:
            fail(f"CONTRIBUTING.md is missing maintenance guidance: {expected}")
    for expected in ["Scalability And Maintenance", "validate_package.py", "Custom events", "Workbook changes"]:
        if expected not in pr_template:
            fail(f"Pull request template is missing review guardrail: {expected}")
    for template_name, template_text in {
        "bug_report.yml": bug_template,
        "feature_request.yml": feature_template,
    }.items():
        for expected in ["Platform scope", "GA4", "Piano Analytics"]:
            if expected not in template_text:
                fail(f"{template_name} is missing issue routing field: {expected}")
    for expected in ["generated/", "deliverables/", "release/", "tracking-plan-corpus-analysis/", "*.zip"]:
        if expected not in gitignore:
            fail(f".gitignore is missing artifact guardrail: {expected}")


def check_skill_resource_links() -> None:
    text = read_text(SKILL / "SKILL.md")
    for rel in [
        "assets/ga4_tracking_plan_template.xlsx",
        "references/01-skill/purpose.md",
        "references/01-skill/users-and-questions.md",
        "references/01-skill/inputs-outputs.md",
        "references/01-skill/acceptance-criteria.md",
        "references/01-skill/non-goals.md",
        "references/02-commands/validation-commands.md",
        "references/02-commands/workbook-generation.md",
        "references/02-commands/corpus-review-workflow.md",
        "references/03-rules/library-ga4-event-scenarios.md",
        "references/03-rules/library-ga4-event-scenarios.json",
        "references/03-rules/library-ga4-recommended-events.json",
        "references/03-rules/policy-platform-boundaries.md",
        "references/03-rules/analysis-business-scenarios.md",
        "references/03-rules/analysis-website-archetypes.md",
        "references/03-rules/analysis-measurement-coherence.md",
        "references/03-rules/analysis-website-coverage.md",
        "references/03-rules/review-corpus-learning-policy.md",
        "references/03-rules/decision-custom-events.md",
        "references/03-rules/library-parameters.json",
        "references/03-rules/platform-piano-reference.md",
        "references/03-rules/platform-piano-official-events.json",
        "references/03-rules/schema-tracking-plan.json",
        "references/03-rules/example-ga4-tracking-plan.json",
        "references/03-rules/example-piano-tracking-plan.json",
        "references/03-rules/example-piano-ecommerce-tracking-plan.json",
        "references/03-rules/scenario-ecommerce.md",
        "references/03-rules/scenario-lead-generation.md",
        "references/03-rules/scenario-search-listing.md",
        "references/03-rules/scenario-account-support-content.md",
        "references/03-rules/scenario-spa-routing.md",
        "references/03-rules/policy-data-quality-privacy.md",
        "references/03-rules/qa-readiness.md",
        "references/03-rules/review-official-first.md",
        "references/03-rules/review-example-comparison.md",
        "references/03-rules/policy-ga4-ecommerce-parameters.md",
        "scripts/ecommerce_matrix.py",
        "scripts/generate_tracking_plan_workbook.py",
        "scripts/validate_tracking_plan.py",
        "scripts/export_tracking_plan_csv.py",
        "scripts/discover_site_journeys.py",
        "scripts/discover_site_journeys_playwright.py",
        "scripts/annotate_screenshot.py",
        "scripts/analyze_tracking_plan_corpus.ps1",
    ]:
        if rel not in text:
            fail(f"SKILL.md does not mention bundled resource {rel}")
        if not (SKILL / rel).exists():
            fail(f"Bundled resource is missing: {rel}")


def check_reference_navigation() -> None:
    for path in REFERENCES.rglob("*.md"):
        text = read_text(path)
        line_count = len(text.splitlines())
        if line_count > 100 and "## Contents" not in text and "## Table of Contents" not in text:
            fail(f"{display_path(path)} has {line_count} lines and should include a Contents section for scalable reference navigation")


def load_json(path: Path):
    return json.loads(read_text(path))


def check_mainstream_analytics_references() -> None:
    piano_text = read_text(RULES / "platform-piano-reference.md")
    for expected in [
        "page.display",
        "click.action",
        "click.navigation",
        "click.download",
        "click.exit",
        "product.display",
        "product.add_to_cart",
        "cart.creation",
        "transaction.confirmation",
        "product.purchased",
        "av.play",
        "av.start",
        "goal_type",
    ]:
        if expected not in piano_text:
            fail(f"Piano Analytics reference is missing {expected}")

    piano_catalog = load_json(RULES / "platform-piano-official-events.json")
    events = {
        event.get("event")
        for family in piano_catalog.get("event_families", [])
        for event in family.get("events", [])
        if isinstance(event, dict)
    }
    for expected in [
        "page.display",
        "click.action",
        "click.navigation",
        "click.download",
        "click.exit",
        "publisher.impression",
        "self_promotion.click",
        "internal_search_result.display",
        "product.display",
        "product.add_to_cart",
        "cart.creation",
        "cart.payment",
        "transaction.confirmation",
        "product.purchased",
        "av.play",
        "av.heartbeat",
        "av.ad.click",
    ]:
        if expected not in events:
            fail(f"Piano official events catalog is missing {expected}")
    scenarios = json.dumps(piano_catalog.get("scenario_mappings", []))
    for expected in ["purchase_confirmation", "add_to_cart", "video_playback"]:
        if expected not in scenarios:
            fail(f"Piano official events catalog is missing scenario mapping {expected}")

    policy_text = read_text(RULES / "policy-platform-boundaries.md")
    for expected in ["business action", "platform mappings", "GA4", "Piano Analytics"]:
        if expected not in policy_text:
            fail(f"Mainstream analytics policy is missing {expected}")

    business_text = read_text(RULES / "analysis-business-scenarios.md")
    for expected in ["macro conversions", "micro conversions", "Diagnostic events", "Custom Event Design Checklist", "Event Consolidation", "Approval Readiness"]:
        if expected not in business_text:
            fail(f"Business scenario analysis reference is missing {expected}")

    corpus_text = read_text(RULES / "review-corpus-learning-policy.md")
    for expected in ["Universal Analytics is sunset", "Legacy context only", "Do not copy client names", "Promotion Criteria"]:
        if expected not in corpus_text:
            fail(f"Corpus learning policy is missing {expected}")

    custom_decision_text = read_text(RULES / "decision-custom-events.md")
    for expected in ["filter_apply", "sort_apply", "select_item", "view_item", "view_item_list", "eventCategory"]:
        if expected not in custom_decision_text:
            fail(f"Custom event decision matrix is missing {expected}")

    parameter_library = load_json(RULES / "library-parameters.json")
    parameter_families = {family.get("family") for family in parameter_library.get("families", [])}
    for expected in [
        "global_page_context",
        "search_listing_filter_sort",
        "forms_leads_quotes",
        "ga4_ecommerce_event_parameters",
        "ga4_ecommerce_item_parameters",
    ]:
        if expected not in parameter_families:
            fail(f"Parameter proposition library is missing {expected}")

    archetype_text = read_text(RULES / "analysis-website-archetypes.md")
    for expected in [
        "Retail ecommerce",
        "Product catalog without online checkout",
        "Lead generation",
        "SaaS",
        "Publisher",
        "Support",
        "Marketplace",
        "Locator",
        "Media player",
        "Regulated finance",
        "Custom Event Acceptance Gate",
        "Hybrid Composition Rules",
    ]:
        if expected not in archetype_text:
            fail(f"Website archetype decision matrix is missing {expected}")

    schema = load_json(RULES / "schema-tracking-plan.json")
    schema_text = json.dumps(schema)
    for expected in ["execution_context", "template_policy", "input_artifact_inventory", "official_verification", "collection_strategy", "duplicate_risk", "parameter_profile", "custom_item_parameter", "official_match", "primary_platform", "measurementRole", "measurement_strategy", "website_coverage_map", "journeys_discovered", "business_event_family", "page_or_component", "data_dependencies", "reporting_purpose", "platform_mappings", "implementation_payloads", "piano_analytics", "piano_custom_property", "piano_data_model_property"]:
        if expected not in schema_text:
            fail(f"Tracking plan schema is missing cross-platform support for {expected}")

    coverage_text = read_text(RULES / "analysis-website-coverage.md")
    for expected in ["sitemap", "robots.txt", "navigation", "Playwright", "website_coverage_map", "Coverage Gate"]:
        if expected not in coverage_text:
            fail(f"Website coverage mapping reference is missing {expected}")


def check_tracking_plan_contract() -> None:
    schema_path = RULES / "schema-tracking-plan.json"
    fixture_path = RULES / "example-ga4-tracking-plan.json"
    piano_fixture_path = RULES / "example-piano-tracking-plan.json"
    piano_ecommerce_fixture_path = RULES / "example-piano-ecommerce-tracking-plan.json"
    schema = load_json(schema_path)
    fixture = load_json(fixture_path)
    piano_fixture = load_json(piano_fixture_path)
    piano_ecommerce_fixture = load_json(piano_ecommerce_fixture_path)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for label, candidate in [
        ("Generic fixture", fixture),
        ("Generic Piano fixture", piano_fixture),
        ("Generic Piano ecommerce fixture", piano_ecommerce_fixture),
    ]:
        errors = sorted(validator.iter_errors(candidate), key=lambda error: list(error.path))
        if errors:
            formatted = []
            for error in errors[:8]:
                path = ".".join(str(part) for part in error.path) or "<root>"
                formatted.append(f"{path}: {error.message}")
            fail(f"{label} does not match schema-tracking-plan.json:\n" + "\n".join(formatted))
        roles = {event.get("measurement_role") for event in candidate["events"]}
        if not roles <= {"macro_conversion", "micro_conversion", "diagnostic", "context"}:
            fail(f"{label} has invalid measurement_role values: {sorted(roles)}")
        if not roles:
            fail(f"{label} does not define measurement roles")
        if not all(event.get("page_or_component") for event in candidate["events"]):
            fail(f"{label} has events without page_or_component")
        if not all(event.get("data_dependencies") for event in candidate["events"]):
            fail(f"{label} has events without data_dependencies")
        if not candidate.get("execution_context", {}).get("template_policy"):
            fail(f"{label} has no execution_context.template_policy")
        if not candidate.get("website_coverage_map", {}).get("journeys_discovered"):
            fail(f"{label} has no website_coverage_map.journeys_discovered")
        if not all(event.get("official_verification") for event in candidate["events"]):
            fail(f"{label} has events without official_verification")
        if not all(event.get("collection_strategy") for event in candidate["events"]):
            fail(f"{label} has events without collection_strategy")
        if not all(parameter.get("official_verification") for parameter in candidate["parameters"]):
            fail(f"{label} has parameters without official_verification")
        strategy = candidate.get("measurement_strategy", {})
        if not strategy.get("scalability_notes"):
            fail(f"{label} has no scalability_notes in measurement_strategy")
        family_ids = {
            family.get("family_id")
            for family in strategy.get("selected_event_families", [])
            if isinstance(family, dict)
        }
        if not family_ids:
            fail(f"{label} has no selected event families in measurement_strategy")
        unknown_families = sorted(
            {
                event.get("business_event_family")
                for event in candidate["events"]
                if event.get("business_event_family") not in family_ids
            }
        )
        if unknown_families:
            fail(f"{label} has events with unknown business_event_family values: {unknown_families}")
        custom_events = {event["event_name"] for event in candidate["events"] if event.get("classification") in {"custom", "piano_custom"}}
        accepted_custom_events = {
            item.get("event_name")
            for item in strategy.get("custom_event_acceptance", [])
            if isinstance(item, dict)
        }
        if custom_events - accepted_custom_events:
            fail(f"{label} has custom events without strategy acceptance entries: {sorted(custom_events - accepted_custom_events)}")

    event_ids = [event["event_id"] for event in fixture["events"]]
    if len(event_ids) != len(set(event_ids)):
        fail("Generic fixture has duplicate event_id values")

    event_qa_ids = {event["qa"]["qa_id"] for event in fixture["events"]}
    case_qa_ids = {case["qa_id"] for case in fixture["qa_cases"]}
    if event_qa_ids != case_qa_ids:
        fail(f"QA cases must match event qa_id values. Event QA={sorted(event_qa_ids)} Case QA={sorted(case_qa_ids)}")

    case_event_ids = {case["event_id"] for case in fixture["qa_cases"]}
    if set(event_ids) != case_event_ids:
        fail("Every event must have exactly one top-level QA case")

    parameter_names = {parameter["parameter_name"] for parameter in fixture["parameters"]}
    referenced_parameters = {parameter for event in fixture["events"] for parameter in event["parameters"]}
    missing_parameters = sorted(referenced_parameters - parameter_names)
    if missing_parameters:
        fail(f"Fixture events reference parameters missing from parameter reference: {missing_parameters}")
    for label, candidate in [
        ("Generic fixture", fixture),
        ("Generic Piano fixture", piano_fixture),
        ("Generic Piano ecommerce fixture", piano_ecommerce_fixture),
    ]:
        for parameter in candidate["parameters"]:
            if not parameter.get("reporting_purpose"):
                fail(f"{label} parameter {parameter.get('parameter_name')} is missing reporting_purpose")

    for event in fixture["events"]:
        if event.get("platform_mappings"):
            for mapping in event["platform_mappings"]:
                if mapping.get("platform") == "piano_analytics" and "developers.piano.io" not in mapping.get("documentation_source", ""):
                    fail(f"{event['event_id']} Piano mapping must cite official Piano documentation")
        if event["classification"] == "recommended_ecommerce":
            event_parameters = set(event["parameters"])
            for required in ["items", "items[].item_id", "items[].item_name"]:
                if required not in event_parameters:
                    fail(f"{event['event_id']} ecommerce event is missing {required}")
            if not event["ga4_payload"].get("items"):
                fail(f"{event['event_id']} ecommerce event has no GA4 items payload example")

    if not any(
        mapping.get("platform") == "piano_analytics"
        for event in fixture["events"]
        for mapping in event.get("platform_mappings", [])
    ):
        fail("Generic fixture should include at least one Piano Analytics platform mapping")

    if piano_fixture.get("analytics_platforms") != ["piano_analytics"]:
        fail("Generic Piano fixture should be Piano-only")
    if piano_ecommerce_fixture.get("analytics_platforms") != ["piano_analytics"]:
        fail("Generic Piano ecommerce fixture should be Piano-only")
    for fixture_label, piano_only_fixture in [
        ("Piano fixture", piano_fixture),
        ("Piano ecommerce fixture", piano_ecommerce_fixture),
    ]:
        for event in piano_only_fixture["events"]:
            if "ga4_payload" in event or "data_layer" in event or "official_ga4_match" in event:
                fail(f"{event['event_id']} in {fixture_label} should not require GA4-specific fields")
            if not event.get("implementation_payloads"):
                fail(f"{event['event_id']} in {fixture_label} is missing implementation_payloads")
            if event.get("primary_platform") != "piano_analytics":
                fail(f"{event['event_id']} in {fixture_label} should use primary_platform=piano_analytics")
    ecommerce_event_names = {event["event_name"] for event in piano_ecommerce_fixture["events"]}
    for expected in ["product.add_to_cart", "cart.creation", "transaction.confirmation", "product.purchased"]:
        if expected not in ecommerce_event_names:
            fail(f"Generic Piano ecommerce fixture is missing {expected}")


def run_command(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        fail(f"{label} failed:\n{result.stdout}{result.stderr}")
    return result


def check_tracking_plan_validator() -> None:
    for fixture_path in [
        RULES / "example-ga4-tracking-plan.json",
        RULES / "example-piano-tracking-plan.json",
        RULES / "example-piano-ecommerce-tracking-plan.json",
    ]:
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_tracking_plan.py"),
                str(fixture_path),
            ],
            f"Tracking plan validator for {display_path(fixture_path)}",
        )


def validator_output_for(plan_data: dict, path: Path) -> subprocess.CompletedProcess[str]:
    path.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_tracking_plan.py"),
            str(path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def expect_validator_error(base_fixture: dict, temp_dir: Path, label: str, mutate, expected_code: str) -> None:
    candidate = json.loads(json.dumps(base_fixture))
    mutate(candidate)
    result = validator_output_for(candidate, temp_dir / f"{label}.json")
    combined = result.stdout + result.stderr
    if result.returncode == 0:
        fail(f"Validator unexpectedly accepted invalid fixture {label}")
    if expected_code not in combined:
        fail(f"Validator output for {label} did not include {expected_code}:\n{combined}")


def check_tracking_plan_negative_lints() -> None:
    fixture = load_json(RULES / "example-ga4-tracking-plan.json")
    piano_ecommerce_fixture = load_json(RULES / "example-piano-ecommerce-tracking-plan.json")
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        def reserved_prefix(candidate: dict) -> None:
            event = candidate["events"][0]
            event["event_name"] = "ga_bad_event"
            event["classification"] = "custom"
            event["official_match"] = "invalid custom event using reserved GA4 prefix"
            event["official_ga4_match"] = "invalid custom event using reserved GA4 prefix"
            event["data_layer"]["event_key"] = "ga_bad_event"
            event["data_layer"]["push"]["event"] = "ga_bad_event"
            event["ga4_payload"]["event_name"] = "ga_bad_event"

        expect_validator_error(fixture, temp_dir, "reserved_prefix", reserved_prefix, "GA4_RESERVED_PREFIX")

        def unknown_recommended(candidate: dict) -> None:
            event = candidate["events"][3]
            event["event_name"] = "search_submit"
            event["official_match"] = "incorrectly classified as official recommended"
            event["official_ga4_match"] = "incorrectly classified as official recommended"
            event["data_layer"]["event_key"] = "search_submit"
            event["data_layer"]["push"]["event"] = "search_submit"
            event["ga4_payload"]["event_name"] = "search_submit"

        expect_validator_error(fixture, temp_dir, "unknown_recommended", unknown_recommended, "GA4_RECOMMENDED_EVENT_UNKNOWN")

        def missing_recommended_required_parameter(candidate: dict) -> None:
            event = candidate["events"][3]
            event["parameters"] = [parameter for parameter in event["parameters"] if parameter != "search_term"]
            event["data_layer"]["push"]["event_data"].pop("search_term", None)
            event["ga4_payload"]["parameters"].pop("search_term", None)

        expect_validator_error(
            fixture,
            temp_dir,
            "missing_recommended_required_parameter",
            missing_recommended_required_parameter,
            "GA4_RECOMMENDED_PARAMETER_MISSING",
        )

        def official_marked_custom(candidate: dict) -> None:
            event = candidate["events"][3]
            event["classification"] = "custom"
            event["official_match"] = "incorrectly marked custom"
            event["official_ga4_match"] = "incorrectly marked custom"

        expect_validator_error(fixture, temp_dir, "official_marked_custom", official_marked_custom, "GA4_OFFICIAL_EVENT_MARKED_CUSTOM")

        def missing_event_platform(candidate: dict) -> None:
            candidate["events"][0].pop("primary_platform", None)

        expect_validator_error(fixture, temp_dir, "missing_event_platform", missing_event_platform, "SCHEMA_VALIDATION")

        def missing_measurement_role(candidate: dict) -> None:
            candidate["events"][0].pop("measurement_role", None)

        expect_validator_error(fixture, temp_dir, "missing_measurement_role", missing_measurement_role, "SCHEMA_VALIDATION")

        def missing_measurement_strategy(candidate: dict) -> None:
            candidate.pop("measurement_strategy", None)

        expect_validator_error(fixture, temp_dir, "missing_measurement_strategy", missing_measurement_strategy, "SCHEMA_VALIDATION")

        def missing_execution_context(candidate: dict) -> None:
            candidate.pop("execution_context", None)

        expect_validator_error(fixture, temp_dir, "missing_execution_context", missing_execution_context, "SCHEMA_VALIDATION")

        def unknown_business_event_family(candidate: dict) -> None:
            candidate["events"][0]["business_event_family"] = "missing_family"

        expect_validator_error(fixture, temp_dir, "unknown_business_event_family", unknown_business_event_family, "EVENT_FAMILY_UNKNOWN")

        def missing_custom_event_acceptance(candidate: dict) -> None:
            candidate["measurement_strategy"]["custom_event_acceptance"] = []

        expect_validator_error(fixture, temp_dir, "missing_custom_event_acceptance", missing_custom_event_acceptance, "CUSTOM_EVENT_ACCEPTANCE_MISSING")

        def missing_page_or_component(candidate: dict) -> None:
            candidate["events"][0].pop("page_or_component", None)

        expect_validator_error(fixture, temp_dir, "missing_page_or_component", missing_page_or_component, "SCHEMA_VALIDATION")

        def weak_page_or_component(candidate: dict) -> None:
            candidate["events"][0]["page_or_component"] = "button"

        expect_validator_error(fixture, temp_dir, "weak_page_or_component", weak_page_or_component, "EVENT_COMPONENT_CONTEXT_WEAK")

        def missing_data_dependencies(candidate: dict) -> None:
            candidate["events"][0]["data_dependencies"] = []

        expect_validator_error(fixture, temp_dir, "missing_data_dependencies", missing_data_dependencies, "EVENT_DATA_DEPENDENCIES_MISSING")

        def weak_data_dependency(candidate: dict) -> None:
            candidate["events"][0]["data_dependencies"] = ["data"]

        expect_validator_error(fixture, temp_dir, "weak_data_dependency", weak_data_dependency, "EVENT_DATA_DEPENDENCY_WEAK")

        def diagnostic_key_event(candidate: dict) -> None:
            event = candidate["events"][0]
            event["measurement_role"] = "diagnostic"
            event["key_event"] = True
            candidate["key_events"] = [
                {
                    "event_name": event["event_name"],
                    "reason": "Invalid diagnostic key event fixture.",
                    "conditions": "Invalid test case."
                }
            ]

        expect_validator_error(fixture, temp_dir, "diagnostic_key_event", diagnostic_key_event, "KEY_EVENT_ROLE_INVALID")

        def unknown_event_journey(candidate: dict) -> None:
            candidate["events"][0]["journey_id"] = "missing_journey"

        expect_validator_error(fixture, temp_dir, "unknown_event_journey", unknown_event_journey, "EVENT_JOURNEY_UNKNOWN")

        def unknown_coverage_journey(candidate: dict) -> None:
            candidate["website_coverage_map"]["journeys_covered"][0]["journey_id"] = "missing_journey"

        expect_validator_error(fixture, temp_dir, "unknown_coverage_journey", unknown_coverage_journey, "COVERAGE_JOURNEY_UNKNOWN")

        def discovered_journey_not_in_brief(candidate: dict) -> None:
            candidate["website_coverage_map"]["journeys_discovered"][0]["journey_id"] = "missing_journey"

        expect_validator_error(
            fixture,
            temp_dir,
            "discovered_journey_not_in_brief",
            discovered_journey_not_in_brief,
            "DISCOVERED_JOURNEY_NOT_IN_MEASUREMENT_BRIEF",
        )

        def empty_declared_journey(candidate: dict) -> None:
            candidate["measurement_brief"].append(
                {
                    **candidate["measurement_brief"][0],
                    "journey_id": "orphan_journey",
                    "journey_name": "Orphan journey",
                    "success_signals": ["orphan_event"],
                }
            )

        expect_validator_error(fixture, temp_dir, "empty_declared_journey", empty_declared_journey, "JOURNEY_HAS_NO_EVENTS")

        def uncovered_success_signal(candidate: dict) -> None:
            candidate["measurement_brief"][0]["success_signals"].append("missing_conversion_signal")

        expect_validator_error(fixture, temp_dir, "uncovered_success_signal", uncovered_success_signal, "SUCCESS_SIGNAL_NOT_COVERED")

        def weak_not_tracked_reason(candidate: dict) -> None:
            candidate["not_tracked"][0]["reason"] = "not needed"

        expect_validator_error(fixture, temp_dir, "weak_not_tracked_reason", weak_not_tracked_reason, "NOT_TRACKED_REASON_WEAK")

        def weak_custom_rationale(candidate: dict) -> None:
            event = next(event for event in candidate["events"] if event["classification"] == "custom")
            event["official_match"] = "track a link click"
            event["official_ga4_match"] = "track a link click"
            event["business_question"] = "Which link was clicked?"
            event["trigger"] = "User clicks a link."
            event["implementation_notes"] = ""

        expect_validator_error(fixture, temp_dir, "weak_custom_rationale", weak_custom_rationale, "CUSTOM_EVENT_RATIONALE_MISSING")

        def low_signal_custom_name(candidate: dict) -> None:
            event = next(event for event in candidate["events"] if event["classification"] == "custom")
            event["event_name"] = "button_click"
            event["data_layer"]["event_key"] = "button_click"
            event["data_layer"]["push"]["event"] = "button_click"
            event["ga4_payload"]["event_name"] = "button_click"

        expect_validator_error(fixture, temp_dir, "low_signal_custom_name", low_signal_custom_name, "LOW_SIGNAL_CUSTOM_EVENT_NAME")

        def legacy_ua_parameter(candidate: dict) -> None:
            event = candidate["events"][0]
            event["parameters"].append("eventCategory")
            event["ga4_payload"]["parameters"]["eventCategory"] = "navigation"
            candidate["parameters"].append(
                {
                    "parameter_name": "eventCategory",
                    "display_name": "Event category",
                    "scope": "event",
                    "type": "string",
                    "classification": "custom_event_parameter",
                    "required": "optional",
                    "description": "Legacy UA event category.",
                    "reporting_purpose": "Attempts to reuse legacy UA category reporting in GA4.",
                    "value_rules": "Legacy UA category value.",
                    "example_value": "navigation",
                    "allowed_values": [],
                    "source": "legacy UA plan",
                    "register_custom_definition": False,
                    "cardinality_risk": "low",
                    "pii_risk": "low",
                    "consent_dependency": "analytics consent",
                }
            )

        expect_validator_error(fixture, temp_dir, "legacy_ua_parameter", legacy_ua_parameter, "LEGACY_UA_FIELD")

        def missing_qa_network_event_name(candidate: dict) -> None:
            candidate["events"][0]["qa"]["expected_network"] = ["GA4 request contains page metadata."]

        expect_validator_error(fixture, temp_dir, "missing_qa_network_event_name", missing_qa_network_event_name, "QA_EXPECTED_NETWORK_EVENT_NAME_MISSING")

        def weak_business_question(candidate: dict) -> None:
            candidate["events"][0]["business_question"] = "Track page view."

        expect_validator_error(fixture, temp_dir, "weak_business_question", weak_business_question, "EVENT_BUSINESS_QUESTION_WEAK")

        def missing_top_level_qa_network_event_name(candidate: dict) -> None:
            candidate["qa_cases"][0]["expected_network"] = ["GA4 request contains page metadata."]

        expect_validator_error(
            fixture,
            temp_dir,
            "missing_top_level_qa_network_event_name",
            missing_top_level_qa_network_event_name,
            "QA_EXPECTED_NETWORK_EVENT_NAME_MISSING",
        )

        def missing_ga4_official_source(candidate: dict) -> None:
            candidate["documentation_sources_checked"] = [
                source
                for source in candidate["documentation_sources_checked"]
                if "google.com/analytics" not in source.get("url", "")
            ]

        expect_validator_error(fixture, temp_dir, "missing_ga4_official_source", missing_ga4_official_source, "GA4_OFFICIAL_SOURCE_MISSING")

        def unverified_official_event(candidate: dict) -> None:
            candidate["events"][1]["official_verification"]["status"] = "unverified"

        expect_validator_error(fixture, temp_dir, "unverified_official_event", unverified_official_event, "OFFICIAL_VERIFICATION_NOT_VERIFIED")

        def weak_duplicate_risk(candidate: dict) -> None:
            event = next(event for event in candidate["events"] if event["event_name"] == "search")
            event["collection_strategy"]["duplicate_risk"] = {
                "level": "low",
                "reason": "manual",
                "dedupe_rule": "none"
            }

        expect_validator_error(fixture, temp_dir, "weak_duplicate_risk", weak_duplicate_risk, "DUPLICATE_RISK_DECISION_WEAK")

        def missing_ecommerce_profile(candidate: dict) -> None:
            event = next(event for event in candidate["events"] if event["event_name"] == "view_promotion")
            event.pop("parameter_profile", None)

        expect_validator_error(fixture, temp_dir, "missing_ecommerce_profile", missing_ecommerce_profile, "ECOMMERCE_PARAMETER_PROFILE_MISSING")

        def missing_custom_definition(candidate: dict) -> None:
            candidate["custom_definitions"] = [
                definition
                for definition in candidate["custom_definitions"]
                if definition.get("parameter_name") != "cta_location"
            ]

        expect_validator_error(fixture, temp_dir, "missing_custom_definition", missing_custom_definition, "CUSTOM_DEFINITION_MISSING")

        def weak_custom_parameter_reporting_purpose(candidate: dict) -> None:
            parameter = next(parameter for parameter in candidate["parameters"] if parameter["parameter_name"] == "cta_location")
            parameter["reporting_purpose"] = "tracking"

        expect_validator_error(
            fixture,
            temp_dir,
            "weak_custom_parameter_reporting_purpose",
            weak_custom_parameter_reporting_purpose,
            "PARAMETER_REPORTING_PURPOSE_WEAK",
        )

        def weak_custom_parameter_value_rules(candidate: dict) -> None:
            parameter = next(parameter for parameter in candidate["parameters"] if parameter["parameter_name"] == "cta_location")
            parameter["value_rules"] = "string"

        expect_validator_error(
            fixture,
            temp_dir,
            "weak_custom_parameter_value_rules",
            weak_custom_parameter_value_rules,
            "CUSTOM_PARAMETER_VALUE_RULES_WEAK",
        )

        def missing_piano_product_purchased_property(candidate: dict) -> None:
            event = next(event for event in candidate["events"] if event["event_name"] == "product.purchased")
            event["parameters"] = [parameter for parameter in event["parameters"] if parameter != "transaction_id"]
            for mapping in event["platform_mappings"]:
                mapping["parameters_or_properties"].pop("transaction_id", None)
            for payload in event["implementation_payloads"]:
                payload["payload"].pop("transaction_id", None)

        expect_validator_error(
            piano_ecommerce_fixture,
            temp_dir,
            "missing_piano_product_purchased_property",
            missing_piano_product_purchased_property,
            "PIANO_MANDATORY_PROPERTY_MISSING",
        )

        def unknown_piano_sales_insights_event(candidate: dict) -> None:
            event = candidate["events"][0]
            event["event_name"] = "product.fake_event"
            for mapping in event["platform_mappings"]:
                mapping["event_name"] = "product.fake_event"
            for payload in event["implementation_payloads"]:
                payload["event_name"] = "product.fake_event"

        expect_validator_error(
            piano_ecommerce_fixture,
            temp_dir,
            "unknown_piano_sales_insights_event",
            unknown_piano_sales_insights_event,
            "PIANO_OFFICIAL_EVENT_UNKNOWN",
        )

        def missing_piano_official_source(candidate: dict) -> None:
            candidate["documentation_sources_checked"] = [
                source
                for source in candidate["documentation_sources_checked"]
                if "piano.io" not in source.get("url", "")
            ]

        expect_validator_error(
            piano_ecommerce_fixture,
            temp_dir,
            "missing_piano_official_source",
            missing_piano_official_source,
            "PIANO_OFFICIAL_SOURCE_MISSING",
        )

        def piano_native_marked_custom(candidate: dict) -> None:
            event = candidate["events"][0]
            event["classification"] = "piano_custom"
            event["official_match"] = "incorrectly marked custom"
            for mapping in event["platform_mappings"]:
                mapping["classification"] = "piano_custom"

        expect_validator_error(
            piano_ecommerce_fixture,
            temp_dir,
            "piano_native_marked_custom",
            piano_native_marked_custom,
            "PIANO_NATIVE_EVENT_MARKED_CUSTOM",
        )


def check_generated_workbook() -> None:
    fixture_path = RULES / "example-ga4-tracking-plan.json"
    piano_fixture_path = RULES / "example-piano-tracking-plan.json"
    piano_ecommerce_fixture_path = RULES / "example-piano-ecommerce-tracking-plan.json"
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "generic_tracking_plan.xlsx"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_tracking_plan_workbook.py"),
                str(fixture_path),
                "--output",
                str(output),
            ],
            "Workbook generator",
        )
        if not output.exists():
            fail("Workbook generator did not create the expected output file")
        check_event_matrix(output)

        piano_output = Path(temp_dir) / "generic_piano_tracking_plan.xlsx"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_tracking_plan_workbook.py"),
                str(piano_fixture_path),
                "--output",
                str(piano_output),
            ],
            "Workbook generator for Piano fixture",
        )
        if not piano_output.exists():
            fail("Workbook generator did not create the expected Piano output file")
        wb = load_workbook(piano_output, read_only=True, data_only=True)
        try:
            if wb.sheetnames != EXPECTED_TABS:
                fail(f"{display_path(piano_output)} has unexpected tabs: {wb.sheetnames}")
            ws = wb["03 Event Matrix"]
            if "page.display" not in {cell.value for row in ws.iter_rows() for cell in row}:
                fail("Piano generated workbook does not include page.display in the event matrix")
        finally:
            wb.close()

        piano_ecommerce_output = Path(temp_dir) / "generic_piano_ecommerce_tracking_plan.xlsx"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_tracking_plan_workbook.py"),
                str(piano_ecommerce_fixture_path),
                "--output",
                str(piano_ecommerce_output),
            ],
            "Workbook generator for Piano ecommerce fixture",
        )
        if not piano_ecommerce_output.exists():
            fail("Workbook generator did not create the expected Piano ecommerce output file")
        wb = load_workbook(piano_ecommerce_output, read_only=True, data_only=True)
        try:
            if wb.sheetnames != EXPECTED_TABS:
                fail(f"{display_path(piano_ecommerce_output)} has unexpected tabs: {wb.sheetnames}")
            ws = wb["03 Event Matrix"]
            matrix_values = {cell.value for row in ws.iter_rows() for cell in row}
            for expected in ["product.add_to_cart", "transaction.confirmation", "product.purchased"]:
                if expected not in matrix_values:
                    fail(f"Piano ecommerce generated workbook does not include {expected} in the event matrix")
        finally:
            wb.close()


def check_csv_export() -> None:
    fixture_path = RULES / "example-ga4-tracking-plan.json"
    piano_fixture_path = RULES / "example-piano-tracking-plan.json"
    piano_ecommerce_fixture_path = RULES / "example-piano-ecommerce-tracking-plan.json"
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "generic_tracking_plan.csv"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "export_tracking_plan_csv.py"),
                str(fixture_path),
                "--output",
                str(output),
            ],
            "CSV exporter",
        )
        if not output.exists() or output.stat().st_size == 0:
            fail("CSV exporter did not create a non-empty output file")
        header = output.read_text(encoding="utf-8-sig").splitlines()[0]
        for expected in ["event_name", "measurement_role", "business_event_family", "page_or_component", "data_dependencies", "official_match", "official_verification_status", "collection_source", "duplicate_risk_level", "parameter_profile", "parameter", "reporting_purpose", "scope_rule", "analytics_platform", "platform_event_name"]:
            if expected not in header:
                fail(f"CSV exporter output is missing header {expected}")
        for hidden in ["event_id", "qa_id"]:
            if hidden in header:
                fail(f"CSV exporter should not expose internal header {hidden}")

        piano_output = Path(temp_dir) / "generic_piano_tracking_plan.csv"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "export_tracking_plan_csv.py"),
                str(piano_fixture_path),
                "--output",
                str(piano_output),
            ],
            "CSV exporter for Piano fixture",
        )
        piano_text = piano_output.read_text(encoding="utf-8-sig")
        for expected in ["piano_analytics", "page.display", "click.navigation"]:
            if expected not in piano_text:
                fail(f"CSV exporter Piano output is missing {expected}")

        piano_ecommerce_output = Path(temp_dir) / "generic_piano_ecommerce_tracking_plan.csv"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "export_tracking_plan_csv.py"),
                str(piano_ecommerce_fixture_path),
                "--output",
                str(piano_ecommerce_output),
            ],
            "CSV exporter for Piano ecommerce fixture",
        )
        piano_ecommerce_text = piano_ecommerce_output.read_text(encoding="utf-8-sig")
        for expected in ["piano_analytics", "product.add_to_cart", "transaction.confirmation", "product.purchased"]:
            if expected not in piano_ecommerce_text:
                fail(f"CSV exporter Piano ecommerce output is missing {expected}")


def check_release_package() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "ga4-tracking-plan-package-test.zip"
        run_command(
            [
                sys.executable,
                str(ROOT / "scripts" / "create_release_package.py"),
                "--version",
                "test",
                "--output",
                str(output),
            ],
            "Release package builder",
        )
        if not output.exists():
            fail("Release package builder did not create a zip")
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
        for expected in ["skill/SKILL.md", "skill/assets/ga4_tracking_plan_template.xlsx", "requirements.txt", "README.md", "LICENSE"]:
            if expected not in names:
                fail(f"Release package is missing {expected}")
        forbidden = [
            name
            for name in names
            if any(part in {"deliverables", "generated", "release", "tracking-plan-corpus-analysis", "__pycache__"} for part in Path(name).parts)
        ]
        if forbidden:
            fail("Release package includes local artifact paths:\n" + "\n".join(sorted(forbidden)))


def event_blocks(ws):
    starts = []
    for row in range(6, ws.max_row + 1):
        value = ws.cell(row, 1).value
        if isinstance(value, str) and value.startswith("J-"):
            starts.append(row)
    starts.append(ws.max_row + 1)
    for index, start in enumerate(starts[:-1]):
        yield start, starts[index + 1] - 1


def row_values(ws, start: int, end: int) -> list[str]:
    values = []
    for row in range(start, end + 1):
        value = ws.cell(row, 1).value
        if isinstance(value, str) and value:
            values.append(value)
    return values


def event_slot_values(ws, row: int) -> list[str]:
    return [
        ws.cell(row, col).value
        for col in range(3, ws.max_column + 1)
        if ws.cell(row, col).value not in (None, "")
    ]


def block_event_types(ws, start: int, end: int) -> list[str]:
    for row in range(start, end + 1):
        if ws.cell(row, 1).value == "event_classification":
            return [str(value) for value in event_slot_values(ws, row)]
    return []


def check_event_matrix(workbook_path: Path) -> None:
    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if wb.sheetnames != EXPECTED_TABS:
            fail(f"{display_path(workbook_path)} has unexpected tabs: {wb.sheetnames}")

        ws = wb["03 Event Matrix"]
        header_values = [ws.cell(5, col).value for col in range(1, ws.max_column + 1)]
        if header_values[:2] != ["Field / parameter path", "Type"]:
            fail(f"{display_path(workbook_path)} Event Matrix must start with human-readable field/parameter and type columns")
        for value_col in range(3, ws.max_column + 1):
            if ws.cell(5, value_col).value != "Expected value / rule":
                fail(f"{display_path(workbook_path)} Event Matrix must keep one Expected value / rule column per event slot")
        matrix_labels = {str(row[0].value) for row in ws.iter_rows() if row and row[0].value}
        for expected_label in ["event_classification", "trigger", "event"]:
            if expected_label not in matrix_labels:
                fail(f"{display_path(workbook_path)} Event Matrix is missing {expected_label} row")
        for hidden_label in ["event_id", "screenshot_id", "qa_id", "key_event", "page_or_component", "dataLayer.event"]:
            if hidden_label in matrix_labels:
                fail(f"{display_path(workbook_path)} Event Matrix should not expose internal {hidden_label} rows")
        overview = wb["00 Overview"]
        overview_values = {cell.value for row in overview.iter_rows() for cell in row}
        for expected in ["Document Summary", "Sheet Contents", "Version History", "Publish date"]:
            if expected not in overview_values:
                fail(f"{display_path(workbook_path)} Overview is missing {expected}")
        screenshot_register = wb["04 Screenshot Register"]
        screenshot_headers = [screenshot_register.cell(3, col).value for col in range(1, 10)]
        expected_screenshot_headers = [
            "Journey",
            "Event",
            "Screenshot preview",
            "Page / component",
            "URL / route",
            "Capture objective",
            "Automation cue",
            "Status",
            "Notes",
        ]
        if screenshot_headers != expected_screenshot_headers:
            fail(f"{display_path(workbook_path)} Screenshot Register headers changed unexpectedly: {screenshot_headers}")
        screenshot_values = {cell.value for row in screenshot_register.iter_rows() for cell in row}
        if "File path or link" in screenshot_values:
            fail(f"{display_path(workbook_path)} Screenshot Register should not expose local file path/link columns")
        screenshot_statuses = {
            str(screenshot_register.cell(row, 8).value)
            for row in range(4, screenshot_register.max_row + 1)
            if screenshot_register.cell(row, 2).value not in (None, "")
        }
        allowed_screenshot_statuses = {
            "capture_required",
            "captured",
            "shared_evidence",
            "skip_allowed",
            "not_needed",
            "blocked",
        }
        unexpected_statuses = screenshot_statuses - allowed_screenshot_statuses
        if unexpected_statuses:
            fail(f"{display_path(workbook_path)} Screenshot Register has unexpected statuses: {sorted(unexpected_statuses)}")
        matrix_event_names = []
        for start, end in event_blocks(ws):
            for row in range(start, end + 1):
                if ws.cell(row, 1).value == "event":
                    matrix_event_names.extend(str(value) for value in event_slot_values(ws, row))
        screenshot_events = [
            str(screenshot_register.cell(row, 2).value)
            for row in range(4, screenshot_register.max_row + 1)
            if screenshot_register.cell(row, 2).value not in (None, "")
        ]
        missing_screenshot_events = sorted(set(matrix_event_names) - set(screenshot_events))
        if missing_screenshot_events:
            fail(f"{display_path(workbook_path)} Screenshot Register is missing event rows: {missing_screenshot_events}")
        found_ecommerce_block = False
        for start, end in event_blocks(ws):
            block_name = str(ws.cell(start, 1).value or "")
            types = block_event_types(ws, start, end)
            is_ecommerce = any(event_type == "recommended_ecommerce" for event_type in types) or "Ecommerce" in block_name
            if not is_ecommerce:
                continue

            found_ecommerce_block = True
            rows = row_values(ws, start, end)
            bad_rows = [row for row in rows if row.startswith("ecommerce.") or row.startswith("event_data.")]
            if bad_rows:
                fail(f"{display_path(workbook_path)} ecommerce block {block_name} has non-official rows: {bad_rows}")
            for required in ["items", "items[].item_id", "items[].item_name"]:
                if required not in rows:
                    fail(f"{display_path(workbook_path)} ecommerce block {block_name} is missing {required}")
            event_names = []
            for row in range(start, end + 1):
                if ws.cell(row, 1).value == "event":
                    event_names = [str(value) for value in event_slot_values(ws, row)]
                    break
            if any(name in {"purchase", "refund"} for name in event_names) and "transaction_id" not in rows:
                fail(f"{display_path(workbook_path)} purchase/refund block {block_name} is missing transaction_id")

        if not found_ecommerce_block:
            fail(f"{display_path(workbook_path)} does not contain an ecommerce block")
    finally:
        wb.close()


def check_workbooks() -> None:
    missing = [str(path.relative_to(ROOT)) for path in WORKBOOKS_TO_VALIDATE if not path.exists()]
    if missing:
        fail(f"Missing workbook(s): {missing}")
    for workbook_path in WORKBOOKS_TO_VALIDATE:
        check_event_matrix(workbook_path)


def check_no_release_only_files_folder() -> None:
    artifact_findings = []
    for artifact_dir in LOCAL_ARTIFACT_DIRS:
        if not artifact_dir.exists():
            continue
        files = [path for path in artifact_dir.rglob("*") if path.is_file()]
        if artifact_dir.name == "files" or files:
            artifact_findings.append(f"{display_path(artifact_dir)} ({len(files)} file(s))")
    if artifact_findings:
        fail("Release, generated, or local analysis artifact folders must not be kept in the repo:\n" + "\n".join(artifact_findings))

    all_path_findings = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or path.name.startswith("~$"):
            continue
        if any(part in {"deliverables", "generated", "release", "tracking-plan-corpus-analysis"} for part in path.parts):
            continue
        rel = display_path(path)
        if any(pattern.search(rel) for pattern in BANNED_PROJECT_PATTERNS):
            all_path_findings.append(rel)
    if all_path_findings:
        fail("Project-specific or test-related paths found:\n" + "\n".join(sorted(all_path_findings)))


def scan_text_for_secrets(path: Path, text: str) -> list[str]:
    findings = []
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            findings.append(f"{display_path(path)}: {name}")
    for pattern in BANNED_PROJECT_PATTERNS:
        if pattern.search(text):
            findings.append(f"{display_path(path)}: project_specific_reference:{pattern.pattern}")
    return findings


def check_confidential_patterns() -> None:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file() or path.name.startswith("~$"):
            continue
        if any(part in {"deliverables", "generated", "release", "tracking-plan-corpus-analysis"} for part in path.parts):
            continue
        suffix = path.suffix.lower()
        if suffix in TEXT_SUFFIXES or path.name in TEXT_SUFFIXES:
            findings.extend(scan_text_for_secrets(path, read_text(path)))
        elif suffix == ".xlsx":
            with zipfile.ZipFile(path) as archive:
                for member in archive.namelist():
                    if not member.endswith(".xml"):
                        continue
                    text = archive.read(member).decode("utf-8", "ignore")
                    for finding in scan_text_for_secrets(path, text):
                        findings.append(f"{finding} in {member}")
    if findings:
        fail("Potential confidential data found:\n" + "\n".join(sorted(findings)))


def main() -> int:
    checks = [
        check_required_files,
        check_skill_frontmatter,
        check_repo_maintenance_docs,
        check_skill_resource_links,
        check_reference_navigation,
        check_mainstream_analytics_references,
        check_tracking_plan_contract,
        check_tracking_plan_validator,
        check_tracking_plan_negative_lints,
        check_no_release_only_files_folder,
        check_workbooks,
        check_generated_workbook,
        check_csv_export,
        check_release_package,
        check_confidential_patterns,
    ]
    for check in checks:
        check()
        print(f"OK {check.__name__}")
    print("Package validation passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"ERROR {error}", file=sys.stderr)
        raise SystemExit(1)
