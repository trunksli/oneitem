"""
Regenerate the site's derived brand images from the master artwork.

    venv/Scripts/python.exe make_brand_images.py

Masters (committed, edited by a designer, never by this script):
  frontend/public/brand/mark.png          the C with the coral star, square
  frontend/public/brand/wordmark.png      mark plus "Curiolet", horizontal
  frontend/public/brand/banner-dark.png   wordmark on navy, wide
  frontend/public/brand/banner-light.png  objects on cream, wide

Derived (overwritten here):
  frontend/src/app/icon.png        512px app icon
  frontend/src/app/apple-icon.png  180px icon for iOS home screens
  frontend/src/app/favicon.ico     browser tab icon, 16-64px
  frontend/public/og-default.png   1200x630 preview for links to the site itself

Re-run after replacing any master. Per-pick share cards are drawn at request
time by app/share.py and are not written here.
"""
import os

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRAND = os.path.join(ROOT, "frontend", "public", "brand")
PUBLIC = os.path.join(ROOT, "frontend", "public")
APP = os.path.join(ROOT, "frontend", "src", "app")

CARD_W, CARD_H = 1200, 630


def icons():
    """App icons from the square mark.

    RGBA throughout: Next.js refuses to build with an RGB .ico ("The PNG is not
    in RGBA format"), and the alpha channel costs nothing here.
    """
    mark = Image.open(os.path.join(BRAND, "mark.png")).convert("RGBA")
    icon = mark.resize((512, 512), Image.LANCZOS)

    png = os.path.join(APP, "icon.png")
    apple = os.path.join(APP, "apple-icon.png")
    ico = os.path.join(APP, "favicon.ico")
    icon.save(png)
    icon.resize((180, 180), Image.LANCZOS).save(apple)
    icon.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return png, apple, ico


def default_card():
    """The link preview for the site itself: the dark banner at card proportions.

    The banner is wider than a preview card, so it is scaled to height and
    centre-cropped, which keeps the wordmark centred and trims the far edges.
    """
    banner = Image.open(os.path.join(BRAND, "banner-dark.png")).convert("RGB")
    scale = CARD_H / banner.height
    wide = banner.resize((int(round(banner.width * scale)), CARD_H), Image.LANCZOS)
    left = max(0, (wide.width - CARD_W) // 2)
    card = wide.crop((left, 0, left + CARD_W, CARD_H))

    path = os.path.join(PUBLIC, "og-default.png")
    card.save(path)
    return path


if __name__ == "__main__":
    for path in icons():
        print("wrote", path)
    print("wrote", default_card())
