"""
Shared background work: refresh candidates, schedule the hour, check outcomes.

Used two ways:
  - run_hourly.py             -> a dedicated worker process (local, or a paid
                                 Render Background Worker)
  - start_background_scheduler() -> a daemon thread inside the API process, so a
                                 single free web service can also do the work
                                 (enable with RUN_SCHEDULER=1)
"""
import datetime
import os
import threading
import time
import traceback

from sqlalchemy import func

from . import database, models
from .ai_scoring import score_candidate
from .ingestion import ingest_seed_channels
from .outcomes import check_pick_outcomes
from .rss_ingestion import ingest_feeds

PIPELINE_EVERY_HOURS = int(os.getenv("PIPELINE_EVERY_HOURS", "6"))

SEED_CHANNELS = [
    "UCMOqf8ab-42UUQIdVoKwjlQ",  # Practical Engineering
    "UCy0tKL1T7wFoYcxCe0xjN6Q",  # Technology Connections
]


def pipeline_is_due(db):
    """True if the candidate pool is stale.

    Checked against the DB rather than in-memory state so restarts and free-tier
    spin-ups don't re-run ingestion every wake and burn YouTube/Gemini quota.
    """
    latest = db.query(func.max(models.ContentCandidate.discovered_date)).scalar()
    if latest is None:
        return True
    return (datetime.datetime.utcnow() - latest).total_seconds() >= PIPELINE_EVERY_HOURS * 3600


def refresh_candidates(db):
    """Ingest from all sources, then score everything still pending."""
    if os.getenv("YOUTUBE_API_KEY"):
        ingest_seed_channels(db, SEED_CHANNELS)
    else:
        print("YOUTUBE_API_KEY not set - skipping YouTube ingestion.")
    ingest_feeds(db)

    pending = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.status == models.Status.PENDING_AI
    ).all()
    print("Scoring %d pending candidates..." % len(pending))
    for candidate in pending:
        score_candidate(db, candidate)


def schedule_top_candidate(db):
    """Promote the best pending candidate into the current hour's slot."""
    now = datetime.datetime.utcnow()
    current_hour = now.replace(minute=0, second=0, microsecond=0)

    existing = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time == current_hour).first()
    if existing:
        print("Already have an HourlyOne for %s" % current_hour)
        return None

    # Theme rotation: prefer a top candidate whose theme differs from the
    # previous hour's, so the same theme doesn't run back-to-back all day.
    previous = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time < current_hour
    ).order_by(models.HourlyOne.publish_time.desc()).first()

    pending = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.status == models.Status.PENDING_REVIEW)

    top_candidate = None
    if previous is not None and previous.theme:
        top_candidate = pending.filter(
            models.ContentCandidate.theme != previous.theme
        ).order_by(models.ContentCandidate.diamond_score.desc()).first()

    # Fall back to the overall best if every remaining candidate shares the theme
    if top_candidate is None:
        top_candidate = pending.order_by(
            models.ContentCandidate.diamond_score.desc()).first()

    if top_candidate is None:
        print("No pending review candidates available to schedule.")
        return None

    hourly = models.HourlyOne(
        publish_time=current_hour,
        theme=top_candidate.theme or models.Theme.RANDOM,
        candidate_id=top_candidate.id,
        editorial_explanation=top_candidate.ai_explanation,
        views_at_feature=top_candidate.view_count,  # snapshot for the 7-day delta
    )
    top_candidate.status = models.Status.PUBLISHED
    db.add(hourly)
    db.commit()
    print("Promoted '%s' (Score: %s) to HourlyOne." % (top_candidate.title, top_candidate.diamond_score))
    return hourly


def run_cycle():
    """One full pass: refresh if stale, schedule the hour, record outcomes.

    Each step is isolated so one failure (e.g. an expired API key) doesn't stop
    the others -- the site keeps rotating content even if ingestion is broken.
    """
    db = database.SessionLocal()
    try:
        try:
            if pipeline_is_due(db):
                refresh_candidates(db)
            else:
                print("Candidate pool is fresh; skipping ingestion.")
        except Exception:
            print("Candidate refresh failed:")
            traceback.print_exc()
            db.rollback()

        try:
            schedule_top_candidate(db)
        except Exception:
            print("Scheduling failed:")
            traceback.print_exc()
            db.rollback()

        try:
            check_pick_outcomes(db)
        except Exception:
            print("Outcome check failed:")
            traceback.print_exc()
            db.rollback()
    finally:
        db.close()


def seconds_until_next_hour():
    now = datetime.datetime.utcnow()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    return max(60, (next_hour - now).total_seconds() + 5)


def scheduler_loop():
    print("ONE scheduler running (pipeline every %dh)." % PIPELINE_EVERY_HOURS)
    while True:
        try:
            run_cycle()
        except Exception:
            print("Scheduler cycle failed:")
            traceback.print_exc()
        delay = seconds_until_next_hour()
        print("Sleeping %ds until the next hour..." % int(delay))
        time.sleep(delay)


def start_background_scheduler():
    """Spawn the scheduler as a daemon thread inside the API process.

    Only for single-worker deployments -- with multiple workers each would run
    its own copy. The unique constraint on HourlyOne.publish_time makes double
    scheduling harmless, but ingestion would duplicate API calls.
    """
    thread = threading.Thread(target=scheduler_loop, name="one-scheduler", daemon=True)
    thread.start()
    return thread
