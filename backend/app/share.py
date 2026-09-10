"""
Share pages and link-preview cards.

Link unfurlers (X, Bluesky, Slack, iMessage, Facebook) read Open Graph tags from
the HTML the server returns and do not run JavaScript. A static single-page site
therefore gives every shared link the same generic preview. For each pick the API
renders:

  /p/<id>        a small HTML page carrying that pick's own Open Graph tags. A
                 script sends people on to the pick; crawlers, which do not run
                 scripts, stay and read the tags. (No meta-refresh: some crawlers
                 follow those and would land on the generic home page instead.)
  /og/<id>.png   a 1200x630 card in the site's own typography. Text only -- no AI
                 imagery, and no fetching of third-party images from the server,
                 which would open a request-forgery hole for no real gain.

The static site rewrites /p/* and /og/* to the API (see DEPLOY.md), so shared
links live on the site's own domain.

Every value on the share page is HTML-escaped: titles come from third-party
feeds, and an unescaped one would be stored cross-site scripting.
"""
import html
import io
import json
import os
import re
import threading

from . import queries

PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "https://one-web-bwjk.onrender.com").rstrip("/")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "https://one-api-lcrh.onrender.com").rstrip("/")

SITE_NAME = "ONE"
TAGLINE = "One good thing, four times a day"

CARD_W, CARD_H = 1200, 630
PAPER = (253, 248, 243)
INK = (42, 26, 15)
INK_MUTED = (107, 88, 71)
ACCENT = (194, 65, 12)
LINE = (228, 215, 200)

# Pick ids are UUIDs; anything else never reaches the database or a URL.
_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")

SOURCE_LABELS = {"YOUTUBE": "YouTube", "RSS": "Article", "VIMEO": "Vimeo",
                 "PODCAST": "Podcast", "WEB": "Web"}


class CardUnavailable(Exception):
    """The image library is missing, so cards cannot be drawn (the API maps this to 503)."""


def is_valid_id(value):
    return bool(value) and bool(_ID.match(value))


def _pick(db, hourly_id):
    if not is_valid_id(hourly_id):
        raise queries.NotFound("No such pick")
    return queries.get_pick(db, hourly_id)


def _trim(text, limit):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "\u2026"


# ------------------------------------------------------------------ share page

def share_page(db, hourly_id):
    """HTML for /p/<id>: this pick's Open Graph tags, and a way on to the pick."""
    pick = _pick(db, hourly_id)
    candidate = pick.get("candidate") or {}

    title = _trim(candidate.get("title") or "A pick on ONE", 140)
    description = _trim(candidate.get("preview_text") or candidate.get("ai_explanation")
                        or TAGLINE, 220)
    share_url = "%s/p/%s" % (PUBLIC_SITE_URL, hourly_id)
    app_url = "%s/?pick=%s" % (PUBLIC_SITE_URL, hourly_id)
    image_url = "%s/og/%s.png" % (API_PUBLIC_URL, hourly_id)

    def e(value):
        return html.escape(value, quote=True)

    # json.dumps gives a valid JS string; replacing "</" stops it closing the tag.
    app_url_js = json.dumps(app_url).replace("</", "<\\/")

    return "\n".join([
        "<!doctype html>",
        '<html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s \u00b7 %s</title>" % (e(title), SITE_NAME),
        '<meta name="description" content="%s">' % e(description),
        '<link rel="canonical" href="%s">' % e(share_url),
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="%s">' % SITE_NAME,
        '<meta property="og:title" content="%s">' % e(title),
        '<meta property="og:description" content="%s">' % e(description),
        '<meta property="og:url" content="%s">' % e(share_url),
        '<meta property="og:image" content="%s">' % e(image_url),
        '<meta property="og:image:width" content="%d">' % CARD_W,
        '<meta property="og:image:height" content="%d">' % CARD_H,
        '<meta property="og:image:alt" content="%s">' % e("%s, featured on %s" % (title, SITE_NAME)),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % e(title),
        '<meta name="twitter:description" content="%s">' % e(description),
        '<meta name="twitter:image" content="%s">' % e(image_url),
        "<style>body{font-family:Georgia,serif;background:#FDF8F3;color:#2A1A0F;"
        "max-width:640px;margin:12vh auto;padding:0 24px;line-height:1.5}"
        "a{color:#C2410C}</style>",
        "<script>location.replace(%s);</script>" % app_url_js,
        "</head><body>",
        '<p><a href="%s">Continue to \u201c%s\u201d on %s</a></p>' % (e(app_url), e(title), SITE_NAME),
        "</body></html>",
    ])


# --------------------------------------------------------------------- cards

_FONT_FILES = {
    "serif": ["C:/Windows/Fonts/georgia.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
              "/usr/share/fonts/TTF/DejaVuSerif.ttf"],
    "serif-bold": ["C:/Windows/Fonts/georgiab.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
                   "/usr/share/fonts/TTF/DejaVuSerif-Bold.ttf"],
    "sans": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "sans-bold": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
}
# A bundled font wins over system fonts: drop e.g. serif.ttf / sans-bold.ttf here.
_BUNDLED_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

_font_cache = {}
_fonts_used = {}


def _font(kind, size):
    """The best available font of this kind, falling back to Pillow's own."""
    key = (kind, size)
    if key in _font_cache:
        return _font_cache[key]
    from PIL import ImageFont

    candidates = [os.path.join(_BUNDLED_DIR, kind + ".ttf")] + _FONT_FILES.get(kind, [])
    font = None
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                _fonts_used[kind] = path
                break
            except OSError:
                continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)  # scalable since Pillow 10.1
            _fonts_used[kind] = "pillow-default"
        except TypeError:
            font = ImageFont.load_default()           # older Pillow: small bitmap
            _fonts_used[kind] = "pillow-bitmap"
    _font_cache[key] = font
    return font


def fonts_in_use():
    """Which font file each style resolved to -- useful when a card looks wrong."""
    return dict(_fonts_used)


def _width(draw, text, font):
    return draw.textlength(text, font=font)


def _wrap(draw, text, font, max_width):
    """Greedy word wrap; words wider than a whole line are broken by character."""
    lines, current = [], ""
    for word in (text or "").split():
        trial = (current + " " + word).strip()
        if _width(draw, trial, font) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        while _width(draw, word, font) > max_width and len(word) > 1:
            cut = len(word)
            while cut > 1 and _width(draw, word[:cut], font) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


def _fit(draw, text, font, max_width):
    """Shorten text with an ellipsis until it fits the width."""
    if _width(draw, text, font) <= max_width:
        return text
    while text and _width(draw, text + "\u2026", font) > max_width:
        text = text[:-1]
    return text.rstrip() + "\u2026"


def draw_card(kicker, title, byline, footer=TAGLINE):
    """Render a 1200x630 PNG card and return its bytes."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise CardUnavailable("Pillow is not installed, so cards cannot be drawn")

    img = Image.new("RGB", (CARD_W, CARD_H), PAPER)
    draw = ImageDraw.Draw(img)
    margin = 72
    max_width = CARD_W - 2 * margin

    draw.rectangle([0, 0, CARD_W, 10], fill=ACCENT)  # the ember rule, as on the site
    draw.text((margin, 56), SITE_NAME, font=_font("serif-bold", 54), fill=INK)
    draw.text((margin, 130), _fit(draw, kicker, _font("sans-bold", 24), max_width),
              font=_font("sans-bold", 24), fill=ACCENT)

    # The title gets the largest size at which it fits the available height.
    top, bottom = 188, CARD_H - 132
    for size in (76, 68, 60, 54, 48, 42):
        font = _font("serif", size)
        line_height = int(size * 1.2)
        lines = _wrap(draw, title, font, max_width)
        if len(lines) * line_height <= bottom - top:
            break
    else:
        keep = max(1, (bottom - top) // line_height)
        lines = lines[:keep]
        lines[-1] = _fit(draw, lines[-1] + " \u2026", font, max_width)
    y = top
    for line in lines:
        draw.text((margin, y), line, font=font, fill=INK)
        y += line_height

    draw.line([margin, CARD_H - 104, CARD_W - margin, CARD_H - 104], fill=LINE, width=2)
    footer_font = _font("sans", 24)
    footer_width = _width(draw, footer, footer_font)
    draw.text((CARD_W - margin - footer_width, CARD_H - 76), footer, font=footer_font, fill=ACCENT)
    byline_font = _font("sans", 28)
    draw.text((margin, CARD_H - 80),
              _fit(draw, byline or "", byline_font, max_width - footer_width - 40),
              font=byline_font, fill=INK_MUTED)

    buffer = io.BytesIO()
    img.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


_card_cache = {}
_card_order = []
_card_lock = threading.Lock()


def render_card(db, hourly_id):
    """PNG bytes for /og/<id>.png. Cached in memory: a pick's card never changes."""
    pick = _pick(db, hourly_id)
    candidate = pick.get("candidate") or {}
    hourly = pick.get("hourly") or {}

    title = candidate.get("title") or "A pick on ONE"
    kicker = " \u00b7 ".join(x for x in [(hourly.get("theme") or "").upper(),
                                        (candidate.get("tone") or "").upper()] if x) or "FEATURED"
    byline = " / ".join(x for x in [candidate.get("creator_name"),
                                    SOURCE_LABELS.get(candidate.get("source_type") or "", "")] if x)

    key = (hourly_id, title, kicker, byline)
    with _card_lock:
        if key in _card_cache:
            return _card_cache[key]
    png = draw_card(kicker, title, byline)
    with _card_lock:
        _card_cache[key] = png
        _card_order.append(key)
        while len(_card_order) > 256:
            _card_cache.pop(_card_order.pop(0), None)
    return png
