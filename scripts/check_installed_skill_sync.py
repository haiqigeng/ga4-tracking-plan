from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether the installed GA4 tracking-plan skill matches this repository.")
    parser.add_argument(
        "--installed",
        type=Path,
        default=Path.home() / ".codex" / "skills" / "ga4-tracking-plan",
        help="Installed skill folder.",
    )
    return parser.parse_args()


def hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def main() -> int:
    args = parse_args()
    source = ROOT / "skill"
    if not args.installed.exists():
        print(f"ERROR Installed skill folder does not exist: {args.installed}")
        return 1
    source_hashes = hashes(source)
    installed_hashes = hashes(args.installed)
    changed = sorted(path for path in source_hashes.keys() & installed_hashes.keys() if source_hashes[path] != installed_hashes[path])
    missing = sorted(source_hashes.keys() - installed_hashes.keys())
    extra = sorted(installed_hashes.keys() - source_hashes.keys())
    if changed or missing or extra:
        for label, values in (("changed", changed), ("missing", missing), ("extra", extra)):
            for value in values:
                print(f"{label.upper()} {value}")
        return 1
    print("Installed skill matches the repository skill tree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
