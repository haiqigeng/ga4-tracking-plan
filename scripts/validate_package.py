from __future__ import annotations

import json
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
REQUIRED_REFERENCE_FILES = [
    SKILL / "references" / "ga4_event_scenario_library.md",
    SKILL / "references" / "ga4_event_scenario_library.json",
    SKILL / "references" / "official_ga4_recommended_events.json",
    SKILL / "references" / "tracking_plan_schema.json",
    SKILL / "references" / "generic_tracking_plan_fixture.json",
    SKILL / "references" / "scenario_ecommerce.md",
    SKILL / "references" / "scenario_lead_generation.md",
    SKILL / "references" / "scenario_search_listing.md",
    SKILL / "references" / "scenario_account_support_content.md",
    SKILL / "references" / "scenario_spa_routing.md",
    SKILL / "references" / "data_quality_privacy.md",
    SKILL / "references" / "qa_contract.md",
]
REQUIRED_SKILL_FILES = [
    SKILL / "SKILL.md",
    SKILL / "agents" / "openai.yaml",
    SKILL / "assets" / "ga4_tracking_plan_template.xlsx",
    ROOT / "scripts" / "create_tracking_plan_template.py",
    ROOT / "scripts" / "create_event_scenario_library.py",
    ROOT / "scripts" / "generate_tracking_plan_workbook.py",
    ROOT / "scripts" / "validate_package.py",
    *REQUIRED_REFERENCE_FILES,
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
    ROOT / "files" / "ga4_tracking_plan_template_v2_1.xlsx",
]
ALLOWED_PUBLIC_FILES = {
    "ga4_tracking_plan_template_v2_1.xlsx",
    "ga4_event_scenario_library.xlsx",
}
TEXT_SUFFIXES = {".md", ".py", ".yml", ".yaml", ".json", ".txt", ".gitignore", ".gitattributes"}
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


def fail(message: str) -> None:
    raise AssertionError(message)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def check_skill_resource_links() -> None:
    text = read_text(SKILL / "SKILL.md")
    for rel in [
        "assets/ga4_tracking_plan_template.xlsx",
        "references/ga4_event_scenario_library.md",
        "references/ga4_event_scenario_library.json",
        "references/official_ga4_recommended_events.json",
        "references/tracking_plan_schema.json",
        "references/generic_tracking_plan_fixture.json",
        "references/scenario_ecommerce.md",
        "references/scenario_lead_generation.md",
        "references/scenario_search_listing.md",
        "references/scenario_account_support_content.md",
        "references/scenario_spa_routing.md",
        "references/data_quality_privacy.md",
        "references/qa_contract.md",
    ]:
        if rel not in text:
            fail(f"SKILL.md does not mention bundled resource {rel}")
        if not (SKILL / rel).exists():
            fail(f"Bundled resource is missing: {rel}")


def load_json(path: Path):
    return json.loads(read_text(path))


def check_tracking_plan_contract() -> None:
    schema_path = SKILL / "references" / "tracking_plan_schema.json"
    fixture_path = SKILL / "references" / "generic_tracking_plan_fixture.json"
    schema = load_json(schema_path)
    fixture = load_json(fixture_path)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(fixture), key=lambda error: list(error.path))
    if errors:
        formatted = []
        for error in errors[:8]:
            path = ".".join(str(part) for part in error.path) or "<root>"
            formatted.append(f"{path}: {error.message}")
        fail("Generic fixture does not match tracking_plan_schema.json:\n" + "\n".join(formatted))

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

    for event in fixture["events"]:
        if event["classification"] == "recommended_ecommerce":
            event_parameters = set(event["parameters"])
            for required in ["items", "items[].item_id", "items[].item_name"]:
                if required not in event_parameters:
                    fail(f"{event['event_id']} ecommerce event is missing {required}")
            if not event["ga4_payload"].get("items"):
                fail(f"{event['event_id']} ecommerce event has no GA4 items payload example")


def check_generated_workbook() -> None:
    fixture_path = SKILL / "references" / "generic_tracking_plan_fixture.json"
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "generic_tracking_plan.xlsx"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_tracking_plan_workbook.py"),
                str(fixture_path),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            fail("Workbook generator failed:\n" + result.stdout + result.stderr)
        if not output.exists():
            fail("Workbook generator did not create the expected output file")
        check_event_matrix(output)


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
        for col in range(3, ws.max_column + 1, 2)
        if ws.cell(row, col).value not in (None, "")
    ]


def block_event_types(ws, start: int, end: int) -> list[str]:
    for row in range(start, end + 1):
        if ws.cell(row, 1).value == "event_type":
            return [str(value) for value in event_slot_values(ws, row)]
    return []


def check_event_matrix(workbook_path: Path) -> None:
    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        if wb.sheetnames != EXPECTED_TABS:
            fail(f"{display_path(workbook_path)} has unexpected tabs: {wb.sheetnames}")

        ws = wb["03 Event Matrix"]
        found_ecommerce_block = False
        for start, end in event_blocks(ws):
            block_name = str(ws.cell(start, 1).value or "")
            types = block_event_types(ws, start, end)
            is_ecommerce = any("ecommerce" in event_type.lower() for event_type in types) or "Ecommerce" in block_name or "Promotion" in block_name
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
                if ws.cell(row, 1).value == "event_name":
                    event_names = [str(value) for value in event_slot_values(ws, row)]
                    break
            if any(name in {"purchase", "refund"} for name in event_names) and "transaction_id" not in rows:
                fail(f"{display_path(workbook_path)} purchase/refund block {block_name} is missing transaction_id")

        allowed_statuses = {"OK", "KO", "Cannot test", None, ""}
        for col in range(4, ws.max_column + 1, 2):
            for row in range(6, ws.max_row + 1):
                value = ws.cell(row, col).value
                if value not in allowed_statuses:
                    fail(f"{display_path(workbook_path)} has invalid test status {value!r} at {ws.cell(row, col).coordinate}")

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


def check_public_files_are_generic() -> None:
    files_dir = ROOT / "files"
    if not files_dir.exists():
        fail("files/ is missing")
    unexpected = sorted(
        path.name
        for path in files_dir.iterdir()
        if path.is_file()
        and not path.name.startswith("~$")
        and path.name not in ALLOWED_PUBLIC_FILES
    )
    if unexpected:
        fail(f"files/ contains non-generic or unexpected public artifacts: {unexpected}")

    all_path_findings = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or path.name.startswith("~$"):
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
        check_skill_resource_links,
        check_tracking_plan_contract,
        check_public_files_are_generic,
        check_workbooks,
        check_generated_workbook,
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
