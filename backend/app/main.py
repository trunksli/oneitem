"""
HTTP layer for ONE.

Deliberately thin: all database logic lives in queries.py (which imports no web
framework, so it can be tested without FastAPI installed). This module handles
routing, request validation, auth, and error mapping only.
"""
import os
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import models, queries
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ONE - Daily Diamond API")

# Lock the API to the deployed frontend in production; "*" is only the local default.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Credentials cannot be combined with a "*" origin, and this API authenticates
    # with a token header rather than cookies.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CommentCreate(BaseModel):
    content: str
    display_name: Optional[str] = None


class FeedbackCreate(BaseModel):
    hourly_one_id: str
    seen_before: str


class AdminAction(BaseModel):
    candidate_id: str


def require_admin(x_admin_token: Optional[str] = Header(None)):
    """Admin routes are disabled entirely unless ADMIN_TOKEN is configured."""
    token = os.getenv("ADMIN_TOKEN")
    if not token or x_admin_token != token:
        raise HTTPException(status_code=403, detail="Admin token required")


@app.on_event("startup")
def _start_scheduler():
    # on_event rather than lifespan so this works across FastAPI versions.
    if os.getenv("RUN_SCHEDULER") == "1":
        from .jobs import start_background_scheduler
        start_background_scheduler()
        print("In-process scheduler enabled (RUN_SCHEDULER=1).")


@app.get("/health")
def health():
    """Cheap liveness probe for the platform health check."""
    return {"status": "ok"}


@app.get("/status")
def status(db: Session = Depends(get_db)):
    """Operational snapshot for diagnosing a deployment. Contains no secrets."""
    return queries.get_status(db)


@app.get("/")
def read_root():
    return {"message": "Welcome to ONE API"}


@app.get("/hourly")
def get_hourly_one(db: Session = Depends(get_db)):
    try:
        return queries.get_hourly(db)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/pick/{hourly_id}")
def get_pick(hourly_id: str, db: Session = Depends(get_db)):
    """Permalink target: one specific featured hour."""
    try:
        return queries.get_pick(db, hourly_id)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/comments")
def get_comments(limit: int = 50, db: Session = Depends(get_db)):
    return queries.get_comments(db, limit)


@app.post("/comments", status_code=201)
def create_comment(comment: CommentCreate, db: Session = Depends(get_db)):
    try:
        return queries.create_comment(db, comment.content, comment.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/feedback", status_code=201)
def create_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    try:
        return queries.create_feedback(db, feedback.hourly_one_id, feedback.seen_before)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/archive")
def get_archive(limit: int = 100, db: Session = Depends(get_db)):
    return queries.get_archive(db, limit)


@app.get("/admin/queue", dependencies=[Depends(require_admin)])
def admin_queue(limit: int = 10, db: Session = Depends(get_db)):
    return queries.get_queue(db, limit)


@app.get("/admin/outcomes", dependencies=[Depends(require_admin)])
def admin_outcomes(db: Session = Depends(get_db)):
    return queries.get_outcomes(db)


@app.get("/admin/sources", dependencies=[Depends(require_admin)])
def admin_sources(db: Session = Depends(get_db)):
    return queries.get_source_stats(db)


@app.post("/admin/schedule", status_code=201, dependencies=[Depends(require_admin)])
def admin_schedule(action: AdminAction, db: Session = Depends(get_db)):
    try:
        return queries.feature_candidate(db, action.candidate_id)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/admin/reject", dependencies=[Depends(require_admin)])
def admin_reject(action: AdminAction, db: Session = Depends(get_db)):
    try:
        return queries.reject_candidate(db, action.candidate_id)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
