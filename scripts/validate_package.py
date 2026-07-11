from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from jsonschema import Draft202012Validator
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
RULES = SKILL / "references" / "03-rules"
COMMANDS = SKILL / "references" / "02-commands"
SCHEMA = RULES / "schema-tracking-plan.json"
FIXTURE = RULES / "example-ga4-tracking-plan.json"

REQUIRED_FILES = {
    ROOT / "README.md",
    ROOT / "LICENSE",
    ROOT / "SECURITY.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "requirements.txt",
    ROOT / "pyproject.toml",
    SKILL / "SKILL.md",
    SKILL / "agents" / "openai.yaml",
    SKILL / "assets" / "ga4_tracking_plan_template.xlsx",
    RULES / "execution-contract.md",
    RULES / "completion-gates.md",
    RULES / "policy-ga4-boundaries.md",
    RULES / "policy-authenticated-user-context.md",
    RULES / "library-ga4-event-scenarios.json",
    RULES / "library-ga4-recommended-events.json",
    RULES / "library-parameters.json",
    SCHEMA,
    FIXTURE,
    COMMANDS / "validation-commands.md",
    COMMANDS / "workbook-generation.md",
    COMMANDS / "official-catalog-maintenance.md",
    SKILL / "scripts" / "validate_tracking_plan.py",
    SKILL / "scripts" / "generate_tracking_plan_workbook.py",
    SKILL / "scripts" / "tracking_plan_screenshots.py",
    SKILL / "scripts" / "tracking_plan_validation_common.py",
    SKILL / "scripts" / "tracking_plan_validation_delivery.py",
    SKILL / "scripts" / "tracking_plan_validation_event_rules.py",
    SKILL / "scripts" / "official_ga4_catalog.py",
    SKILL / "scripts" / "inspect_tracking_plan_template.py",
    SKILL / "scripts" / "adapt_tracking_plan_workbook.py",
    SKILL / "scripts" / "check_official_catalog.py",
    SKILL / "scripts" / "migrate_tracking_plan.py",
    ROOT / "scripts" / "inspect_tracking_plan_template.py",
    ROOT / "scripts" / "adapt_tracking_plan_workbook.py",
}

EXPECTED_TABS = ["00 Overview", "01 GTM Protocol", "02 Parameter Reference", "03 Event Matrix", "04 DataLayer Examples", "05 Screenshot Register"]
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".ps1"}
BANNED_PATH_PARTS = {"deliverables", "generated", "release", "tracking-plan-corpus-analysis", "__pycache__"}
SECRET_PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "GTM container ID": re.compile(r"\bGTM-[A-Z0-9]{6,}\b"),
    "GA4 measurement ID": re.compile(r"\bG-[A-Z0-9]{8,}\b"),
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8")
    if result.returncode:
        fail(f"{label} failed\n{result.stdout}\n{result.stderr}")
    return result


def check_required_files() -> None:
    missing = sorted(str(path.relative_to(ROOT)) for path in REQUIRED_FILES if not path.exists())
    if missing:
        fail(f"Missing required files: {', '.join(missing)}")


def check_skill_metadata() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n") or "name: ga4-tracking-plan" not in text or "description:" not in text:
        fail("SKILL.md frontmatter is invalid")
    if len(text.splitlines()) > 500:
        fail("SKILL.md exceeds the 500-line progressive-disclosure limit")
    agent = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for expected in ("GA4 Web Analyst", "$ga4-tracking-plan"):
        if expected not in agent:
            fail(f"agents/openai.yaml is missing {expected}")


def check_reference_navigation() -> None:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    referenced = set(re.findall(r"`((?:references|scripts|assets)/[^`]+)`", text))
    for relative in referenced:
        path = SKILL / relative
        if "*" in relative:
            continue
        if not path.exists():
            fail(f"SKILL.md references missing resource: {relative}")


def check_ga4_only_scope() -> None:
    forbidden = "pia" + "no"
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore").lower()
        if forbidden in text:
            fail(f"GA4-only package contains unsupported platform residue in {path.relative_to(ROOT)}")
    schema_text = SCHEMA.read_text(encoding="utf-8")
    for forbidden_field in ("analytics_platforms", "platform_mappings", "implementation_payloads", "qa_cases", "qa_id"):
        if f'"{forbidden_field}"' in schema_text:
            fail(f"GA4 v2 schema still contains removed field {forbidden_field}")


def check_schema_and_fixture() -> None:
    schema = load_json(SCHEMA)
    Draft202012Validator.check_schema(schema)
    fixture = load_json(FIXTURE)
    errors = sorted(Draft202012Validator(schema).iter_errors(fixture), key=lambda item: list(item.path))
    if errors:
        fail("Generic GA4 fixture does not match schema:\n" + "\n".join(error.message for error in errors))
    if fixture.get("schema_version") != "2.1.0":
        fail("Generic fixture must use schema_version 2.1.0")
    event_ids = {event["event_id"] for event in fixture["events"]}
    covered = {event_id for evidence in fixture["screenshot_evidence"] for event_id in evidence["event_ids"]}
    if event_ids != covered:
        fail("Screenshot evidence must cover every fixture event exactly through explicit references")


def validator_issues(plan: dict, temp_dir: Path) -> list[dict]:
    path = temp_dir / "candidate.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-B", "scripts/validate_tracking_plan.py", str(path), "--format", "json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode not in {0, 1}:
        fail(f"Tracking plan validator failed\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def expect_code(base: dict, temp_dir: Path, code: str, mutate) -> None:
    candidate = copy.deepcopy(base)
    mutate(candidate)
    codes = {issue["code"] for issue in validator_issues(candidate, temp_dir)}
    if code not in codes:
        fail(f"Validator did not emit expected {code}; got {sorted(codes)}")


def check_validator() -> None:
    fixture = load_json(FIXTURE)
    with tempfile.TemporaryDirectory() as raw:
        temp_dir = Path(raw)
        issues = validator_issues(fixture, temp_dir)
        if issues:
            fail(f"Generic fixture has validator issues: {issues}")

        expect_code(
            fixture,
            temp_dir,
            "LEGACY_UA_FIELD",
            lambda plan: plan["parameters"][0].update({"parameter_name": "eventCategory"}),
        )
        expect_code(
            fixture,
            temp_dir,
            "SCREENSHOT_EVENT_MISSING",
            lambda plan: plan.update({"screenshot_evidence": plan["screenshot_evidence"][1:]}),
        )
        expect_code(
            fixture,
            temp_dir,
            "SCREENSHOT_FILE_MISSING",
            lambda plan: plan["screenshot_evidence"][0].update({"status": "captured", "file_name": ""}),
        )
        expect_code(
            fixture,
            temp_dir,
            "EVENT_ANALYSIS_USE_WEAK",
            lambda plan: plan["events"][0].update({"analysis_use": "reporting"}),
        )
        expect_code(
            fixture,
            temp_dir,
            "PARAMETER_DATA_OWNER_MISSING",
            lambda plan: plan["parameters"][0].update({"availability": "to_confirm", "data_owner": "TBD"}),
        )


def check_workbook(path: Path) -> None:
    wb = load_workbook(path, read_only=False, data_only=True)
    if wb.sheetnames != EXPECTED_TABS:
        fail(f"Unexpected workbook tabs: {wb.sheetnames}")

    overview = wb["00 Overview"]
    overview_text = " ".join(str(cell.value) for row in overview.iter_rows() for cell in row if cell.value is not None).lower()
    for forbidden in ("main users", "reviewed by", "template used", "qa cases", "automation cue"):
        if forbidden in overview_text:
            fail(f"Overview contains non-essential field: {forbidden}")

    parameter_headers = [cell.value for cell in wb["02 Parameter Reference"][3]]
    for expected in ("Variable name", "Display name", "Value rules", "Availability", "Data owner", "Register in GA4"):
        if expected not in parameter_headers:
            fail(f"Parameter Reference is missing {expected}")

    matrix = wb["03 Event Matrix"]
    if matrix.freeze_panes != "C6" or not str(matrix.auto_filter.ref).startswith("A5:F"):
        fail("Event Matrix must keep its parameter columns frozen and all event slots filterable")
    matrix_text = " ".join(str(cell.value) for row in matrix.iter_rows() for cell in row if cell.value is not None)
    for forbidden in ("event_id", "qa_id", "screenshot_id", "primary_platform"):
        if forbidden in matrix_text:
            fail(f"Event Matrix exposes internal field {forbidden}")

    datalayer_headers = [cell.value for cell in wb["04 DataLayer Examples"][3]]
    expected_datalayer_headers = ["Journey", "Event", "Evidence", "Trigger", "dataLayer.push example", "GTM and GA4 mapping", "Implementation notes"]
    if datalayer_headers[:7] != expected_datalayer_headers:
        fail(f"Unexpected DataLayer Examples headers: {datalayer_headers}")
    if wb["04 DataLayer Examples"].freeze_panes != "A4" or not str(wb["04 DataLayer Examples"].auto_filter.ref).startswith("A3:G"):
        fail("DataLayer Examples must keep headers frozen and all seven columns filterable")

    datalayer_text = " ".join(str(cell.value) for row in wb["04 DataLayer Examples"].iter_rows() for cell in row if cell.value is not None)
    for event in load_json(FIXTURE)["events"]:
        if event["event_name"] not in datalayer_text:
            fail(f"DataLayer Examples is missing event {event['event_name']}")

    screenshot_headers = [cell.value for cell in wb["05 Screenshot Register"][3]]
    expected_headers = ["Journey", "Event(s)", "Screenshot preview", "Page / component", "URL / route", "Capture objective", "Status", "Notes"]
    if screenshot_headers[:8] != expected_headers:
        fail(f"Unexpected Screenshot Register headers: {screenshot_headers}")


def check_generated_outputs() -> None:
    with tempfile.TemporaryDirectory() as raw:
        temp_dir = Path(raw)
        workbook = temp_dir / "plan.xlsx"
        csv_path = temp_dir / "plan.csv"
        run([sys.executable, "-B", "scripts/generate_tracking_plan_workbook.py", str(FIXTURE), "--output", str(workbook)], "Workbook generation")
        run([sys.executable, "-B", "scripts/export_tracking_plan_csv.py", str(FIXTURE), "--output", str(csv_path)], "CSV generation")
        check_workbook(workbook)
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        for expected in ("analysis_use", "evidence_status", "availability", "data_owner"):
            if expected not in csv_text.splitlines()[0]:
                fail(f"CSV output is missing {expected}")

    check_workbook(SKILL / "assets" / "ga4_tracking_plan_template.xlsx")


def check_catalog() -> None:
    run([sys.executable, "-B", "scripts/check_official_catalog.py", "--offline"], "Offline official catalog check")


def check_migration() -> None:
    fixture = load_json(FIXTURE)
    legacy = copy.deepcopy(fixture)
    legacy["schema_version"] = "1.1.0"
    legacy["analytics_platforms"] = ["ga4"]
    legacy["qa_cases"] = []
    with tempfile.TemporaryDirectory() as raw:
        temp_dir = Path(raw)
        source = temp_dir / "legacy.json"
        output = temp_dir / "migrated.json"
        source.write_text(json.dumps(legacy), encoding="utf-8")
        run([sys.executable, "-B", "scripts/migrate_tracking_plan.py", str(source), "--output", str(output)], "Contract migration")
        migrated = load_json(output)
        if migrated.get("schema_version") != "2.1.0" or "analytics_platforms" in migrated or "qa_cases" in migrated:
            fail("Contract migration did not produce a clean v2.1 plan")


def check_release_package() -> None:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "package.zip"
        run([sys.executable, "-B", "scripts/create_release_package.py", "--version", "validation", "--output", str(output)], "Release package")
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        if not any(name.endswith("skill/SKILL.md") for name in names):
            fail("Release package is missing skill/SKILL.md")
        for name in names:
            if any(part in BANNED_PATH_PARTS for part in Path(name).parts):
                fail(f"Release package contains banned path: {name}")


def check_privacy_and_cleanliness() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if "__pycache__" in relative.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if any(part in BANNED_PATH_PARTS - {"__pycache__"} for part in relative.parts):
            fail(f"Repository contains generated or release-only path: {relative}")
        if path.suffix.lower() == ".xlsx":
            check_xlsx_privacy(path, relative)
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            fail(f"Text file contains UTF-8 BOM: {relative}")
        text = raw.decode("utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(0)
                if value in {"GTM-XXXX", "GTM-XXXXXX", "G-XXXXXXXXXX"}:
                    continue
                fail(f"Potential {label} in {relative}: {value[:24]}")


def check_xlsx_privacy(path: Path, relative: Path) -> None:
    workbook = load_workbook(path, read_only=False, data_only=False)
    hidden = [sheet.title for sheet in workbook.worksheets if sheet.sheet_state != "visible"]
    if hidden:
        fail(f"Workbook contains hidden sheets in {relative}: {', '.join(hidden)}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if any("externalLinks" in name for name in names):
            fail(f"Workbook contains external links: {relative}")
        for name in names:
            if not name.endswith((".xml", ".rels")):
                continue
            text = archive.read(name).decode("utf-8", errors="ignore")
            if name.endswith(".rels") and 'TargetMode="External"' in text:
                relationships = ElementTree.fromstring(text)
                blocked = [
                    item.get("Target", "")
                    for item in relationships
                    if item.get("TargetMode") == "External" and not item.get("Type", "").endswith("/hyperlink")
                ]
                if blocked:
                    fail(f"Workbook contains an external data relationship in {relative}: {blocked[0]}")
            for label, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(text):
                    value = match.group(0)
                    if value in {"GTM-XXXX", "GTM-XXXXXX", "G-XXXXXXXXXX"}:
                        continue
                    fail(f"Potential {label} in {relative} ({name}): {value[:24]}")


CHECKS = [
    check_required_files,
    check_skill_metadata,
    check_reference_navigation,
    check_ga4_only_scope,
    check_schema_and_fixture,
    check_validator,
    check_generated_outputs,
    check_catalog,
    check_migration,
    check_release_package,
    check_privacy_and_cleanliness,
]


def main() -> int:
    for check in CHECKS:
        check()
        print(f"OK {check.__name__}")
    print("Package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
