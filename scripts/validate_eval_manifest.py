from __future__ import annotations

import argparse
from pathlib import Path

from validate_fresh_agent_evals import DEFAULT_MANIFEST, load_json, validate_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate evaluation case structure without claiming agent execution.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    errors = validate_manifest(manifest)
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(f"Evaluation manifest passed ({len(manifest['cases'])} cases); no agent was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
