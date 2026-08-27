"""
Incrementality outcome tracking.

~7 days after a pick was featured, re-poll its YouTube view count and store it
next to the view count it had when featured. The growth ratio is the core
incrementality signal:
  - stayed near its feature-time views  -> we surfaced something the wider
    internet was not going to deliver (incremental)
  - exploded regardless                 -> we were frontrunning virality
Paired with the candidate's score breakdown (frozen at scoring time), this is
the dataset for tuning the Diamond Score weights empirically.
"""
import datetime
import os

from sqlalchemy.orm import Session

from . import models
from .ingestion import get_videos_details

OUTCOME_CHECK_DAYS = int(os.getenv("OUTCOME_CHECK_DAYS", "7"))


def check_pick_outcomes(db: Session):
    """Finds featured picks past the check window and records their current views."""
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=OUTCOME_CHECK_DAYS)
    due = db.query(models.HourlyOne).filter(
        models.HourlyOne.publish_time <= cutoff,
        models.HourlyOne.outcome_checked_at.is_(None),
    ).all()
    if not due:
        return 0

    candidates = {c.id: c for c in db.query(models.ContentCandidate).filter(
        models.ContentCandidate.id.in_([h.candidate_id for h in due])).all()}

    # Batch-fetch current stats for the YouTube picks (API allows up to 50 ids)
    youtube_picks = [(h, candidates[h.candidate_id]) for h in due
                     if h.candidate_id in candidates
                     and candidates[h.candidate_id].source_type == models.SourceType.YOUTUBE
                     and candidates[h.candidate_id].source_id]
    current_views = {}
    video_ids = [c.source_id for _, c in youtube_picks]
    for i in range(0, len(video_ids), 50):
        try:
            for item in get_videos_details(video_ids[i:i + 50]):
                current_views[item['id']] = int(item.get('statistics', {}).get('viewCount', 0))
        except Exception as e:
            print(f"Outcome check: YouTube stats fetch failed: {e}")

    now = datetime.datetime.utcnow()
    checked = 0
    for hourly in due:
        candidate = candidates.get(hourly.candidate_id)
        # Backfill for picks scheduled before views_at_feature existed
        if hourly.views_at_feature is None and candidate is not None:
            hourly.views_at_feature = candidate.view_count

        if candidate is not None and candidate.source_type == models.SourceType.YOUTUBE:
            if candidate.source_id not in current_views:
                # Fetch failed or video deleted - leave unchecked so a later run retries
                continue
            hourly.views_after_7d = current_views[candidate.source_id]
        # Non-YouTube picks have no view data; mark checked so they don't queue forever

        hourly.outcome_checked_at = now
        checked += 1

    db.commit()
    print(f"Outcome check: recorded outcomes for {checked} of {len(due)} due picks.")
    return checked
