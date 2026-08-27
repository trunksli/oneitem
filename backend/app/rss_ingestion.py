"""
Phase B connector: RSS/Atom feeds (blogs, magazines, essays).

Parses feeds with the stdlib (xml.etree) to avoid new dependencies on the
pinned Python 3.6 environment, and extracts readable article text for the AI
scoring prompt (stored in ContentCandidate.transcript, same slot YouTube
transcripts use).

TikTok / Instagram Reels are intentionally NOT scraped here: neither offers a
public content API and scraping violates their ToS. The plan is to accept
those via user-submitted links (Phase C) using official embeds.
"""
import datetime
import re
import requests
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from sqlalchemy.orm import Session

from . import models

# High-quality "obsessive expert" feeds. Edit freely.
SEED_FEEDS = [
    "https://www.quantamagazine.org/feed/",
    "https://aeon.co/feed.rss",
    "https://nautil.us/feed/",
]

MAX_ITEMS_PER_FEED = 10
ARTICLE_TEXT_LIMIT = 20000

ATOM_NS = "{http://www.w3.org/2005/Atom}"


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


def strip_html(html_text: str) -> str:
    """Plain-text-ify a snippet of HTML (used for feed descriptions)."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_text or '')).strip()


def fetch_article_text(url: str) -> str:
    """Fetches an article page and extracts readable text. Empty string on failure."""
    try:
        res = requests.get(url, timeout=20, headers={"User-Agent": "ONE-curator/0.1"})
        res.raise_for_status()
        extractor = _TextExtractor()
        extractor.feed(res.text)
        return extractor.text()[:ARTICLE_TEXT_LIMIT]
    except Exception as e:
        print(f"Could not fetch article text for {url}: {e}")
        return ""


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


def _first_text(element, *tags):
    for tag in tags:
        found = element.find(tag)
        if found is not None and (found.text or '').strip():
            return found.text.strip()
    return None


def parse_feed(xml_text: str):
    """Returns (feed_title, [entry dicts]) for RSS 2.0 or Atom."""
    root = ET.fromstring(xml_text)
    entries = []

    if root.tag == 'rss' or root.tag.endswith('rss'):
        channel = root.find('channel')
        if channel is None:
            return None, []
        feed_title = _first_text(channel, 'title')
        for item in channel.findall('item')[:MAX_ITEMS_PER_FEED]:
            link = _first_text(item, 'link')
            if not link:
                continue
            entries.append({
                "title": _first_text(item, 'title') or "(untitled)",
                "url": link,
                "description": strip_html(_first_text(item, 'description') or ""),
                "published": _parse_date(_first_text(item, 'pubDate')),
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
            })
        return feed_title, entries

    return None, []


def ingest_feeds(db: Session, feed_urls=None):
    """Ingests articles from RSS/Atom feeds as ContentCandidates."""
    feed_urls = feed_urls if feed_urls is not None else SEED_FEEDS
    added = 0
    for feed_url in feed_urls:
        print(f"Fetching feed: {feed_url}")
        try:
            res = requests.get(feed_url, timeout=20, headers={"User-Agent": "ONE-curator/0.1"})
            res.raise_for_status()
            feed_title, entries = parse_feed(res.text)
            if not entries:
                print(f"No entries parsed from {feed_url}")
                continue

            for entry in entries:
                existing = db.query(models.ContentCandidate).filter_by(url=entry['url']).first()
                if existing:
                    continue
                # Fetch full text only for new items (one HTTP request each)
                article_text = fetch_article_text(entry['url'])
                candidate = models.ContentCandidate(
                    source_type=models.SourceType.RSS,
                    source_id=entry['url'],
                    url=entry['url'],
                    title=entry['title'],
                    description=entry['description'],
                    creator_name=feed_title or feed_url,
                    creator_url=feed_url,
                    upload_date=entry['published'],
                    thumbnail_url="",
                    transcript=article_text,
                )
                db.add(candidate)
                added += 1
            db.commit()
        except Exception as e:
            print(f"Error ingesting feed {feed_url}: {e}")
            db.rollback()
    print(f"RSS ingestion complete: {added} new candidates.")
    return added
