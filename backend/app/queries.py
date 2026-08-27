"""
All database logic, deliberately free of any web-framework import.

Kept separate from main.py so it can be exercised directly (see test_queries.py)
without needing FastAPI installed, and so the HTTP layer stays thin.

Every function returns plain JSON-ready values (strings, numbers, dicts) rather
than ORM objects, so serialization behaves identically across library versions.
"""
import datetime

from . import models

MAX_COMMENT_LENGTH = 500
MAX_DISPLAY_NAME_LENGTH = 40


class NotFound(Exception):
    """Raised when a requested row does not exist; the HTTP layer maps it to 404."""


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
        "creator_url": candidate.creator_url,
        "url": candidate.url,
        "thumbnail_url": candidate.thumbnail_url,
        "source_type": _plain(candidate.source_type),
        "source_id": candidate.source_id,
    }


# ---------------------------------------------------------------- public reads

def get_hourly(db):
    """The current hour's pick, falling back to the latest so the site is never blank."""
    now = datetime.datetime.utcnow()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    hourly = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time >= hour_start,
        models.HourlyOne.publish_time <= now,
    ).order_by(models.HourlyOne.publish_time.desc()).first()

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


def create_feedback(db, hourly_one_id, seen_before):
    """Records a Never-Seen / Knew-Already vote against an hourly pick."""
    if not hourly_one_id:
        raise ValueError("hourly_one_id is required")
    try:
        seen = models.SeenBefore(seen_before)
    except ValueError:
        raise ValueError("seen_before must be one of %s" % [s.value for s in models.SeenBefore])

    feedback = models.Feedback(hourly_one_id=hourly_one_id, seen_before=seen)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "seen_before": _plain(feedback.seen_before)}


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
        "id": c.id, "title": c.title, "creator_name": c.creator_name, "url": c.url,
        "source_type": _plain(c.source_type), "theme": _plain(c.theme),
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

    rows = []
    for hourly in hourlies:
        candidate = candidates.get(hourly.candidate_id)
        counts = tallies.get(hourly.id, {"never_seen": 0, "knew_already": 0})
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
            "url": candidate.url if candidate else None,
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
                "_ratios": [], "blowups": 0,
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
        total = stats["never_seen"] + stats["knew_already"]
        stats["never_seen_rate"] = round(float(stats["never_seen"]) / total, 2) if total else None
        result.append(stats)
    result.sort(key=lambda s: (s["picks_featured"], s["candidates"]), reverse=True)
    return result


# --------------------------------------------------------------- admin actions

def feature_candidate(db, candidate_id):
    """Override the current hour with a chosen candidate (Phase A manual curation)."""
    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == candidate_id).first()
    if candidate is None:
        raise NotFound("Candidate not found")

    hour_start = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    hourly = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time == hour_start).first()

    if hourly is not None:
        displaced = db.query(models.ContentCandidate).filter(
            models.ContentCandidate.id == hourly.candidate_id).first()
        if displaced is not None and displaced.id != candidate.id:
            displaced.status = models.Status.PENDING_REVIEW
        hourly.candidate_id = candidate.id
        hourly.theme = candidate.theme or models.Theme.RANDOM
        hourly.editorial_explanation = candidate.ai_explanation
        hourly.views_at_feature = candidate.view_count
        hourly.views_after_7d = None
        hourly.outcome_checked_at = None
    else:
        hourly = models.HourlyOne(
            publish_time=hour_start,
            theme=candidate.theme or models.Theme.RANDOM,
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
        "publish_time": _plain(hour_start),
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
