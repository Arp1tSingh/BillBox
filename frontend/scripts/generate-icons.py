"""Generate the PWA icons. Requires Pillow: `pip install pillow`.

Run from the frontend directory:
    python scripts/generate-icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "public" / "icons"
BRAND = (15, 118, 110, 255)
PAPER = (248, 250, 252, 255)


def draw_icon(size: int, *, maskable: bool = False) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = int(size * 0.22) if not maskable else 0
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=BRAND)

    # Maskable icons keep the receipt inside the 80% safe zone.
    scale = 0.66 if maskable else 0.78
    paper_w = size * scale
    paper_h = size * scale * 1.08
    left = (size - paper_w) / 2
    top = (size - paper_h) / 2
    right = left + paper_w
    bottom = top + paper_h
    tooth = paper_w * 0.1

    points = [(left, top), (right, top), (right, bottom - tooth)]
    x = right
    while x > left:
        points.append((x - tooth / 2, bottom))
        points.append((x - tooth, bottom - tooth))
        x -= tooth
    points.append((left, bottom - tooth))
    draw.polygon(points, fill=PAPER)

    line_w = max(2, int(size * 0.045))
    for index, width in enumerate((0.52, 0.52, 0.34)):
        y = top + paper_h * (0.28 + index * 0.2)
        draw.line(
            (left + paper_w * 0.2, y, left + paper_w * (0.2 + width), y),
            fill=BRAND,
            width=line_w,
        )
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_icon(192).save(OUT / "icon-192.png")
    draw_icon(512).save(OUT / "icon-512.png")
    draw_icon(512, maskable=True).save(OUT / "maskable-512.png")
    print(f"Wrote icons to {OUT}")


if __name__ == "__main__":
    main()
