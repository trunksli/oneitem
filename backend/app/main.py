"""
HTTP layer for ONE.

Deliberately thin: all database logic lives in queries.py (which imports no web
framework, so it can be tested without FastAPI installed). This module handles
routing, request validation, auth, and error mapping only.
"""
import os
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import auth, models, queries, ratelimit, share, visitors
from .database import engine, get_db
from .migrations import ensure_schema

models.Base.metadata.create_all(bind=engine)
# create_all never alters existing tables, and there is live data to bring forward.
ensure_schema(engine)

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


class EventCreate(BaseModel):
    hourly_one_id: str
    event_type: str


def _visitor(request: Request, db: Session) -> str:
    """Daily-salted visitor hash; the address is used to compute it and discarded."""
    ip = visitors.client_ip(request.headers.get("x-forwarded-for"),
                            request.client.host if request.client else "")
    return visitors.visitor_key(db, ip, request.headers.get("user-agent"))


def _limit(bucket: str, key: str):
    if not ratelimit.allow(bucket, key):
        raise HTTPException(status_code=429, detail="Too many requests; please slow down.")


class AdminAction(BaseModel):
    candidate_id: str
    publish_time: Optional[str] = None


class AdminLogin(BaseModel):
    username: str
    password: str


class UnscheduleAction(BaseModel):
    hourly_id: str


def require_admin(x_admin_token: Optional[str] = Header(None)):
    """Accepts a signed session token from the login form, or the raw ADMIN_TOKEN
    for scripts. Admin routes are disabled entirely when nothing is configured."""
    if not auth.verify_token(x_admin_token):
        raise HTTPException(status_code=403, detail="Sign in required")


@app.post("/admin/login")
def admin_login(credentials: AdminLogin):
    """Exchange username and password for a short-lived session token."""
    if not auth.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Admin access is not configured (set ADMIN_USERNAME and ADMIN_PASSWORD)")
    if not auth.check_credentials(credentials.username, credentials.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token, expires_at = auth.issue_token()
    return {"token": token, "expires_at": expires_at}


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


@app.get("/p/{hourly_id}", response_class=HTMLResponse)
def share_page(hourly_id: str, db: Session = Depends(get_db)):
    """Share link: this pick's Open Graph tags for link previews, then on to the pick."""
    try:
        return HTMLResponse(share.share_page(db, hourly_id),
                            headers={"Cache-Control": "public, max-age=300"})
    except queries.NotFound:
        raise HTTPException(status_code=404, detail="No such pick")


@app.get("/og/{hourly_id}.png")
def og_card(hourly_id: str, db: Session = Depends(get_db)):
    """1200x630 link-preview card for one pick."""
    try:
        png = share.render_card(db, hourly_id)
    except queries.NotFound:
        raise HTTPException(status_code=404, detail="No such pick")
    except share.CardUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/comments")
def get_comments(limit: int = 50, db: Session = Depends(get_db)):
    return queries.get_comments(db, limit)


@app.post("/comments", status_code=201)
def create_comment(comment: CommentCreate, request: Request, db: Session = Depends(get_db)):
    _limit("comments", _visitor(request, db))
    try:
        return queries.create_comment(db, comment.content, comment.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/feedback", status_code=201)
def create_feedback(feedback: FeedbackCreate, request: Request, db: Session = Depends(get_db)):
    key = _visitor(request, db)
    _limit("feedback", key)
    try:
        return queries.create_feedback(db, feedback.hourly_one_id, feedback.seen_before, key)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/events", status_code=202)
def create_event(event: EventCreate, request: Request, db: Session = Depends(get_db)):
    """Anonymous engagement (view / play / read / share), deduplicated per visitor per day."""
    key = _visitor(request, db)
    _limit("events", key)
    try:
        return queries.record_event(db, event.hourly_one_id, event.event_type, key)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
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


@app.get("/admin/schedule", dependencies=[Depends(require_admin)])
def admin_get_schedule(count: Optional[int] = None, db: Session = Depends(get_db)):
    """The upcoming curation runway: publishing slots, seven days by default."""
    return queries.get_schedule(db, count)


@app.post("/admin/schedule", status_code=201, dependencies=[Depends(require_admin)])
def admin_schedule(action: AdminAction, db: Session = Depends(get_db)):
    try:
        return queries.feature_candidate(db, action.candidate_id, action.publish_time)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/unschedule", dependencies=[Depends(require_admin)])
def admin_unschedule(action: UnscheduleAction, db: Session = Depends(get_db)):
    try:
        return queries.unschedule(db, action.hourly_id)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/reject", dependencies=[Depends(require_admin)])
def admin_reject(action: AdminAction, db: Session = Depends(get_db)):
    try:
        return queries.reject_candidate(db, action.candidate_id)
    except queries.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
