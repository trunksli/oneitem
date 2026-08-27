import datetime
import os
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ONE - Daily Diamond API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_COMMENT_LENGTH = 500

class CommentCreate(BaseModel):
    content: str
    display_name: Optional[str] = None

class FeedbackCreate(BaseModel):
    hourly_one_id: str
    seen_before: models.SeenBefore

class AdminAction(BaseModel):
    candidate_id: str

def require_admin(x_admin_token: Optional[str] = Header(None)):
    token = os.getenv("ADMIN_TOKEN")
    if not token or x_admin_token != token:
        raise HTTPException(status_code=403, detail="Admin token required")

@app.get("/")
def read_root():
    return {"message": "Welcome to ONE API"}

@app.get("/candidates")
def get_candidates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    candidates = db.query(models.ContentCandidate).order_by(models.ContentCandidate.diamond_score.desc()).offset(skip).limit(limit).all()
    return candidates

@app.get("/hourly")
def get_hourly_one(db: Session = Depends(get_db)):
    # Prefer the item scheduled for the current hour; fall back to the most
    # recent one (flagged stale) so the site never goes blank.
    now = datetime.datetime.utcnow()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    hourly = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time >= hour_start,
        models.HourlyOne.publish_time <= now,
    ).order_by(models.HourlyOne.publish_time.desc()).first()

    is_stale = False
    if not hourly:
        hourly = db.query(models.HourlyOne).order_by(models.HourlyOne.publish_time.desc()).first()
        is_stale = True
    if not hourly:
        raise HTTPException(status_code=404, detail="No hourly one found")

    candidate = db.query(models.ContentCandidate).filter(models.ContentCandidate.id == hourly.candidate_id).first()
    return {
        "hourly": hourly,
        "candidate": candidate,
        "is_stale": is_stale
    }

@app.get("/comments")
def get_comments(db: Session = Depends(get_db), limit: int = 50):
    # "Daily Lobby": only today's comments (UTC midnight cutoff), and the
    # NEWEST batch (oldest-first for display) so the chat never freezes at 50.
    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    comments = db.query(models.Comment).filter(
        models.Comment.created_at >= today_start
    ).order_by(models.Comment.created_at.desc()).limit(limit).all()
    return list(reversed(comments))

@app.post("/comments", status_code=201)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    content = comment.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Comment content is required")
    if len(content) > MAX_COMMENT_LENGTH:
        raise HTTPException(status_code=400, detail=f"Comment too long (max {MAX_COMMENT_LENGTH} chars)")
    display_name = (comment.display_name or "").strip()[:40] or None
    db_comment = models.Comment(content=content, display_name=display_name)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

@app.get("/archive")
def get_archive(limit: int = 100, db: Session = Depends(get_db)):
    now = datetime.datetime.utcnow()
    hourlies = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time <= now
    ).order_by(models.HourlyOne.publish_time.desc()).limit(min(limit, 200)).all()
    candidate_ids = [h.candidate_id for h in hourlies]
    candidates = {c.id: c for c in db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id.in_(candidate_ids)).all()}
    result = []
    for h in hourlies:
        c = candidates.get(h.candidate_id)
        result.append({
            "hourly_id": h.id, "publish_time": h.publish_time, "theme": h.theme,
            "editorial_explanation": h.editorial_explanation,
            "candidate_id": h.candidate_id,
            "title": c.title if c else None,
            "creator_name": c.creator_name if c else None,
            "creator_url": c.creator_url if c else None,
            "url": c.url if c else None,
            "thumbnail_url": c.thumbnail_url if c else None,
            "source_type": c.source_type if c else None,
            "source_id": c.source_id if c else None,
        })
    return result

@app.get("/admin/queue", dependencies=[Depends(require_admin)])
def admin_queue(limit: int = 10, db: Session = Depends(get_db)):
    return db.query(models.ContentCandidate).filter(
        models.ContentCandidate.status == models.Status.PENDING_REVIEW
    ).order_by(models.ContentCandidate.diamond_score.desc()).limit(min(limit, 50)).all()

@app.post("/admin/schedule", status_code=201, dependencies=[Depends(require_admin)])
def admin_schedule(action: AdminAction, db: Session = Depends(get_db)):
    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == action.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    hour_start = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    hourly = db.query(models.HourlyOne).filter(models.HourlyOne.publish_time == hour_start).first()
    if hourly:
        displaced = db.query(models.ContentCandidate).filter(
            models.ContentCandidate.id == hourly.candidate_id).first()
        if displaced:
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
    return {"hourly_id": hourly.id, "candidate_id": candidate.id, "publish_time": hour_start}

def _outcome_rows(db: Session):
    """Featured picks with frozen scores, view deltas, and feedback tallies."""
    now = datetime.datetime.utcnow()
    hourlies = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time <= now
    ).order_by(models.HourlyOne.publish_time.desc()).limit(200).all()
    candidates = {c.id: c for c in db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id.in_([h.candidate_id for h in hourlies])).all()}

    feedback = {}
    for f in db.query(models.Feedback).all():
        tallies = feedback.setdefault(f.hourly_one_id, {"never_seen": 0, "knew_already": 0})
        if f.seen_before == models.SeenBefore.NEVER_SEEN:
            tallies["never_seen"] += 1
        else:
            tallies["knew_already"] += 1

    rows = []
    for h in hourlies:
        c = candidates.get(h.candidate_id)
        tallies = feedback.get(h.id, {"never_seen": 0, "knew_already": 0})
        growth = None
        if h.views_at_feature and h.views_after_7d:
            growth = round(h.views_after_7d / h.views_at_feature, 2)
        rows.append({
            "hourly_id": h.id, "publish_time": h.publish_time, "theme": h.theme,
            "views_at_feature": h.views_at_feature, "views_after_7d": h.views_after_7d,
            "outcome_checked_at": h.outcome_checked_at, "growth_ratio": growth,
            "candidate_id": h.candidate_id,
            "title": c.title if c else None,
            "creator_name": c.creator_name if c else None,
            "source_type": c.source_type if c else None,
            "url": c.url if c else None,
            "diamond_score": c.diamond_score if c else None,
            "quality_score": c.quality_score if c else None,
            "interestingness_score": c.interestingness_score if c else None,
            "rarity_score": c.rarity_score if c else None,
            "originality_score": c.originality_score if c else None,
            "outlier_score": c.outlier_score if c else None,
            "clickbait_penalty": c.clickbait_penalty if c else None,
            "trustworthiness_score": c.trustworthiness_score if c else None,
            "never_seen": tallies["never_seen"],
            "knew_already": tallies["knew_already"],
        })
    return rows

@app.get("/admin/outcomes", dependencies=[Depends(require_admin)])
def admin_outcomes(db: Session = Depends(get_db)):
    return _outcome_rows(db)

@app.get("/admin/sources", dependencies=[Depends(require_admin)])
def admin_sources(db: Session = Depends(get_db)):
    from sqlalchemy import func, case
    sources = {}
    stats_query = db.query(
        models.ContentCandidate.creator_name,
        models.ContentCandidate.source_type,
        func.count().label("candidates"),
        func.avg(models.ContentCandidate.diamond_score).label("avg_diamond"),
        func.sum(case([(models.ContentCandidate.status == models.Status.REJECTED, 1)], else_=0)).label("rejected"),
    ).group_by(models.ContentCandidate.creator_name, models.ContentCandidate.source_type)
    for row in stats_query.all():
        sources[(row.creator_name, row.source_type)] = {
            "creator_name": row.creator_name, "source_type": row.source_type,
            "candidates": row.candidates,
            "avg_diamond": round(row.avg_diamond, 1) if row.avg_diamond is not None else None,
            "rejected": row.rejected or 0,
            "picks_featured": 0, "never_seen": 0, "knew_already": 0,
            "growth_ratios": [], "blowups": 0,
        }
    for outcome in _outcome_rows(db):
        stats = sources.get((outcome["creator_name"], outcome["source_type"]))
        if not stats:
            continue
        stats["picks_featured"] += 1
        stats["never_seen"] += outcome["never_seen"]
        stats["knew_already"] += outcome["knew_already"]
        if outcome["growth_ratio"] is not None:
            stats["growth_ratios"].append(outcome["growth_ratio"])
            if outcome["growth_ratio"] >= 3.0:
                stats["blowups"] += 1
    result = []
    for stats in sources.values():
        ratios = stats.pop("growth_ratios")
        stats["avg_growth_ratio"] = round(sum(ratios) / len(ratios), 2) if ratios else None
        stats["outcomes_checked"] = len(ratios)
        total = stats["never_seen"] + stats["knew_already"]
        stats["never_seen_rate"] = round(stats["never_seen"] / total, 2) if total else None
        result.append(stats)
    result.sort(key=lambda s: (s["picks_featured"], s["candidates"]), reverse=True)
    return result

@app.post("/admin/reject", dependencies=[Depends(require_admin)])
def admin_reject(action: AdminAction, db: Session = Depends(get_db)):
    candidate = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id == action.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    candidate.status = models.Status.REJECTED
    candidate.admin_notes = "Rejected by admin"
    db.commit()
    return {"id": candidate.id, "status": "REJECTED"}

@app.post("/feedback", status_code=201)
def create_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    db_feedback = models.Feedback(
        hourly_one_id=feedback.hourly_one_id,
        seen_before=feedback.seen_before,
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback
