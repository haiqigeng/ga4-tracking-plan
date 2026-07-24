from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill"
REFERENCES = SKILL / "references"
SCHEMA = REFERENCES / "schema-tracking-plan.json"
EXAMPLE = REFERENCES / "example-tracking-plan.json"
ASSET = SKILL / "assets" / "default-tracking-plan.xlsx"

REQUIRED_SKILL_FILES = {
    "SKILL.md",
    "release.json",
    "agents/openai.yaml",
    "assets/default-tracking-plan.xlsx",
    "references/product.md",
    "references/workflow.md",
    "references/official-first.md",
    "references/workbook-contract.md",
    "references/schema-tracking-plan.json",
    "references/schema-analysis-context.json",
    "references/example-tracking-plan.json",
    "references/library-ga4-recommended-events.json",
    "scripts/check_official_sources.py",
    "scripts/generate_tracking_plan_workbook.py",
    "scripts/import_tracking_plan_workbook.py",
    "scripts/validate_tracking_plan.py",
    "tests/test_skill.py",
}

ROOT_WRAPPERS = {
    "adapt_tracking_plan_workbook.py",
    "annotate_screenshot.py",
    "check_official_sources.py",
    "create_default_template.py",
    "diff_tracking_plans.py",
    "discover_site_journeys.py",
    "discover_site_journeys_playwright.py",
    "generate_tracking_plan_workbook.py",
    "import_tracking_plan_workbook.py",
    "inspect_browser_environment.py",
    "inspect_tracking_plan_template.py",
    "validate_tracking_plan.py",
}

BANNED_PACKAGE_PARTS = {
    ".git",
    "__pycache__",
    "deliverables",
    "generated",
    "release",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode:
        fail(f"{label} failed\n{result.stdout}\n{result.stderr}")
    return result


def check_required_files() -> None:
    root_files = {
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "requirements.txt",
        "pyproject.toml",
        "scripts/create_release_package.py",
        "scripts/validate_package.py",
    }
    missing = [
        relative
        for relative in sorted(root_files)
        if not (ROOT / relative).is_file()
    ]
    missing.extend(
        f"skill/{relative}"
        for relative in sorted(REQUIRED_SKILL_FILES)
        if not (SKILL / relative).is_file()
    )
    missing.extend(
        f"scripts/{name}"
        for name in sorted(ROOT_WRAPPERS)
        if not (ROOT / "scripts" / name).is_file()
    )
    if missing:
        fail("Missing required files: " + ", ".join(missing))


def check_metadata() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    release = load_json(SKILL / "release.json")
    example = load_json(EXAMPLE)
    version = str(project.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"Invalid project semantic version: {version}")
    if release.get("name") != "ga4-tracking-plan":
        fail("skill/release.json contains the wrong skill name")
    if release.get("version") != version:
        fail("pyproject.toml and skill/release.json versions differ")
    if release.get("schema_version") != example.get("schema_version"):
        fail("Release and example schema versions differ")
    if release.get("python_requires") != project.get("requires-python"):
        fail("Release and project Python requirements differ")
    try:
        date.fromisoformat(str(release.get("released_on", "")))
    except ValueError as error:
        raise RuntimeError("Invalid release date") from error

    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n"):
        fail("SKILL.md has no YAML frontmatter")
    for expected in (
        "name: ga4-tracking-plan",
        "## North Star",
        "Use one adaptive workflow and one quality standard.",
    ):
        if expected not in skill_text:
            fail(f"SKILL.md is missing: {expected}")
    if "## Scope Tiers" in skill_text:
        fail("SKILL.md reintroduces tracking-plan size tiers")
    if len(skill_text.splitlines()) > 500:
        fail("SKILL.md exceeds the progressive-disclosure limit")
    agent_text = (SKILL / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    )
    if "$ga4-tracking-plan" not in agent_text:
        fail("agents/openai.yaml does not invoke the skill")


def check_schema_and_example() -> None:
    schema = load_json(SCHEMA)
    example = load_json(EXAMPLE)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(example),
        key=lambda item: list(item.path),
    )
    if errors:
        fail(
            "Generic example does not match the schema:\n"
            + "\n".join(error.message for error in errors)
        )

    parameter = schema["$defs"]["parameter"]["properties"]
    if parameter["requirement"]["enum"] != [
        "required",
        "conditional",
        "optional",
    ]:
        fail("Parameter requirement contains non-contract values")
    if parameter["allowed_values"].get("maxItems") != 50:
        fail("Finite value domains must stop at 50 values")
    event_classes = schema["$defs"]["event"]["properties"][
        "classification"
    ]["enum"]
    if event_classes != [
        "official",
        "official_ecommerce",
        "custom",
        "context",
    ]:
        fail("Event classifications violate the manual-only contract")

    run(
        [
            sys.executable,
            "-B",
            "scripts/validate_tracking_plan.py",
            str(EXAMPLE),
            "--warnings-as-errors",
        ],
        "Example semantic validation",
    )


def check_workbook_round_trip() -> None:
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        workbook = directory / "tracking-plan.xlsx"
        imported = directory / "imported.json"
        run(
            [
                sys.executable,
                "-B",
                "scripts/generate_tracking_plan_workbook.py",
                str(EXAMPLE),
                "--output",
                str(workbook),
            ],
            "Workbook generation",
        )
        run(
            [
                sys.executable,
                "-B",
                "scripts/import_tracking_plan_workbook.py",
                str(workbook),
                "--output",
                str(imported),
            ],
            "Workbook import",
        )
        if load_json(imported) != load_json(EXAMPLE):
            fail("Generated workbook does not round-trip to the exact model")


def check_release_package() -> None:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "package.zip"
        run(
            [
                sys.executable,
                "-B",
                "scripts/create_release_package.py",
                "--version",
                "validation",
                "--output",
                str(output),
            ],
            "Release package generation",
        )
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            packaged_release = json.loads(
                archive.read("skill/release.json")
            )
            packaged_project = tomllib.loads(
                archive.read("pyproject.toml").decode("utf-8")
            )["project"]
        if packaged_release["version"] != packaged_project["version"]:
            fail("Release package contains inconsistent versions")
        required = {
            "skill/SKILL.md",
            "skill/assets/default-tracking-plan.xlsx",
            "skill/tests/test_skill.py",
            "scripts/validate_tracking_plan.py",
            "scripts/check_installed_skill_sync.py",
            "README.md",
            "LICENSE",
        }
        missing = sorted(required - names)
        if missing:
            fail("Release package is missing: " + ", ".join(missing))
        for name in names:
            if any(
                part in BANNED_PACKAGE_PARTS for part in Path(name).parts
            ):
                fail(f"Release package contains banned path: {name}")


def check_repository_cleanliness() -> None:
    if not ASSET.is_file():
        fail("Default workbook asset is missing")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if any(part == "__pycache__" for part in relative.parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo", ".zip"}:
            fail(f"Repository contains generated artifact: {relative}")
        if path.name.startswith("~$"):
            fail(f"Repository contains temporary workbook: {relative}")
        if path.suffix.lower() not in {
            ".md",
            ".py",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".txt",
            ".ps1",
        }:
            continue
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            fail(f"Text file contains a UTF-8 BOM: {relative}")
        text = raw.decode("utf-8", errors="ignore")
        client_markers = (
            "".join(("daxon", ".fr")),
            "".join(("kpark", ".fr")),
        )
        for client_marker in client_markers:
            if client_marker in text.casefold():
                fail(f"Repository contains client-specific data: {relative}")
        if re.search(r"gh[pousr]_[A-Za-z0-9]{30,}", text):
            fail(f"Repository contains a possible GitHub token: {relative}")


CHECKS = [
    check_required_files,
    check_metadata,
    check_schema_and_example,
    check_workbook_round_trip,
    check_release_package,
    check_repository_cleanliness,
]


def main() -> int:
    for check in CHECKS:
        check()
        print(f"OK {check.__name__}")
    print("Package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
