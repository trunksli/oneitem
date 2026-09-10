"""
Tests for share pages and link-preview cards (app/share.py).

    venv/Scripts/python.exe test_share.py

The most important check is escaping: titles come from third-party feeds, so a
share page that interpolated one raw would be stored cross-site scripting.
"""
import datetime
import io
import os
import sys
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, queries, share

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        failures.append(label)


EVIL_TITLE = 'A <b>bold</b> & "quoted" title</title><script>alert(1)</script>'


def seed(db):
    now = datetime.datetime.utcnow()
    db.add(models.ContentCandidate(
        id="cand-1", url="https://example.com/a", source_id="a",
        source_type=models.SourceType.RSS, title=EVIL_TITLE,
        creator_name="Quanta Magazine", theme="Space", tone="Fascinating",
        preview_text="Two plain sentences about the piece. Nothing more.",
        status=models.Status.PUBLISHED, diamond_score=80.0, discovered_date=now))
    db.add(models.HourlyOne(id="11111111-2222-3333-4444-555555555555",
                            publish_time=now.replace(minute=0, second=0, microsecond=0),
                            theme="Space", candidate_id="cand-1"))
    db.add(models.ContentCandidate(
        id="cand-2", url="https://example.com/b", source_id="b",
        source_type=models.SourceType.YOUTUBE, title="word " * 120,
        creator_name="A Channel With A Rather Long Name " * 3, theme="Oddities",
        status=models.Status.PUBLISHED, diamond_score=70.0, discovered_date=now))
    db.add(models.HourlyOne(id="long-title-pick", publish_time=now - datetime.timedelta(days=1),
                            theme="Oddities", candidate_id="cand-2"))
    db.commit()


def main():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    engine = create_engine("sqlite:///" + path, connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    pick_id = "11111111-2222-3333-4444-555555555555"

    try:
        seed(db)

        print("\nshare page")
        page = share.share_page(db, pick_id)
        check("third-party markup is escaped, not executed",
              "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page)
        check("quotes cannot break out of an attribute", '"quoted" title' not in page.split("<body>")[0])
        check("has an og:title", 'property="og:title"' in page)
        check("uses a large-image card", 'content="summary_large_image"' in page)
        check("og:image points at this pick's card",
              ('%s/og/%s.png' % (share.API_PUBLIC_URL, pick_id)) in page)
        check("canonical URL is the share link on the site's domain",
              ('%s/p/%s' % (share.PUBLIC_SITE_URL, pick_id)) in page)
        check("sends people on to the pick", ("?pick=%s" % pick_id) in page and "location.replace" in page)
        check("no meta refresh (crawlers must stay on the tags)", "http-equiv" not in page)
        check("description uses the preview", "Two plain sentences" in page)

        print("\nids")
        check("a real id is valid", share.is_valid_id(pick_id))
        for bad in ["../../etc/passwd", "<script>", "a/b", "", "x" * 65]:
            check("rejects %r" % bad[:20], not share.is_valid_id(bad))
        try:
            share.share_page(db, "../../etc/passwd")
            check("a malformed id is a 404, not a lookup", False)
        except queries.NotFound:
            check("a malformed id is a 404, not a lookup", True)
        try:
            share.share_page(db, "no-such-pick")
            check("an unknown id is a 404", False)
        except queries.NotFound:
            check("an unknown id is a 404", True)

        print("\ncards")
        png = share.render_card(db, pick_id)
        check("returns a PNG", png[:8] == b"\x89PNG\r\n\x1a\n")
        from PIL import Image
        size = Image.open(io.BytesIO(png)).size
        check("is 1200x630", size == (1200, 630), str(size))
        check("a repeat request is served from cache", share.render_card(db, pick_id) is png)
        long_png = share.render_card(db, "long-title-pick")
        check("a very long title still renders", Image.open(io.BytesIO(long_png)).size == (1200, 630))
        check("cards stay small enough to unfurl quickly", len(png) < 500000, "%d bytes" % len(png))
        print("  fonts used: %s" % share.fonts_in_use())
    finally:
        db.close()
        engine.dispose()
        try:
            os.remove(path)
        except OSError:
            pass

    print("")
    if failures:
        print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("All share checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
