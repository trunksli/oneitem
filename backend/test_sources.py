"""
Tests for the source expansion: podcast and Vimeo feed parsing, the scoring
budget's turn-taking between media, medium rotation when picking, and the new
source types round-tripping through the database.

    venv/Scripts/python.exe test_sources.py
"""
import datetime
import os
import sys
import tempfile
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, queries, slots
from app.jobs import select_for_scoring
from app.migrations import ensure_schema
from app.rss_ingestion import parse_duration, parse_feed, vimeo_id

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        failures.append(label)


PODCAST_XML = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
  <title>Test Show</title><link>https://show.example</link>
  <itunes:image href="https://img.example/cover.jpg"/>
  <item>
    <title>Episode One</title><link>https://show.example</link>
    <description>&lt;p&gt;An episode about bells.&lt;/p&gt;</description>
    <pubDate>Tue, 8 Sep 2026 08:00:00 +0000</pubDate>
    <enclosure url="https://audio.example/1.mp3" type="audio/mpeg" length="1"/>
    <itunes:duration>00:38:01</itunes:duration>
  </item>
  <item>
    <title>Episode Two</title><link>https://show.example/two</link>
    <description>Two.</description>
    <enclosure url="javascript:alert(1)" type="audio/mpeg"/>
    <itunes:image href="https://img.example/two.jpg"/>
    <itunes:duration>125</itunes:duration>
  </item>
</channel></rss>"""

VIMEO_XML = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>Vimeo Staff Picks</title><link>https://vimeo.com/channels/staffpicks</link>
  <item>
    <title>A Film</title>
    <link>https://vimeo.com/channels/staffpicks/1218291127</link>
    <guid isPermaLink="false">tag:vimeo,2026-09-09:clip1218291127</guid>
    <media:content medium="video" duration="270"/>
  </item>
</channel></rss>"""


def test_feed_parsing():
    print("Feed parsing")
    title, entries = parse_feed(PODCAST_XML)
    one, two = entries
    check("podcast feed title", title == "Test Show")
    check("episode linked to the show page is identified by its audio",
          one["url"] == "https://audio.example/1.mp3", one["url"])
    check("audio enclosure found", one["audio_url"] == "https://audio.example/1.mp3")
    check("show cover art available as a fallback", one["feed_image"] == "https://img.example/cover.jpg")
    check("hh:mm:ss duration read", one["duration"] == 2281, one["duration"])
    check("show notes are plain text", one["description"] == "An episode about bells.", one["description"])
    check("non-http enclosure is dropped", two["audio_url"] is None)
    check("episode's own art preferred", two["image"] == "https://img.example/two.jpg")
    check("plain-seconds duration read", two["duration"] == 125)

    _, films = parse_feed(VIMEO_XML)
    check("vimeo id from guid", vimeo_id(films[0]) == "1218291127")
    check("vimeo duration from media:content", films[0]["duration"] == 270)
    check("vimeo id from a plain link", vimeo_id({"url": "https://vimeo.com/555"}) == "555")
    check("no vimeo id from a channel page", vimeo_id({"url": "https://vimeo.com/channels/staffpicks"}) is None)
    check("unreadable duration is None", parse_duration("soon") is None)


def test_scoring_budget():
    print("Scoring budget")
    base = datetime.datetime(2026, 9, 1)

    def item(medium, days):
        return SimpleNamespace(source_type=medium, upload_date=base + datetime.timedelta(days=days),
                               discovered_date=None, name="%s-%d" % (medium, days))

    pending = [item("RSS", d) for d in range(10)] + [item("YOUTUBE", d) for d in (1, 2)] + [item("PODCAST", 3)]
    chosen = select_for_scoring(pending, 6)
    counts = {}
    for c in chosen:
        counts[c.source_type] = counts.get(c.source_type, 0) + 1
    check("every medium gets a turn", counts == {"PODCAST": 1, "YOUTUBE": 2, "RSS": 3}, counts)
    rss = [c.name for c in chosen if c.source_type == "RSS"]
    check("newest first within a medium", rss == ["RSS-9", "RSS-8", "RSS-7"], rss)
    check("never more than the budget", len(select_for_scoring(pending, 100)) == len(pending))


def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine("sqlite:///%s" % path)
    models.Base.metadata.create_all(engine)
    ensure_schema(engine)
    return sessionmaker(bind=engine)(), path


def candidate(cid, medium, theme, score, status=models.Status.PENDING_REVIEW):
    return models.ContentCandidate(
        id=cid, url="https://example.com/%s" % cid, source_id=cid, source_type=medium,
        title=cid, creator_name="c", status=status, theme=theme, diamond_score=score,
        discovered_date=datetime.datetime.utcnow())


def picked(article_score):
    db, path = make_db()
    try:
        before = slots.slot_start() - datetime.timedelta(hours=6)
        db.add(candidate("prev", models.SourceType.YOUTUBE, "Engineering", 80, models.Status.PUBLISHED))
        db.add(models.HourlyOne(publish_time=before, theme="Engineering", candidate_id="prev"))
        db.add(candidate("same-theme", models.SourceType.RSS, "Engineering", 99))
        db.add(candidate("video", models.SourceType.YOUTUBE, "History", 90))
        db.add(candidate("article", models.SourceType.RSS, "Food", article_score))
        db.commit()
        hourly = queries.promote_next_pick(db)
        return hourly.candidate_id if hourly else None
    finally:
        db.close()
        os.remove(path)


def test_medium_rotation():
    print("Medium rotation")
    check("near-tie from another medium wins after a video", picked(85) == "article", picked(85))
    check("a clearly better pick still wins", picked(70) == "video", picked(70))


def test_new_source_types():
    print("New source types")
    db, path = make_db()
    try:
        db.add(candidate("pod", models.SourceType.PODCAST, "Sound", 50))
        db.add(candidate("film", models.SourceType.VIMEO, "Film", 50))
        db.commit()
        pod = db.get(models.ContentCandidate, "pod")
        film = db.get(models.ContentCandidate, "film")
        check("podcast source type stored", pod.source_type == models.SourceType.PODCAST)
        check("vimeo source type stored", film.source_type == models.SourceType.VIMEO)
    finally:
        db.close()
        os.remove(path)


if __name__ == "__main__":
    test_feed_parsing()
    test_scoring_budget()
    test_medium_rotation()
    test_new_source_types()
    if failures:
        print("\n%d source check(s) FAILED: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("\nAll source checks passed.")
