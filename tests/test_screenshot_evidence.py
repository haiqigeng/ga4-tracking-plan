from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

from generate_tracking_plan_workbook import build_workbook  # noqa: E402
from tracking_plan_screenshots import PREVIEW_HEIGHT, PREVIEW_WIDTH, create_screenshot_preview, resolve_screenshot, screenshot_files  # noqa: E402


class ScreenshotEvidenceTests(unittest.TestCase):
    def test_exact_file_mapping_and_standardized_preview(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            source = folder / "homepage.png"
            Image.new("RGB", (1200, 2400), "white").save(source)
            files = screenshot_files(folder)
            self.assertEqual(resolve_screenshot({"file_name": "homepage.png"}, files), source)
            self.assertIsNone(resolve_screenshot({"file_name": "other.png"}, files))

            output = folder / "preview.png"
            create_screenshot_preview(
                source,
                output,
                crop={"x": 0, "y": 0, "width": 1200, "height": 740},
                annotation={"x1": 100, "y1": 100, "x2": 500, "y2": 300},
            )
            with Image.open(output) as preview:
                self.assertEqual(preview.size, (PREVIEW_WIDTH, PREVIEW_HEIGHT))

    def test_workbook_uses_explicit_evidence_files(self) -> None:
        plan = json.loads((ROOT / "skill" / "references" / "03-rules" / "example-ga4-tracking-plan.json").read_text(encoding="utf-8"))
        plan = copy.deepcopy(plan)
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            Image.new("RGB", (800, 600), "red").save(folder / "page.png")
            Image.new("RGB", (800, 600), "blue").save(folder / "promotion.png")
            plan["screenshot_evidence"][0].update({"status": "captured", "file_name": "page.png"})
            plan["screenshot_evidence"][1].update({"status": "captured", "file_name": "promotion.png"})
            workbook = build_workbook(plan, screenshot_dir=folder, preview_dir=folder / "previews")
            images = workbook["05 Screenshot Register"]._images
            self.assertEqual(len(images), 2)
            self.assertEqual({(image.width, image.height) for image in images}, {(PREVIEW_WIDTH, PREVIEW_HEIGHT)})


if __name__ == "__main__":
    unittest.main()
