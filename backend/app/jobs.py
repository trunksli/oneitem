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

from . import database, models, runlog, slots, sources
from .ai_scoring import score_candidate
from .ingestion import ingest_seed_channels
from .outcomes import check_pick_outcomes
from .queries import promote_next_pick, purge_expired
from .rss_ingestion import ingest_feeds

PIPELINE_EVERY_HOURS = int(os.getenv("PIPELINE_EVERY_HOURS", "6"))

# Each scoring is one Gemini call. Anything over the cap waits for the next run.
MAX_SCORING_PER_RUN = int(os.getenv("MAX_SCORING_PER_RUN", "40"))

SEED_CHANNELS = list(sources.YOUTUBE_CHANNELS)

FEED_GROUPS = (
    ("article", sources.ARTICLE_FEEDS),
    ("vimeo", sources.VIMEO_FEEDS),
    ("podcast", sources.PODCAST_FEEDS),
)


def select_for_scoring(pending, limit):
    """Which pending candidates to score this run: newest first, taking turns by medium.

    Without turns, whichever medium has the most items (there are more article
    feeds than anything) would use the whole budget, and the others would never
    reach the pool of scored candidates at all.
    """
    def newest(c):
        return c.upload_date or c.discovered_date or datetime.datetime.min

    queues = {}
    for candidate in sorted(pending, key=newest, reverse=True):
        medium = getattr(candidate.source_type, "value", candidate.source_type)
        queues.setdefault(medium, []).append(candidate)

    ordered = [queues[medium] for medium in sorted(queues)]
    chosen = []
    while len(chosen) < limit and any(ordered):
        for queue in ordered:
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
    return chosen


def pipeline_is_due(db):
    """True if the candidate pool is stale.

    Checked against the DB rather than in-memory state so restarts and free-tier
    spin-ups don't re-run ingestion every wake and burn YouTube/Gemini quota.
    """
    latest = db.query(func.max(models.ContentCandidate.discovered_date)).scalar()
    if latest is None:
        return True
    return (datetime.datetime.utcnow() - latest).total_seconds() >= PIPELINE_EVERY_HOURS * 3600


def score_pending(db, limit=None):
    """Score a capped, mixed batch of whatever is waiting. Returns (scored, failed)."""
    pending = db.query(models.ContentCandidate).filter(
        models.ContentCandidate.status == models.Status.PENDING_AI
    ).all()
    batch = select_for_scoring(pending, limit or MAX_SCORING_PER_RUN)
    print("Scoring %d of %d pending candidates..." % (len(batch), len(pending)))
    scored = failed = 0
    for candidate in batch:
        try:
            if score_candidate(db, candidate):
                scored += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            traceback.print_exc()
            runlog.record(last_score_problem="%s: %s" % (type(e).__name__, str(e)[:250]))
            db.rollback()
        runlog.record(scored=scored, score_failures=failed)
    return scored, failed


def ready_count(db):
    return db.query(func.count(models.ContentCandidate.id)).filter(
        models.ContentCandidate.status == models.Status.PENDING_REVIEW).scalar() or 0


def ingest_all(db):
    """Fetch new candidates from every source."""
    if os.getenv("YOUTUBE_API_KEY"):
        ingest_seed_channels(db, SEED_CHANNELS)
    else:
        print("YOUTUBE_API_KEY not set - skipping YouTube ingestion.")
    for kind, feeds in FEED_GROUPS:
        # One broken medium must not stop the others
        try:
            ingest_feeds(db, feeds, kind=kind)
        except Exception:
            print("%s ingestion failed:" % kind)
            traceback.print_exc()
            db.rollback()


def refresh_candidates(db):
    """Ingest from all sources, then score a capped, mixed batch of what is pending."""
    ingest_all(db)
    score_pending(db)


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
    runlog.start()
    try:
        # Scoring is not tied to ingestion. It used to run only straight after an
        # ingest, and ingestion is skipped for 6 hours after it last added
        # anything -- so if the free host slept between the two, the new items
        # were never scored, the ready pool ran dry, and the site froze on its
        # last pick. Now anything waiting is scored every cycle, and when nothing
        # is ready it is scored FIRST, before a slow ingest can be interrupted.
        try:
            if ready_count(db) == 0:
                score_pending(db)
        except Exception:
            print("Scoring failed:")
            traceback.print_exc()
            db.rollback()

        try:
            if pipeline_is_due(db):
                ingest_all(db)
                runlog.record(ingested=datetime.datetime.utcnow().isoformat())
            else:
                print("Candidate pool is fresh; skipping ingestion.")
            score_pending(db)
        except Exception as e:
            print("Candidate refresh failed:")
            traceback.print_exc()
            runlog.record(error="%s: %s" % (type(e).__name__, str(e)[:200]))
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

        try:
            purged = purge_expired(db)
            print("Retention: removed %(comments)d old comments and %(salts)d old salts." % purged)
        except Exception:
            print("Retention cleanup failed:")
            traceback.print_exc()
            db.rollback()
    finally:
        runlog.finish()
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
