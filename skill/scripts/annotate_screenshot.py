from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

RED = (230, 0, 35, 255)


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must use x1,y1,x2,y2")
    try:
        x1, y1, x2, y2 = [int(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("box coordinates must be integers") from exc
    if x2 <= x1 or y2 <= y1:
        raise argparse.ArgumentTypeError("box must have positive width and height")
    return x1, y1, x2, y2


def annotate_screenshot(
    source: Path,
    output: Path,
    box: tuple[int, int, int, int],
    label: str | None,
    line_width: int,
) -> None:
    image = Image.open(source).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x1, y1, x2, y2 = box
    for offset in range(line_width):
        draw.rectangle((x1 - offset, y1 - offset, x2 + offset, y2 + offset), outline=RED)

    if label:
        label_width = max(160, 13 * len(label) + 34)
        label_box = (x1, max(0, y1 - 48), x1 + label_width, y1 - 8)
        draw.rounded_rectangle(label_box, radius=4, fill=RED)
        draw.text((label_box[0] + 14, label_box[1] + 10), label, fill=(255, 255, 255, 255))

    output.parent.mkdir(parents=True, exist_ok=True)
    annotated = Image.alpha_composite(image, overlay).convert("RGB")
    annotated.save(output, quality=95)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add a red target rectangle to a screenshot.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--box", required=True, type=parse_box, help="Target rectangle as x1,y1,x2,y2.")
    parser.add_argument("--label", help="Optional short label. Avoid labels for small workbook thumbnails.")
    parser.add_argument("--line-width", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    annotate_screenshot(args.source, args.output, args.box, args.label, max(1, args.line_width))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
