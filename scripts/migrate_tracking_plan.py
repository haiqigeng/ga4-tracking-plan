from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "skill" / "scripts"))
    runpy.run_path(
        str(root / "maintenance" / "scripts" / "migrate_tracking_plan.py"),
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
