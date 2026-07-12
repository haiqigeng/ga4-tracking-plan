from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANNED_PARTS = {"deliverables", "generated", "release", "tracking-plan-corpus-analysis", "fresh-agent-evaluation-output", "__pycache__"}
PACKAGE_ROOTS = [ROOT / "skill"]
WRAPPER_NAMES = [
    "adapt_tracking_plan_workbook.py",
    "annotate_screenshot.py",
    "check_official_catalog.py",
    "diff_tracking_plans.py",
    "discover_site_journeys.py",
    "discover_site_journeys_playwright.py",
    "export_tracking_plan_csv.py",
    "generate_tracking_plan_workbook.py",
    "init_tracking_plan.py",
    "inspect_browser_environment.py",
    "inspect_tracking_plan_template.py",
    "migrate_tracking_plan.py",
    "validate_tracking_plan.py",
]
PACKAGE_FILES = [
    ROOT / "requirements.txt",
    ROOT / "README.md",
    ROOT / "LICENSE",
    ROOT / "scripts" / "_run_skill_script.py",
    ROOT / "scripts" / "check_installed_skill_sync.py",
    ROOT / "scripts" / "validate_fresh_agent_evals.py",
    *(ROOT / "scripts" / name for name in WRAPPER_NAMES),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a public release zip for the GA4 tracking plan skill.")
    parser.add_argument("--version", default="local", help="Version or release tag to include in the zip filename.")
    parser.add_argument("--output", "-o", type=Path, help="Output zip path. Defaults to release/ga4-tracking-plan-package-<version>.zip")
    return parser.parse_args()


def assert_public_path(path: Path) -> None:
    rel = path.relative_to(ROOT)
    if any(part in BANNED_PARTS for part in rel.parts):
        raise ValueError(f"Release package cannot include local artifact path: {rel}")
    if path.name.startswith("~$") or path.suffix.lower() in {".tmp", ".bak", ".log"}:
        raise ValueError(f"Release package cannot include temporary file: {rel}")


def iter_package_files() -> list[Path]:
    files: list[Path] = []
    for root in PACKAGE_ROOTS:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(ROOT)
            if any(part in BANNED_PARTS for part in rel.parts):
                continue
            if not path.is_file():
                continue
            assert_public_path(path)
            files.append(path)
    for path in PACKAGE_FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        assert_public_path(path)
        files.append(path)
    return files


def main() -> int:
    args = parse_args()
    output = args.output or ROOT / "release" / f"ga4-tracking-plan-package-{args.version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    files = iter_package_files()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
