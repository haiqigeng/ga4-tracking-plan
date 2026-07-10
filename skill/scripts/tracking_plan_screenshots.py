from __future__ import annotations

from pathlib import Path
from typing import Any

PREVIEW_WIDTH = 260
PREVIEW_HEIGHT = 160
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def screenshot_files(screenshot_dir: Path | None) -> dict[str, Path]:
    if not screenshot_dir or not screenshot_dir.exists():
        return {}
    return {
        path.name.lower(): path
        for path in sorted(screenshot_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }


def resolve_screenshot(evidence: dict[str, Any], files_by_name: dict[str, Path]) -> Path | None:
    file_name = Path(str(evidence.get("file_name", ""))).name.lower()
    return files_by_name.get(file_name) if file_name else None


def _bounded_crop(image, crop: dict[str, Any] | None):
    if crop:
        x = max(0, int(crop.get("x", 0)))
        y = max(0, int(crop.get("y", 0)))
        width = max(1, int(crop.get("width", image.width)))
        height = max(1, int(crop.get("height", image.height)))
        right = min(image.width, x + width)
        bottom = min(image.height, y + height)
        if right > x and bottom > y:
            return image.crop((x, y, right, bottom)), (x, y)
    crop_height = min(image.height, max(1, int(image.width * PREVIEW_HEIGHT / PREVIEW_WIDTH)))
    return image.crop((0, 0, image.width, crop_height)), (0, 0)


def create_screenshot_preview(
    source: Path,
    destination: Path,
    crop: dict[str, Any] | None = None,
    annotation: dict[str, Any] | None = None,
) -> Path | None:
    try:
        from PIL import Image as PILImage
        from PIL import ImageDraw, ImageOps
    except ImportError:
        return None

    with PILImage.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        cropped, origin = _bounded_crop(image, crop)
        original_width, original_height = cropped.size
        cropped.thumbnail((PREVIEW_WIDTH, PREVIEW_HEIGHT), PILImage.Resampling.LANCZOS)
        scale_x = cropped.width / original_width
        scale_y = cropped.height / original_height

        canvas = PILImage.new("RGB", (PREVIEW_WIDTH, PREVIEW_HEIGHT), "white")
        offset_x = (PREVIEW_WIDTH - cropped.width) // 2
        offset_y = (PREVIEW_HEIGHT - cropped.height) // 2
        canvas.paste(cropped, (offset_x, offset_y))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, PREVIEW_WIDTH - 1, PREVIEW_HEIGHT - 1), outline="#BBC8D6", width=1)

        if annotation:
            x1 = offset_x + (int(annotation.get("x1", 0)) - origin[0]) * scale_x
            y1 = offset_y + (int(annotation.get("y1", 0)) - origin[1]) * scale_y
            x2 = offset_x + (int(annotation.get("x2", 0)) - origin[0]) * scale_x
            y2 = offset_y + (int(annotation.get("y2", 0)) - origin[1]) * scale_y
            bounds = (
                max(0, min(PREVIEW_WIDTH - 1, round(x1))),
                max(0, min(PREVIEW_HEIGHT - 1, round(y1))),
                max(0, min(PREVIEW_WIDTH - 1, round(x2))),
                max(0, min(PREVIEW_HEIGHT - 1, round(y2))),
            )
            if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                draw.rectangle(bounds, outline="#D32F2F", width=3)

        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destination, "PNG", optimize=True)
        return destination
