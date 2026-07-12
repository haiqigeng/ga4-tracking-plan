from __future__ import annotations

import argparse
import json
from pathlib import Path

from browser_environment import inspect_browser_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect the default browser and local Playwright readiness without launching a browser.")
    parser.add_argument("--output", "-o", type=Path, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = inspect_browser_environment()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(text)
    return 0 if result["readiness"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
