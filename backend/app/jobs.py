"""
Shared background work: refresh candidates, fill the current slot, check outcomes.

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

from . import database, models, slots
from .ai_scoring import score_candidate
from .ingestion import ingest_seed_channels
from .outcomes import check_pick_outcomes
from .queries import promote_next_pick
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
    """Promote the best pending candidate into the current hour's slot.

    Thin wrapper: the logic lives in queries.promote_next_pick so that the API can
    also schedule lazily on read, without pulling the ingestion stack into a request.
    """
    hourly = promote_next_pick(db)
    if hourly is None:
        print("Nothing to schedule: the slot is filled or no candidates are pending review.")
    else:
        print("Promoted candidate %s to HourlyOne for %s." % (hourly.candidate_id, hourly.publish_time))
    return hourly


def run_cycle():
    """One full pass: refresh if stale, fill the current slot, record outcomes.

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


def scheduler_loop():
    print("ONE scheduler running (pipeline every %dh)." % PIPELINE_EVERY_HOURS)
    while True:
        try:
            run_cycle()
        except Exception:
            print("Scheduler cycle failed:")
            traceback.print_exc()
        delay = slots.seconds_until_next_slot()
        print("Sleeping %ds until the next publishing slot..." % int(delay))
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
