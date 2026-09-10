"""
All database logic, deliberately free of any web-framework import.

Kept separate from main.py so it can be exercised directly (see test_queries.py)
without needing FastAPI installed, and so the HTTP layer stays thin.

Every function returns plain JSON-ready values (strings, numbers, dicts) rather
than ORM objects, so serialization behaves identically across library versions.
"""
import datetime
import os

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from . import models, slots
from .themes import DEFAULT_THEME, normalize_theme

MAX_COMMENT_LENGTH = 500
MAX_DISPLAY_NAME_LENGTH = 40

# Pick selection: how many top candidates are considered, and how close (in
# diamond points) a candidate from a different medium must be to win the slot.
ROTATION_WINDOW = 25
MEDIUM_ROTATION_MARGIN = float(os.getenv("MEDIUM_ROTATION_MARGIN", "10"))


class NotFound(Exception):
    """Raised when a requested row does not exist; the HTTP layer maps it to 404."""


SAFE_URL_SCHEMES = ("http://", "https://")


def _safe_url(value):
    """Return the URL only if it is http(s).

    Feed and API data is third-party: a `javascript:` or `data:` link would reach
    an <a href> or window.open() in the browser and execute. Checked on output as
    well as on ingestion so rows stored before validation existed stay harmless.
    """
    if not value:
        return None
    if value.strip().lower().startswith(SAFE_URL_SCHEMES):
        return value
    return None


def _plain(value):
    """Normalize enums to their string value and datetimes to ISO strings."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    value_attr = getattr(value, "value", None)
    if value_attr is not None and hasattr(value, "name"):
        return value_attr
    return value


def _candidate_summary(candidate):
    if candidate is None:
        return {}
    return {
        "title": candidate.title,
        "creator_name": candidate.creator_name,
        "creator_url": _safe_url(candidate.creator_url),
        "url": _safe_url(candidate.url),
        "thumbnail_url": _safe_url(candidate.thumbnail_url),
        "source_type": _plain(candidate.source_type),
        "source_id": candidate.source_id,
        "preview_text": candidate.preview_text,
        "tone": candidate.tone,
    }


# ---------------------------------------------------------------- public reads

def promote_next_pick(db):
    """Fill the current publishing slot with the best pending candidate.

    Pure database work -- candidates are already ingested and scored, so this makes
    no network calls and is cheap enough to run inside a request (see get_hourly).
    Returns the new HourlyOne, or None if the slot is already filled or nothing is
    waiting for review.
    """
    now = datetime.datetime.utcnow()
    current_slot = slots.slot_start(now)
    following_slot = slots.next_slot_start(now)

    existing = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time >= current_slot,
        models.HourlyOne.publish_time < following_slot).first()
    if existing is not None:
        return None

    # Theme rotation: prefer a top candidate whose theme differs from the previous
    # pick's, so the same theme does not run back-to-back all day.
    previous = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time < current_slot
    ).order_by(models.HourlyOne.publish_time.desc()).first()

    pending = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.status == models.Status.PENDING_REVIEW)
    by_score = models.ContentCandidate.diamond_score.desc()

    contenders = []
    if previous is not None and previous.theme:
        contenders = pending.filter(
            models.ContentCandidate.theme != previous.theme
        ).order_by(by_score).limit(ROTATION_WINDOW).all()

    # Fall back to the overall best if every remaining candidate shares the theme
    if not contenders:
        contenders = pending.order_by(by_score).limit(ROTATION_WINDOW).all()

    if not contenders:
        return None
    top_candidate = contenders[0]

    # Medium rotation: after a video, prefer a near-equal article or podcast (and so
    # on), so the day is not four videos running. Only among near-ties -- a clearly
    # better pick still wins, whatever it is.
    previous_candidate = db.get(models.ContentCandidate, previous.candidate_id) \
        if previous is not None and previous.candidate_id else None
    if previous_candidate is not None:
        floor = (top_candidate.diamond_score or 0) - MEDIUM_ROTATION_MARGIN
        for contender in contenders:
            if (contender.diamond_score or 0) < floor:
                break
            if contender.source_type != previous_candidate.source_type:
                top_candidate = contender
                break

    hourly = models.HourlyOne(
        publish_time=current_slot,
        theme=top_candidate.theme or DEFAULT_THEME,
        candidate_id=top_candidate.id,
        editorial_explanation=top_candidate.ai_explanation,
        views_at_feature=top_candidate.view_count,  # snapshot for the 7-day delta
    )
    top_candidate.status = models.Status.PUBLISHED
    db.add(hourly)
    db.commit()
    return hourly


def get_hourly(db):
    """The current slot's pick, falling back to the latest so the site is never blank."""
    now = datetime.datetime.utcnow()
    slot_begins = slots.slot_start(now)

    def current_pick():
        return db.query(models.HourlyOne).filter(
            models.HourlyOne.publish_time >= slot_begins,
            models.HourlyOne.publish_time <= datetime.datetime.utcnow(),
        ).order_by(models.HourlyOne.publish_time.desc()).first()

    hourly = current_pick()

    # Lazy scheduling: fill this slot on demand rather than relying on a background
    # thread having survived. Free/sleepy hosts kill the process between requests,
    # so the loop in jobs.py rarely lives long enough to reach the next slot.
    if hourly is None and os.getenv("LAZY_SCHEDULING", "1") != "0":
        try:
            promote_next_pick(db)
        except IntegrityError:
            # Another request won the race for this slot; publish_time is unique.
            db.rollback()
        except Exception:
            db.rollback()
            raise
        hourly = current_pick()

    is_stale = False
    if hourly is None:
        hourly = db.query(models.HourlyOne).order_by(
            models.HourlyOne.publish_time.desc()).first()
        is_stale = True
    if hourly is None:
        raise NotFound("No hourly one found")

    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == hourly.candidate_id).first()

    payload = {"id": candidate.id} if candidate is not None else {}
    payload.update(_candidate_summary(candidate))
    if candidate is not None:
        payload["ai_explanation"] = candidate.ai_explanation

    return {
        "hourly": {
            "id": hourly.id,
            "publish_time": _plain(hourly.publish_time),
            "theme": _plain(hourly.theme),
            "editorial_explanation": hourly.editorial_explanation,
        },
        "candidate": payload or None,
        "is_stale": is_stale,
        "next_publish_time": _plain(slots.next_slot_start(now)),
    }


def get_pick(db, hourly_id):
    """One specific featured pick, addressed by id -- the permalink target.

    Same payload shape as get_hourly so the page can render either without
    branching, plus is_permalink so it can show the "back to now" affordance.
    """
    hourly = db.query(models.HourlyOne).filter(
        models.HourlyOne.id == hourly_id).first()
    if hourly is None:
        raise NotFound("No such pick")

    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == hourly.candidate_id).first()

    payload = {"id": candidate.id} if candidate is not None else {}
    payload.update(_candidate_summary(candidate))
    if candidate is not None:
        payload["ai_explanation"] = candidate.ai_explanation

    return {
        "hourly": {
            "id": hourly.id,
            "publish_time": _plain(hourly.publish_time),
            "theme": _plain(hourly.theme),
            "editorial_explanation": hourly.editorial_explanation,
        },
        "candidate": payload or None,
        "is_stale": False,
        "is_permalink": True,
        "next_publish_time": _plain(slots.next_slot_start()),
    }


def get_status(db):
    """Operational snapshot for diagnosing a deployment in one request.

    Deliberately public and deliberately secret-free: it reports whether keys and
    the database are configured, never their values.
    """
    now = datetime.datetime.utcnow()
    current_slot = slots.slot_start(now)
    pipeline_every = int(os.getenv("PIPELINE_EVERY_HOURS", "6"))

    # Every database section is individually guarded. The whole point of this
    # endpoint is to explain a broken deployment, so it has to keep answering when
    # the database is the broken part -- an earlier version 500'd alongside
    # everything else and was useless exactly when it was needed.
    errors = []

    def attempt(label, fn, default=None):
        try:
            return fn()
        except Exception as e:
            db.rollback()
            errors.append("%s: %s" % (label, e))
            return default

    counts = {}
    for status, total in attempt("candidates_by_status", lambda: db.query(
            models.ContentCandidate.status, func.count()
    ).group_by(models.ContentCandidate.status).all(), []):
        counts[_plain(status) or "UNKNOWN"] = total

    by_source = {}
    for source, total in attempt("candidates_by_source", lambda: db.query(
            models.ContentCandidate.source_type, func.count()
    ).group_by(models.ContentCandidate.source_type).all(), []):
        by_source[_plain(source) or "UNKNOWN"] = total

    latest_discovered = attempt("last_ingestion", lambda: db.query(
        func.max(models.ContentCandidate.discovered_date)).scalar())
    pipeline_due = (
        True if latest_discovered is None
        else (now - latest_discovered).total_seconds() >= pipeline_every * 3600
    )

    this_hour = attempt("current_slot", lambda: db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time == current_slot).first())
    latest = attempt("latest_hour", lambda: db.query(models.HourlyOne).order_by(
        models.HourlyOne.publish_time.desc()).first())
    latest_candidate = None
    if latest is not None:
        latest_candidate = attempt("latest_candidate", lambda: db.query(
            models.ContentCandidate).filter(
            models.ContentCandidate.id == latest.candidate_id).first())

    # Missing columns are the most likely cause of blanket 500s, so name them here.
    from .migrations import verify_schema
    missing_columns = attempt("schema_check", lambda: verify_schema(db.get_bind()), ["<unknown>"])

    database_url = os.getenv("DATABASE_URL") or ""
    if database_url.startswith("postgres"):
        backend = "postgres"
    elif database_url:
        backend = "other"
    else:
        backend = "sqlite (ephemeral on most hosts)"

    return {
        "status": "degraded" if (errors or missing_columns) else "ok",
        "utc_now": _plain(now),
        "current_slot": _plain(current_slot),
        "next_slot": _plain(slots.next_slot_start(now)),
        "slot_timezone": slots.SLOT_TIMEZONE,
        "slot_hours_local": slots.SLOT_HOURS,

        "schema": {
            "ok": not missing_columns,
            "missing_columns": missing_columns,
            "hint": ("Redeploy the API, or run `python migrate.py`, to apply pending "
                     "schema changes." if missing_columns else None),
        },
        "errors": errors,

        "config": {
            "database": backend,
            "gemini_key_configured": bool(os.getenv("GEMINI_API_KEY")),
            "youtube_key_configured": bool(os.getenv("YOUTUBE_API_KEY")),
            "admin_token_configured": bool(os.getenv("ADMIN_TOKEN")),
            "background_scheduler_enabled": os.getenv("RUN_SCHEDULER") == "1",
            "lazy_scheduling_enabled": os.getenv("LAZY_SCHEDULING", "1") != "0",
            "allowed_origins": os.getenv("ALLOWED_ORIGINS", "*"),
            "pipeline_every_hours": pipeline_every,
            "outcome_check_days": int(os.getenv("OUTCOME_CHECK_DAYS", "7")),
        },

        "content": {
            "candidates_by_status": counts,
            "candidates_by_source": by_source,
            "ready_to_feature": counts.get("PENDING_REVIEW", 0),
            "last_ingestion": _plain(latest_discovered),
            "pipeline_due": pipeline_due,
        },

        "schedule": {
            "hours_published": attempt("hours_published", lambda: db.query(
                func.count(models.HourlyOne.id)).scalar()) or 0,
            "current_slot_filled": this_hour is not None,
            "latest_publish_time": _plain(latest.publish_time) if latest else None,
            "latest_title": latest_candidate.title if latest_candidate else None,
            "outcomes_pending_check": attempt("outcomes_pending", lambda: db.query(
                func.count(models.HourlyOne.id)).filter(
                models.HourlyOne.outcome_checked_at.is_(None)).scalar()) or 0,
        },

        "engagement": {
            "comments_total": attempt("comments_total", lambda: db.query(
                func.count(models.Comment.id)).scalar()) or 0,
            "feedback_total": attempt("feedback_total", lambda: db.query(
                func.count(models.Feedback.id)).scalar()) or 0,
        },
    }


def get_comments(db, limit=50):
    """Today's chat only (UTC midnight cutoff), newest `limit`, oldest-first for display."""
    today_start = datetime.datetime.utcnow().replace(
        hour=0, minute=0, second=0, microsecond=0)
    rows = db.query(models.Comment).filter(
        models.Comment.created_at >= today_start
    ).order_by(models.Comment.created_at.desc()).limit(max(1, min(limit, 200))).all()
    rows = list(reversed(rows))
    return [{
        "id": c.id,
        "content": c.content,
        "display_name": c.display_name,
        "created_at": _plain(c.created_at),
    } for c in rows]


def create_comment(db, content, display_name=None):
    """Validates and stores a chat message. Raises ValueError on bad input."""
    content = (content or "").strip()
    if not content:
        raise ValueError("Comment content is required")
    if len(content) > MAX_COMMENT_LENGTH:
        raise ValueError("Comment too long (max %d chars)" % MAX_COMMENT_LENGTH)
    name = (display_name or "").strip()[:MAX_DISPLAY_NAME_LENGTH] or None

    comment = models.Comment(content=content, display_name=name)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id, "content": comment.content, "display_name": comment.display_name}


def create_feedback(db, hourly_one_id, seen_before, visitor_key=None):
    """Records a New-to-me / Already-knew vote against a pick.

    With a visitor key, a second vote from the same person changes their answer
    instead of adding another, so the new-to-me rate -- the core incrementality
    signal -- cannot be inflated by clicking twice or refreshing. The key is a
    daily-salted hash computed server-side (see visitors.py); nothing identifying
    is stored.
    """
    if not hourly_one_id:
        raise ValueError("hourly_one_id is required")
    try:
        seen = models.SeenBefore(seen_before)
    except ValueError:
        raise ValueError("seen_before must be one of %s" % [s.value for s in models.SeenBefore])
    if db.query(models.HourlyOne.id).filter(models.HourlyOne.id == hourly_one_id).first() is None:
        raise NotFound("No such pick")

    if visitor_key:
        link = db.query(models.FeedbackKey).filter(
            models.FeedbackKey.hourly_one_id == hourly_one_id,
            models.FeedbackKey.visitor_key == visitor_key).first()
        if link is not None:
            existing = db.query(models.Feedback).filter(
                models.Feedback.id == link.feedback_id).first()
            if existing is not None:
                existing.seen_before = seen
                db.commit()
                return {"id": existing.id, "seen_before": _plain(existing.seen_before),
                        "changed": True}

    feedback = models.Feedback(hourly_one_id=hourly_one_id, seen_before=seen)
    db.add(feedback)
    db.flush()
    if visitor_key:
        db.add(models.FeedbackKey(hourly_one_id=hourly_one_id, visitor_key=visitor_key,
                                  feedback_id=feedback.id))
    try:
        db.commit()
    except IntegrityError:
        # Two simultaneous first votes from one visitor: the retry finds the
        # winner's link and updates it, so this recurses at most once.
        db.rollback()
        return create_feedback(db, hourly_one_id, seen_before, visitor_key)
    db.refresh(feedback)
    return {"id": feedback.id, "seen_before": _plain(feedback.seen_before), "changed": False}


def get_archive(db, limit=100):
    """Past Diamonds: every previously featured pick, newest first."""
    now = datetime.datetime.utcnow()
    hourlies = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time <= now
    ).order_by(models.HourlyOne.publish_time.desc()).limit(max(1, min(limit, 200))).all()
    candidates = _candidates_by_id(db, hourlies)

    result = []
    for hourly in hourlies:
        row = {
            "hourly_id": hourly.id,
            "publish_time": _plain(hourly.publish_time),
            "theme": _plain(hourly.theme),
            "editorial_explanation": hourly.editorial_explanation,
            "candidate_id": hourly.candidate_id,
            "title": None, "creator_name": None, "creator_url": None,
            "url": None, "thumbnail_url": None, "source_type": None, "source_id": None,
            "preview_text": None, "tone": None,
        }
        row.update(_candidate_summary(candidates.get(hourly.candidate_id)))
        result.append(row)
    return result


def _candidates_by_id(db, hourlies):
    ids = [h.candidate_id for h in hourlies if h.candidate_id]
    if not ids:
        return {}
    return {c.id: c for c in db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id.in_(ids)).all()}


# ----------------------------------------------------------------- admin reads

def get_queue(db, limit=10):
    """Candidates awaiting review, best first, with the full score breakdown."""
    rows = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.status == models.Status.PENDING_REVIEW
    ).order_by(models.ContentCandidate.diamond_score.desc()).limit(max(1, min(limit, 50))).all()
    return [{
        "id": c.id, "title": c.title, "creator_name": c.creator_name, "url": _safe_url(c.url),
        "source_type": _plain(c.source_type), "theme": _plain(c.theme), "tone": c.tone,
        "preview_text": c.preview_text, "thumbnail_url": _safe_url(c.thumbnail_url),
        "view_count": c.view_count, "subscriber_count": c.subscriber_count,
        "upload_date": _plain(c.upload_date),
        "diamond_score": c.diamond_score, "quality_score": c.quality_score,
        "interestingness_score": c.interestingness_score, "rarity_score": c.rarity_score,
        "originality_score": c.originality_score, "outlier_score": c.outlier_score,
        "clickbait_penalty": c.clickbait_penalty,
        "trustworthiness_score": c.trustworthiness_score,
        "ai_explanation": c.ai_explanation,
    } for c in rows]


def get_outcomes(db, limit=200):
    """Featured picks with frozen score breakdowns, view deltas, and feedback tallies.

    This is the dataset for judging incrementality and tuning Diamond weights.
    """
    now = datetime.datetime.utcnow()
    hourlies = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time <= now
    ).order_by(models.HourlyOne.publish_time.desc()).limit(max(1, min(limit, 500))).all()
    candidates = _candidates_by_id(db, hourlies)

    tallies = {}
    for feedback in db.query(models.Feedback).all():
        counts = tallies.setdefault(feedback.hourly_one_id, {"never_seen": 0, "knew_already": 0})
        if feedback.seen_before == models.SeenBefore.NEVER_SEEN:
            counts["never_seen"] += 1
        else:
            counts["knew_already"] += 1

    events = _event_tallies(db)
    engaged_by_pick = _engaged_visitors(db)

    rows = []
    for hourly in hourlies:
        candidate = candidates.get(hourly.candidate_id)
        counts = tallies.get(hourly.id, {"never_seen": 0, "knew_already": 0})
        pick_events = events.get(hourly.id, {})
        views = pick_events.get("view", 0)
        engaged = engaged_by_pick.get(hourly.id, 0)
        shares = sum(n for kind, n in pick_events.items()
                     if kind == "copy_link" or kind.startswith("share_"))
        growth = None
        if hourly.views_at_feature and hourly.views_after_7d:
            growth = round(float(hourly.views_after_7d) / hourly.views_at_feature, 2)
        rows.append({
            "hourly_id": hourly.id,
            "publish_time": _plain(hourly.publish_time),
            "theme": _plain(hourly.theme),
            "views_at_feature": hourly.views_at_feature,
            "views_after_7d": hourly.views_after_7d,
            "outcome_checked_at": _plain(hourly.outcome_checked_at),
            "growth_ratio": growth,
            "candidate_id": hourly.candidate_id,
            "title": candidate.title if candidate else None,
            "creator_name": candidate.creator_name if candidate else None,
            "source_type": _plain(candidate.source_type) if candidate else None,
            "url": _safe_url(candidate.url) if candidate else None,
            "diamond_score": candidate.diamond_score if candidate else None,
            "quality_score": candidate.quality_score if candidate else None,
            "interestingness_score": candidate.interestingness_score if candidate else None,
            "rarity_score": candidate.rarity_score if candidate else None,
            "originality_score": candidate.originality_score if candidate else None,
            "outlier_score": candidate.outlier_score if candidate else None,
            "clickbait_penalty": candidate.clickbait_penalty if candidate else None,
            "trustworthiness_score": candidate.trustworthiness_score if candidate else None,
            "never_seen": counts["never_seen"],
            "knew_already": counts["knew_already"],
            "views": views,
            "engaged": engaged,
            "shares": shares,
            "ctr": round(float(engaged) / views, 2) if views else None,
        })
    return rows


def get_source_stats(db):
    """Per-source incrementality scoreboard.

    Aggregated in Python rather than SQL: case()'s list form was removed in
    SQLAlchemy 2.0, and the candidate table is small enough that it does not matter.
    """
    sources = {}
    columns = db.query(
        models.ContentCandidate.creator_name,
        models.ContentCandidate.source_type,
        models.ContentCandidate.status,
        models.ContentCandidate.diamond_score,
    ).all()
    for row in columns:
        key = (row.creator_name, _plain(row.source_type))
        stats = sources.get(key)
        if stats is None:
            stats = sources[key] = {
                "creator_name": row.creator_name,
                "source_type": key[1],
                "candidates": 0, "rejected": 0, "_scores": [],
                "picks_featured": 0, "never_seen": 0, "knew_already": 0,
                "_ratios": [], "blowups": 0, "views": 0, "engaged": 0,
            }
        stats["candidates"] += 1
        if row.status == models.Status.REJECTED:
            stats["rejected"] += 1
        if row.diamond_score is not None:
            stats["_scores"].append(row.diamond_score)

    for outcome in get_outcomes(db):
        stats = sources.get((outcome["creator_name"], outcome["source_type"]))
        if stats is None:
            continue
        stats["picks_featured"] += 1
        stats["never_seen"] += outcome["never_seen"]
        stats["knew_already"] += outcome["knew_already"]
        stats["views"] += outcome["views"]
        stats["engaged"] += outcome["engaged"]
        if outcome["growth_ratio"] is not None:
            stats["_ratios"].append(outcome["growth_ratio"])
            if outcome["growth_ratio"] >= 3.0:
                stats["blowups"] += 1

    result = []
    for stats in sources.values():
        scores = stats.pop("_scores")
        ratios = stats.pop("_ratios")
        stats["avg_diamond"] = round(sum(scores) / len(scores), 1) if scores else None
        stats["avg_growth_ratio"] = round(sum(ratios) / len(ratios), 2) if ratios else None
        stats["outcomes_checked"] = len(ratios)
        stats["ctr"] = round(float(stats["engaged"]) / stats["views"], 2) if stats["views"] else None
        total = stats["never_seen"] + stats["knew_already"]
        stats["never_seen_rate"] = round(float(stats["never_seen"]) / total, 2) if total else None
        result.append(stats)
    result.sort(key=lambda s: (s["picks_featured"], s["candidates"]), reverse=True)
    return result


# ----------------------------------------------------- engagement & retention

# What the page may report. "Engaged" means the reader actually consumed it.
EVENT_TYPES = ("view", "play", "read", "open_original", "copy_link",
               "share_x", "share_bluesky", "share_native")
ENGAGED_EVENTS = ("play", "read", "open_original")

COMMENT_RETENTION_DAYS = int(os.getenv("COMMENT_RETENTION_DAYS", "30"))


def record_event(db, hourly_one_id, event_type, visitor_key):
    """Anonymous engagement, counted once per visitor, pick and action per day.

    The visitor key is a daily-salted hash computed server-side (visitors.py);
    nothing identifying is stored, and one day's keys cannot be linked to the next.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError("event_type must be one of %s" % list(EVENT_TYPES))
    if not hourly_one_id:
        raise ValueError("hourly_one_id is required")
    if not visitor_key:
        raise ValueError("visitor key is required")
    if db.query(models.HourlyOne.id).filter(models.HourlyOne.id == hourly_one_id).first() is None:
        raise NotFound("No such pick")

    db.add(models.Event(hourly_one_id=hourly_one_id, event_type=event_type,
                        visitor_key=visitor_key))
    try:
        db.commit()
        return {"recorded": True}
    except IntegrityError:
        db.rollback()  # already counted for this visitor today
        return {"recorded": False}


def _event_tallies(db):
    """{pick id: {event type: visitors}} -- rows are already unique per visitor."""
    tallies = {}
    for pick_id, kind, total in db.query(
            models.Event.hourly_one_id, models.Event.event_type, func.count(models.Event.id)
    ).group_by(models.Event.hourly_one_id, models.Event.event_type).all():
        tallies.setdefault(pick_id, {})[kind] = total
    return tallies


def _engaged_visitors(db):
    """{pick id: distinct visitors who played, read, or opened the original}.

    Counted as people, not clicks: someone who plays and then opens the original
    is one engaged reader, so the rate can never exceed 100%.
    """
    return {pick_id: total for pick_id, total in db.query(
        models.Event.hourly_one_id, func.count(func.distinct(models.Event.visitor_key))
    ).filter(models.Event.event_type.in_(ENGAGED_EVENTS)).group_by(
        models.Event.hourly_one_id).all()}


def purge_expired(db):
    """Delete what the privacy policy says we do not keep.

    Chat older than COMMENT_RETENTION_DAYS, and visitor salts from earlier days
    (destroying the salt is what makes old visitor keys unlinkable).
    """
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(days=COMMENT_RETENTION_DAYS)
    comments = db.query(models.Comment).filter(models.Comment.created_at < cutoff).delete()
    salts = db.query(models.DailySalt).filter(
        models.DailySalt.day < now.strftime("%Y-%m-%d")).delete()
    db.commit()
    return {"comments": comments, "salts": salts}


# --------------------------------------------------------------- admin actions

def get_schedule(db, count=None):
    """The next `count` publishing slots, filled or empty (default: seven days).

    The curation runway: lets an editor see what is queued to go live before it
    does, rather than finding out afterwards.
    """
    per_day = max(1, slots.SLOTS_PER_DAY)
    count = per_day * 7 if count is None else max(1, min(int(count), per_day * 14))
    times = slots.upcoming_slots(count)
    end = slots.next_slot_start(times[-1])

    scheduled = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time >= times[0],
        models.HourlyOne.publish_time < end,
    ).all()
    # Keyed by the slot each pick falls in, so a pick from the hourly era that
    # sits off a slot boundary still shows up in the right row.
    by_slot = {slots.slot_start(h.publish_time): h for h in scheduled}
    candidates = _candidates_by_id(db, scheduled)

    runway = []
    for index, slot_time in enumerate(times):
        hourly = by_slot.get(slot_time)
        candidate = candidates.get(hourly.candidate_id) if hourly is not None else None
        runway.append({
            "publish_time": _plain(slot_time),
            "is_current_slot": index == 0,
            "hourly_id": hourly.id if hourly is not None else None,
            "theme": _plain(hourly.theme) if hourly is not None else None,
            "candidate_id": hourly.candidate_id if hourly is not None else None,
            "title": candidate.title if candidate is not None else None,
            "creator_name": candidate.creator_name if candidate is not None else None,
            "thumbnail_url": _safe_url(candidate.thumbnail_url) if candidate is not None else None,
            "source_type": _plain(candidate.source_type) if candidate is not None else None,
            "diamond_score": candidate.diamond_score if candidate is not None else None,
        })
    return runway


def unschedule(db, hourly_id):
    """Clear a slot and return its candidate to the review queue.

    Refuses to unpick an hour that has already gone live -- the archive is a
    record of what was actually published, not what we wish we had published.
    """
    hourly = db.query(models.HourlyOne).filter(models.HourlyOne.id == hourly_id).first()
    if hourly is None:
        raise NotFound("No such scheduled hour")

    current_slot = slots.slot_start()
    if hourly.publish_time < current_slot:
        raise ValueError("That slot has already been published")

    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == hourly.candidate_id).first()
    if candidate is not None:
        candidate.status = models.Status.PENDING_REVIEW
    db.delete(hourly)
    db.commit()
    return {"hourly_id": hourly_id, "freed": _plain(hourly.publish_time)}


def feature_candidate(db, candidate_id, publish_time=None):
    """Put a chosen candidate into a specific hour (default: the current one).

    `publish_time` accepts an ISO string or datetime and is floored to the hour,
    so upcoming slots can be curated ahead of time.
    """
    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == candidate_id).first()
    if candidate is None:
        raise NotFound("Candidate not found")

    current_slot = slots.slot_start()
    if publish_time is None:
        slot_begins = current_slot
    else:
        if isinstance(publish_time, str):
            try:
                parsed = datetime.datetime.strptime(
                    publish_time.replace("Z", "").split(".")[0], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                raise ValueError("publish_time must be ISO format, e.g. 2026-09-08T14:00:00")
        else:
            parsed = publish_time
        slot_begins = slots.slot_start(parsed)
        if slot_begins < current_slot:
            raise ValueError("Cannot schedule into a past slot")
    hourly = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time >= slot_begins,
        models.HourlyOne.publish_time < slots.next_slot_start(slot_begins),
    ).order_by(models.HourlyOne.publish_time.desc()).first()

    if hourly is not None:
        displaced = db.query(models.ContentCandidate).filter(
            models.ContentCandidate.id == hourly.candidate_id).first()
        if displaced is not None and displaced.id != candidate.id:
            displaced.status = models.Status.PENDING_REVIEW
        hourly.candidate_id = candidate.id
        hourly.theme = candidate.theme or DEFAULT_THEME
        hourly.editorial_explanation = candidate.ai_explanation
        hourly.views_at_feature = candidate.view_count
        hourly.views_after_7d = None
        hourly.outcome_checked_at = None
    else:
        hourly = models.HourlyOne(
            publish_time=slot_begins,
            theme=candidate.theme or DEFAULT_THEME,
            candidate_id=candidate.id,
            editorial_explanation=candidate.ai_explanation,
            views_at_feature=candidate.view_count,
        )
        db.add(hourly)

    candidate.status = models.Status.PUBLISHED
    db.commit()
    return {
        "hourly_id": hourly.id,
        "candidate_id": candidate.id,
        "publish_time": _plain(slot_begins),
    }


def reject_candidate(db, candidate_id):
    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == candidate_id).first()
    if candidate is None:
        raise NotFound("Candidate not found")
    candidate.status = models.Status.REJECTED
    candidate.admin_notes = "Rejected by admin"
    db.commit()
    return {"id": candidate.id, "status": "REJECTED"}
