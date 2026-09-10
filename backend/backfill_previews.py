"""
Give existing content a thumbnail and a preview.

Articles ingested before preview support have thumbnail_url="" and no
preview_text, which is why the site and the archive show empty boxes. This
re-fetches each article once to pick up its og:image and opening sentences, and
derives a YouTube thumbnail from the video id where one is missing.

Safe to re-run: it only touches rows that are actually missing something.

    venv/Scripts/python.exe backfill_previews.py
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from app import database, models
from app.migrations import ensure_schema
from app.ai_scoring import call_llm
from app.previews import build_gist_prompt, is_usable
from app.rss_ingestion import fetch_article, first_sentences


def youtube_thumbnail(video_id):
    # hqdefault exists for every video, unlike maxresdefault
    return "https://i.ytimg.com/vi/%s/hqdefault.jpg" % video_id


def write_gist(candidate):
    """Ask the model for a clean two-sentence preview of the actual content."""
    body = (candidate.transcript or "")[:4000] or (candidate.description or "")
    if not body.strip():
        return None
    kind = "video" if candidate.source_type == models.SourceType.YOUTUBE else "article"
    result = call_llm(build_gist_prompt(candidate, body, kind))
    gist = (result or {}).get("gist", "").strip()
    return gist if gist and is_usable(gist) else None


def from_description(candidate):
    """A video preview lifted from its description rather than written from the content.

    Descriptions open with the sponsor read, and sponsor copy does not always use
    words a filter can catch -- so these are never trusted, only rewritten.
    """
    if candidate.source_type != models.SourceType.YOUTUBE:
        return False
    preview = (candidate.preview_text or "").rstrip(". …")
    description = " ".join((candidate.description or "").split())
    return bool(preview) and description.startswith(" ".join(preview.split())[:80])


def backfill(db, limit=None, use_llm=True):
    candidates = db.query(models.ContentCandidate).all()
    # Rewrite previews that are missing OR that are sponsor reads / nav chrome:
    # a bad preview is worse than none, because it misdescribes the content.
    needs_work = [
        c for c in candidates
        if not (c.thumbnail_url or "").strip() or not is_usable(c.preview_text)
        or from_description(c)
    ]
    if limit:
        needs_work = needs_work[:limit]

    print("%d of %d candidates need a thumbnail or preview." % (len(needs_work), len(candidates)))
    fixed_images = fixed_previews = 0

    for candidate in needs_work:
        is_youtube = candidate.source_type == models.SourceType.YOUTUBE

        if is_youtube:
            if not (candidate.thumbnail_url or "").strip() and candidate.source_id:
                candidate.thumbnail_url = youtube_thumbnail(candidate.source_id)
                fixed_images += 1
            if not is_usable(candidate.preview_text) or from_description(candidate):
                # A video description is mostly sponsor copy, so go straight to the model
                gist = write_gist(candidate) if use_llm else None
                if gist:
                    candidate.preview_text = gist
                    fixed_previews += 1
            print("  %-52s img=%-3s preview=%s" % (
                (candidate.title or "")[:50],
                "yes" if (candidate.thumbnail_url or "").strip() else "NO",
                "yes" if is_usable(candidate.preview_text) else "NO"))
            continue

        # Articles: one fetch yields both the social image and the opening lines
        text, image = fetch_article(candidate.url) if candidate.url else ("", None)
        if image and not (candidate.thumbnail_url or "").strip():
            candidate.thumbnail_url = image
            fixed_images += 1
        if not is_usable(candidate.preview_text):
            opening = first_sentences(text or candidate.transcript or candidate.description or "")
            preview = opening if is_usable(opening) else None
            if not preview and use_llm:
                preview = write_gist(candidate)
            if preview:
                candidate.preview_text = preview
                fixed_previews += 1
        print("  %-52s img=%-3s preview=%s" % (
            (candidate.title or "")[:50],
            "yes" if (candidate.thumbnail_url or "").strip() else "NO",
            "yes" if is_usable(candidate.preview_text) else "NO"))

    db.commit()
    print("Backfill complete: %d thumbnails, %d previews added." % (fixed_images, fixed_previews))

    unusable = [c for c in db.query(models.ContentCandidate).all() if not is_usable(c.preview_text)]
    print("Candidates still without a usable preview: %d" % len(unusable))
    return fixed_images, fixed_previews


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-llm"]
    use_llm = "--no-llm" not in sys.argv
    limit = int(args[0]) if args else None
    ensure_schema(database.engine)
    db = database.SessionLocal()
    try:
        backfill(db, limit, use_llm)
    finally:
        db.close()
