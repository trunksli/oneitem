"""
Feed connectors: articles (RSS/Atom), Vimeo films, and podcasts.

Parses feeds with the stdlib (xml.etree) to avoid new dependencies on the
pinned Python 3.6 environment. Articles get their readable text extracted for
the AI scoring prompt (stored in ContentCandidate.transcript, the same slot
YouTube transcripts use, and only until scored).

TikTok / Instagram Reels are intentionally NOT scraped here: neither offers a
public content API and scraping violates their ToS. The plan is to accept
those via user-submitted links (Phase C) using official embeds.
"""
import datetime
import os
import re
import requests
from urllib import robotparser
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, sources
from .previews import SCORING_TEXT_LIMIT, choose_preview

# Kept for callers that ingest without naming feeds.
SEED_FEEDS = sources.ARTICLE_FEEDS

MAX_ITEMS_PER_FEED = 10
ARTICLE_TEXT_LIMIT = 20000

ATOM_NS = "{http://www.w3.org/2005/Atom}"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"

# A well-behaved crawler says who it is and how to reach its operator.
CRAWLER_TOKEN = "ONE-curator"
USER_AGENT = "%s/0.2 (+%s; %s)" % (
    CRAWLER_TOKEN,
    os.getenv("PUBLIC_SITE_URL", "https://one-web-bwjk.onrender.com"),
    os.getenv("CRAWLER_CONTACT", "balmodyco@gmail.com"),
)

_robots_cache = {}


def allowed_by_robots(url):
    """Whether robots.txt permits fetching this page.

    Follows RFC 9309: a missing robots.txt (4xx) allows everything, while an
    unreachable one (5xx or a network error) is treated as disallowing
    everything. Cached per host for the life of the process.
    """
    parts = urlparse(url)
    base = "%s://%s" % (parts.scheme, parts.netloc)
    parser = _robots_cache.get(base)
    if parser is None:
        parser = robotparser.RobotFileParser()
        try:
            res = requests.get(base + "/robots.txt", timeout=10,
                               headers={"User-Agent": USER_AGENT})
            if res.status_code >= 500:
                parser.disallow_all = True
            elif res.status_code >= 400:
                parser.parse([])
            else:
                parser.parse(res.text.splitlines())
        except Exception:
            parser.disallow_all = True
        _robots_cache[base] = parser
    return parser.can_fetch(CRAWLER_TOKEN, url)


class _MetaExtractor(HTMLParser):
    """Pulls the social preview image out of an article page.

    Publishers already choose a representative image for og:image -- using it
    means articles get a real thumbnail rather than a blank rectangle, with no
    image generation and nothing invented.
    """
    IMAGE_PROPS = ("og:image", "og:image:url", "twitter:image", "twitter:image:src")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or self.image:
            return
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or "").strip().lower()
        content = (a.get("content") or "").strip()
        if key in self.IMAGE_PROPS and content.lower().startswith(("http://", "https://")):
            self.image = content


def first_sentences(text, count=2, limit=320):
    """The opening of an article, for the preview card.

    The author's own first sentences, not a paraphrase -- short enough to be fair
    use as a snippet and more honest than a generated summary.
    """
    if not text:
        return ""
    cleaned = re.sub(r'\s+', ' ', text).strip()
    parts = re.split(r'(?<=[.!?])\s+', cleaned)
    out = ""
    for part in parts[:count]:
        candidate = (out + " " + part).strip() if out else part
        if len(candidate) > limit:
            break
        out = candidate
    if not out:
        out = cleaned[:limit]
    if len(out) < len(cleaned):
        out = out.rstrip(" .") + "..."
    return out


class _TextExtractor(HTMLParser):
    """Crude but dependency-free: collects text from paragraph-ish tags."""
    BLOCK_TAGS = {"p", "li", "h1", "h2", "h3", "blockquote"}
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self._skip_depth = 0
        self._collecting = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self.BLOCK_TAGS:
            self._collecting += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in self.BLOCK_TAGS and self._collecting > 0:
            self._collecting -= 1
            self.chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0 and self._collecting > 0:
            self.chunks.append(data)

    def text(self):
        raw = "".join(self.chunks)
        return re.sub(r'\n{2,}', '\n\n', re.sub(r'[ \t]+', ' ', raw)).strip()


def is_safe_url(url):
    """Only http(s) links may be stored: a feed is third-party input, and a
    `javascript:` link would become one-click code execution in the browser."""
    return bool(url) and url.strip().lower().startswith(("http://", "https://"))


def strip_html(html_text: str) -> str:
    """Plain-text-ify a snippet of HTML (used for feed descriptions)."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_text or '')).strip()


def fetch_article(url: str):
    """Fetches an article once and returns (readable_text, preview_image_url)."""
    if not allowed_by_robots(url):
        # Respect the publisher: use only what their feed chose to syndicate.
        print(f"robots.txt disallows {url}; using feed content only")
        return "", None
    try:
        res = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
        res.raise_for_status()
        html = res.text

        meta = _MetaExtractor()
        meta.feed(html)

        extractor = _TextExtractor()
        extractor.feed(html)
        return extractor.text()[:ARTICLE_TEXT_LIMIT], meta.image
    except Exception as e:
        print(f"Could not fetch article for {url}: {e}")
        return "", None


def fetch_article_text(url: str) -> str:
    """Backwards-compatible wrapper returning only the text."""
    return fetch_article(url)[0]


def _parse_date(text):
    if not text:
        return None
    text = text.strip()
    # RFC 822 (RSS): "Mon, 25 Aug 2026 14:00:00 +0000" / "... GMT"
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            parsed = datetime.datetime.strptime(text, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue
    # ISO with fractional seconds, e.g. Atom "2026-08-25T14:00:00.123Z"
    match = re.match(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})', text)
    if match:
        try:
            return datetime.datetime.strptime(match.group(1) + " " + match.group(2), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None


def parse_duration(text):
    """Seconds from "2281", "38:01" or "00:38:01"; None if unreadable."""
    if not text:
        return None
    parts = text.strip().split(":")
    try:
        numbers = [int(float(p)) for p in parts]
    except ValueError:
        return None
    seconds = 0
    for n in numbers:
        seconds = seconds * 60 + n
    return seconds or None


def _first_text(element, *tags):
    for tag in tags:
        found = element.find(tag)
        if found is not None and (found.text or '').strip():
            return found.text.strip()
    return None


def _safe(url):
    return url.strip() if is_safe_url(url) else None


def _item_image(item):
    """The image a feed item carries itself, before any page is fetched."""
    for el in item.iter(MEDIA_NS + 'thumbnail'):
        if _safe(el.get('url')):
            return el.get('url').strip()
    for el in item.iter(MEDIA_NS + 'content'):
        if (el.get('medium') == 'image' or (el.get('type') or '').startswith('image/')) and _safe(el.get('url')):
            return el.get('url').strip()
    enclosure = item.find('enclosure')
    if enclosure is not None and (enclosure.get('type') or '').startswith('image/') and _safe(enclosure.get('url')):
        return enclosure.get('url').strip()
    itunes = item.find(ITUNES_NS + 'image')
    if itunes is not None and _safe(itunes.get('href')):
        return itunes.get('href').strip()
    return None


def _item_duration(item):
    seconds = parse_duration(_first_text(item, ITUNES_NS + 'duration'))
    if seconds:
        return seconds
    for el in item.iter(MEDIA_NS + 'content'):
        seconds = parse_duration(el.get('duration'))
        if seconds:
            return seconds
    return None


def parse_feed(xml_text: str):
    """Returns (feed_title, [entry dicts]) for RSS 2.0 or Atom.

    Each entry has title, url, description, published, plus what media feeds add:
    image (the item's own), feed_image (the show's cover art), audio_url (a
    podcast enclosure), duration (seconds) and guid.
    """
    root = ET.fromstring(xml_text)
    entries = []

    if root.tag == 'rss' or root.tag.endswith('rss'):
        channel = root.find('channel')
        if channel is None:
            return None, []
        feed_title = _first_text(channel, 'title')
        feed_link = _first_text(channel, 'link')
        cover = channel.find(ITUNES_NS + 'image')
        feed_image = _safe(cover.get('href')) if cover is not None else None
        feed_image = feed_image or _safe(_first_text(channel.find('image'), 'url')
                                         if channel.find('image') is not None else None)

        for item in channel.findall('item')[:MAX_ITEMS_PER_FEED]:
            enclosure = item.find('enclosure')
            audio = None
            if enclosure is not None and (enclosure.get('type') or '').startswith('audio/'):
                audio = _safe(enclosure.get('url'))
            link = _first_text(item, 'link')
            # Many podcasts link every episode to the show's home page; the audio
            # is the only thing that identifies the episode then.
            if audio and (not link or link == feed_link):
                link = audio
            if not link:
                continue
            description = (_first_text(item, 'description', CONTENT_NS + 'encoded',
                                       ITUNES_NS + 'summary') or "")
            entries.append({
                "title": _first_text(item, 'title') or "(untitled)",
                "url": link,
                "description": strip_html(description),
                "published": _parse_date(_first_text(item, 'pubDate')),
                "image": _item_image(item),
                "feed_image": feed_image,
                "audio_url": audio,
                "duration": _item_duration(item),
                "guid": _first_text(item, 'guid'),
            })
        return feed_title, entries

    if root.tag == ATOM_NS + 'feed':
        feed_title = _first_text(root, ATOM_NS + 'title')
        for entry in root.findall(ATOM_NS + 'entry')[:MAX_ITEMS_PER_FEED]:
            link = None
            for link_el in entry.findall(ATOM_NS + 'link'):
                if link_el.get('rel') in (None, 'alternate'):
                    link = link_el.get('href')
                    break
            if not link:
                continue
            entries.append({
                "title": _first_text(entry, ATOM_NS + 'title') or "(untitled)",
                "url": link,
                "description": strip_html(_first_text(entry, ATOM_NS + 'summary', ATOM_NS + 'content') or ""),
                "published": _parse_date(_first_text(entry, ATOM_NS + 'published', ATOM_NS + 'updated')),
                "image": _item_image(entry),
                "feed_image": None,
                "audio_url": None,
                "duration": None,
                "guid": _first_text(entry, ATOM_NS + 'id'),
            })
        return feed_title, entries

    return None, []


# ------------------------------------------------------------------ per medium

def _article_candidate(entry, feed_title, feed_url):
    # One request per new item yields both the text and the image
    article_text, image_url = fetch_article(entry['url'])
    # Prefer the article's own opening; fall back to the feed summary.
    # Quality-checked: sponsor reads and nav chrome are rejected here,
    # and the scorer will supply a written gist instead.
    preview = choose_preview(
        first_sentences(article_text), first_sentences(entry['description']))
    return models.ContentCandidate(
        source_type=models.SourceType.RSS,
        source_id=entry['url'],
        url=entry['url'],
        title=entry['title'],
        description=entry['description'],
        creator_name=feed_title or feed_url,
        creator_url=feed_url,
        upload_date=entry['published'],
        thumbnail_url=image_url or entry.get('image') or "",
        preview_text=preview,
        # Only what the scorer reads is kept, and only until it is scored.
        transcript=(article_text or "")[:SCORING_TEXT_LIMIT] or None,
    )


def _podcast_candidate(entry, feed_title, feed_url):
    """An episode. The audio is never downloaded -- the listener's player streams it."""
    if not entry.get('audio_url'):
        return None
    notes = entry['description'] or ""
    return models.ContentCandidate(
        source_type=models.SourceType.PODCAST,
        source_id=entry['audio_url'],
        url=entry['url'],
        title=entry['title'],
        description=notes[:SCORING_TEXT_LIMIT],
        creator_name=feed_title or feed_url,
        creator_url=feed_url,
        upload_date=entry['published'],
        # The episode's own art where it has one, else the show's cover
        thumbnail_url=entry.get('image') or entry.get('feed_image') or "",
        duration_seconds=entry.get('duration'),
        preview_text=choose_preview(first_sentences(notes)),
        # Show notes are what the scorer reads for a podcast
        transcript=notes[:SCORING_TEXT_LIMIT] or None,
    )


def vimeo_id(entry):
    """The numeric film id, from the guid ("tag:vimeo,...:clip123") or the link."""
    match = re.search(r'clip(\d+)', entry.get('guid') or '') or \
        re.search(r'vimeo\.com/(?:.*/)?(\d+)/?$', entry.get('url') or '')
    return match.group(1) if match else None


def vimeo_oembed(url):
    """Public film details from Vimeo's oEmbed endpoint; {} if unavailable."""
    try:
        res = requests.get("https://vimeo.com/api/oembed.json", params={"url": url},
                           timeout=15, headers={"User-Agent": USER_AGENT})
        return res.json() if res.ok else {}
    except Exception as e:
        print("Vimeo oEmbed failed for %s: %s" % (url, e))
        return {}


def _vimeo_candidate(entry, feed_title, feed_url):
    video_id = vimeo_id(entry)
    if not video_id:
        return None
    url = "https://vimeo.com/%s" % video_id
    info = vimeo_oembed(url)
    # oEmbed returns a small thumbnail; the same image is served at any size
    thumb = _safe(info.get('thumbnail_url')) or ""
    thumb = re.sub(r'-d_\d+x\d+', '-d_1280x720', thumb)
    notes = strip_html(info.get('description') or "") or entry['description'] or ""
    return models.ContentCandidate(
        source_type=models.SourceType.VIMEO,
        source_id=video_id,
        url=url,
        title=info.get('title') or entry['title'],
        description=notes[:SCORING_TEXT_LIMIT],
        creator_name=info.get('author_name') or feed_title or "Vimeo",
        creator_url=_safe(info.get('author_url')) or url,
        upload_date=entry['published'],
        thumbnail_url=thumb,
        duration_seconds=info.get('duration') or entry.get('duration'),
        preview_text=choose_preview(first_sentences(notes)),
        transcript=notes[:SCORING_TEXT_LIMIT] or None,
    )


BUILDERS = {
    "article": _article_candidate,
    "podcast": _podcast_candidate,
    "vimeo": _vimeo_candidate,
}


def ingest_feeds(db: Session, feed_urls=None, kind="article", per_feed=None):
    """Ingests new items from feeds of one kind ("article", "podcast" or "vimeo")."""
    feed_urls = feed_urls if feed_urls is not None else SEED_FEEDS
    build = BUILDERS[kind]
    per_feed = per_feed or sources.NEW_ITEMS_PER_FEED
    added = 0
    for feed_url in feed_urls:
        print(f"Fetching {kind} feed: {feed_url}")
        try:
            res = requests.get(feed_url, timeout=20, headers={"User-Agent": USER_AGENT})
            res.raise_for_status()
            feed_title, entries = parse_feed(res.content)
            if not entries:
                print(f"No entries parsed from {feed_url}")
                continue

            new_here = 0
            for entry in entries:
                if new_here >= per_feed:
                    break
                if not is_safe_url(entry['url']):
                    print("Skipping entry with unsafe link: %r" % (entry['url'],))
                    continue
                keys = [entry['url']] + ([entry['audio_url']] if entry.get('audio_url') else [])
                if kind == "vimeo" and vimeo_id(entry):
                    keys.append("https://vimeo.com/%s" % vimeo_id(entry))
                existing = db.query(models.ContentCandidate).filter(or_(
                    models.ContentCandidate.url.in_(keys),
                    models.ContentCandidate.source_id.in_(keys))).first()
                if existing:
                    continue
                candidate = build(entry, feed_title, feed_url)
                if candidate is None:
                    continue
                if kind == "vimeo" and (candidate.duration_seconds or 0) and \
                        candidate.duration_seconds < sources.MIN_VIDEO_SECONDS:
                    continue
                db.add(candidate)
                db.flush()  # so a repeat of this item later in the feed is seen
                new_here += 1
                added += 1
            db.commit()
        except Exception as e:
            print(f"Error ingesting feed {feed_url}: {e}")
            db.rollback()
    print(f"{kind.capitalize()} ingestion complete: {added} new candidates.")
    return added
