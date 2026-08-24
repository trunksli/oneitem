import datetime

from fastapi import FastAPI, Depends, HTTPException
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

class FeedbackCreate(BaseModel):
    hourly_one_id: str
    seen_before: models.SeenBefore

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
    db_comment = models.Comment(content=content)
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

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
