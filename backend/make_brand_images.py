"""
Generate the site's static brand images from the same renderer as the share cards.

    venv/Scripts/python.exe make_brand_images.py

Writes:
  frontend/public/og-default.png   preview card for links to the site itself
  frontend/src/app/icon.png        512px app icon (Next.js metadata file)
  frontend/src/app/favicon.ico     replaces the default Next.js favicon

Re-run after changing the palette or the positioning line. The outputs are
committed, so the deployed site never needs Pillow for these.
"""
import os

from app.share import ACCENT, PAPER, _font, draw_card

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC = os.path.join(ROOT, "frontend", "public")
APP = os.path.join(ROOT, "frontend", "src", "app")


def default_card():
    png = draw_card(
        kicker="ONE GOOD THING, FOUR TIMES A DAY",
        title="The internet already showed you everything it wanted to. This is the other stuff.",
        byline="6am · 12pm · 6pm · midnight Eastern",
        footer="Chosen, not fed",
    )
    path = os.path.join(PUBLIC, "og-default.png")
    with open(path, "wb") as f:
        f.write(png)
    return path


def icon():
    """An ember square with a paper-coloured serif "1" -- ONE at 16 pixels."""
    from PIL import Image, ImageDraw

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=96, fill=ACCENT)
    font = _font("serif-bold", 380)
    left, top, right, bottom = draw.textbbox((0, 0), "1", font=font)
    x = (size - (right - left)) / 2 - left
    y = (size - (bottom - top)) / 2 - top
    draw.text((x, y), "1", font=font, fill=PAPER)

    png_path = os.path.join(APP, "icon.png")
    img.save(png_path)
    ico_path = os.path.join(APP, "favicon.ico")
    img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return png_path, ico_path


if __name__ == "__main__":
    print("wrote", default_card())
    for path in icon():
        print("wrote", path)
