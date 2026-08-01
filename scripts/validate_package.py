from __future__ import annotations

import hashlib
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
EXAMPLE = REFERENCES / "example-tracking-plan.json"
ASSET = SKILL / "assets" / "default-tracking-plan.xlsx"

REQUIRED_SKILL_FILES = {
    "SKILL.md",
    "release.json",
    "requirements.txt",
    "agents/openai.yaml",
    "assets/default-tracking-plan.xlsx",
    "references/product.md",
    "references/workflow.md",
    "references/official-first.md",
    "references/workbook-contract.md",
    "references/schema-tracking-plan.json",
    "references/schema-analysis-context.json",
    "references/schema-change-request.json",
    "references/schema-delivery-handoff.json",
    "references/schema-drift-report.json",
    "references/schema-expected-events.json",
    "references/schema-impact-report.json",
    "references/schema-interactive-journey.json",
    "references/example-tracking-plan.json",
    "references/example-analysis-context.json",
    "references/example-change-request.json",
    "references/example-interactive-journey.json",
    "references/library-ga4-recommended-events.json",
    "scripts/analyze_tracking_plan_change_impact.py",
    "scripts/build_tracking_plan_delivery.py",
    "scripts/capture_interactive_journey.py",
    "scripts/check_official_sources.py",
    "scripts/detect_tracking_plan_drift.py",
    "scripts/generate_tracking_plan_workbook.py",
    "scripts/import_tracking_plan_workbook.py",
    "scripts/validate_analysis_context.py",
    "scripts/validate_tracking_plan.py",
    "scripts/validate_tracking_plan_workbook.py",
    "tests/test_skill.py",
}

ROOT_WRAPPERS = {
    "adapt_tracking_plan_workbook.py",
    "analyze_tracking_plan_change_impact.py",
    "annotate_screenshot.py",
    "build_tracking_plan_delivery.py",
    "capture_interactive_journey.py",
    "check_official_sources.py",
    "create_default_template.py",
    "detect_tracking_plan_drift.py",
    "diff_tracking_plans.py",
    "discover_site_journeys.py",
    "discover_site_journeys_playwright.py",
    "generate_tracking_plan_workbook.py",
    "import_tracking_plan_workbook.py",
    "inspect_browser_environment.py",
    "inspect_tracking_plan_template.py",
    "validate_analysis_context.py",
    "validate_tracking_plan.py",
    "validate_tracking_plan_workbook.py",
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


def check_schemas_and_examples() -> None:
    schemas = {
        path.name: load_json(path)
        for path in sorted(REFERENCES.glob("schema-*.json"))
    }
    for name, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            raise RuntimeError(f"Invalid JSON Schema {name}: {error}") from error

    example_pairs = {
        "example-tracking-plan.json": "schema-tracking-plan.json",
        "example-analysis-context.json": "schema-analysis-context.json",
        "example-change-request.json": "schema-change-request.json",
        "example-interactive-journey.json": "schema-interactive-journey.json",
    }
    for example_name, schema_name in example_pairs.items():
        example = load_json(REFERENCES / example_name)
        errors = sorted(
            Draft202012Validator(schemas[schema_name]).iter_errors(example),
            key=lambda item: list(item.path),
        )
        if errors:
            fail(
                f"{example_name} does not match {schema_name}:\n"
                + "\n".join(error.message for error in errors)
            )

    schema = schemas["schema-tracking-plan.json"]

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
    run(
        [
            sys.executable,
            "-B",
            "scripts/validate_analysis_context.py",
            str(REFERENCES / "example-analysis-context.json"),
            "--plan",
            str(EXAMPLE),
            "--delivery",
        ],
        "Example analysis-context validation",
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


def check_delivery_bundle() -> None:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "delivery"
        run(
            [
                sys.executable,
                "-B",
                "scripts/build_tracking_plan_delivery.py",
                str(EXAMPLE),
                str(REFERENCES / "example-analysis-context.json"),
                "--output-dir",
                str(output),
                "--official-offline",
            ],
            "Atomic delivery build",
        )

        required = {
            "plan.json",
            "tracking-plan.xlsx",
            "handoff.json",
            "expected-events.json",
            "internal/analysis-context.json",
            "internal/official-check.json",
            "contracts/tracking-plan.schema.json",
            "contracts/analysis-context.schema.json",
            "contracts/expected-events.schema.json",
            "contracts/delivery-handoff.schema.json",
        }
        present = {
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        }
        missing = sorted(required - present)
        if missing:
            fail("Atomic delivery is missing: " + ", ".join(missing))
        if not any(name.startswith("schemas/") for name in present):
            fail("Atomic delivery contains no per-event dataLayer schemas")

        handoff = load_json(output / "handoff.json")
        expected_events = load_json(output / "expected-events.json")
        Draft202012Validator(load_json(REFERENCES / "schema-delivery-handoff.json")).validate(handoff)
        Draft202012Validator(load_json(REFERENCES / "schema-expected-events.json")).validate(expected_events)
        if handoff["skill"]["version"] != load_json(SKILL / "release.json")["version"]:
            fail("Delivery handoff contains the wrong skill version")
        for artifact in handoff["artifacts"]:
            artifact_path = output / artifact["path"]
            if not artifact_path.is_file():
                fail(f"Handoff references a missing artifact: {artifact['path']}")
            digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if digest != artifact["sha256"]:
                fail(f"Handoff hash mismatch: {artifact['path']}")


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
            "skill/references/schema-delivery-handoff.json",
            "skill/references/example-analysis-context.json",
            "skill/scripts/build_tracking_plan_delivery.py",
            "skill/scripts/capture_interactive_journey.py",
            "skill/tests/test_skill.py",
            "scripts/build_tracking_plan_delivery.py",
            "scripts/capture_interactive_journey.py",
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
    check_schemas_and_examples,
    check_workbook_round_trip,
    check_delivery_bundle,
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
