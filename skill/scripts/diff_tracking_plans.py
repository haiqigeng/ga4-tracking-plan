from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two GA4 tracking-plan JSON files by event and parameter definition.")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def entity_diff(before: list[dict[str, Any]], after: list[dict[str, Any]], key: str) -> dict[str, list[str]]:
    previous = {str(item[key]): item for item in before}
    current = {str(item[key]): item for item in after}
    return {
        "added": sorted(current.keys() - previous.keys()),
        "removed": sorted(previous.keys() - current.keys()),
        "changed": sorted(name for name in previous.keys() & current.keys() if previous[name] != current[name]),
    }


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_version": {"before": before.get("document", {}).get("version", ""), "after": after.get("document", {}).get("version", "")},
        "events": entity_diff(before.get("events", []), after.get("events", []), "event_id"),
        "parameters": entity_diff(before.get("parameters", []), after.get("parameters", []), "parameter_name"),
        "screenshot_evidence": entity_diff(before.get("screenshot_evidence", []), after.get("screenshot_evidence", []), "evidence_id"),
    }


def render_text(diff: dict[str, Any]) -> str:
    lines = [f"Version: {diff['document_version']['before']} -> {diff['document_version']['after']}"]
    for entity in ("events", "parameters", "screenshot_evidence"):
        lines.append(entity.replace("_", " ").title())
        for change in ("added", "removed", "changed"):
            values = diff[entity][change]
            lines.append(f"  {change}: {', '.join(values) if values else '-'}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    diff = compare(load(args.before), load(args.after))
    print(json.dumps(diff, indent=2, ensure_ascii=False) if args.format == "json" else render_text(diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
