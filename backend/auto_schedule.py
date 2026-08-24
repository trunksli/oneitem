import datetime
from sqlalchemy.orm import Session
from app import database, models

def schedule_top_candidate():
    print("Auto-scheduling the top candidate for the current hour...")
    db = database.SessionLocal()
    
    try:
        # Get current hour block
        now = datetime.datetime.utcnow()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
    
        # Check if we already have one for this hour
        existing = db.query(models.HourlyOne).filter(models.HourlyOne.publish_time == current_hour).first()
        if existing:
            print(f"Already have an HourlyOne for {current_hour}")
            return
            
        # Theme rotation: prefer a top candidate whose theme differs from the
        # previous hour's, so the same theme doesn't run back-to-back all day.
        previous = db.query(models.HourlyOne).filter(
            models.HourlyOne.publish_time < current_hour
        ).order_by(models.HourlyOne.publish_time.desc()).first()

        pending = db.query(models.ContentCandidate).filter(
            models.ContentCandidate.status == models.Status.PENDING_REVIEW
        )

        top_candidate = None
        if previous and previous.theme:
            top_candidate = pending.filter(
                models.ContentCandidate.theme != previous.theme
            ).order_by(models.ContentCandidate.diamond_score.desc()).first()

        # Fall back to the overall best if every remaining candidate shares the theme
        if not top_candidate:
            top_candidate = pending.order_by(models.ContentCandidate.diamond_score.desc()).first()

        if not top_candidate:
            print("No pending review candidates available to schedule.")
            return
            
        # Promote it
        hourly = models.HourlyOne(
            publish_time=current_hour,
            theme=top_candidate.theme or models.Theme.RANDOM,
            candidate_id=top_candidate.id,
            editorial_explanation=top_candidate.ai_explanation
        )
        
        top_candidate.status = models.Status.PUBLISHED
        
        db.add(hourly)
        db.commit()
        print(f"Success! Promoted '{top_candidate.title}' (Score: {top_candidate.diamond_score}) to HourlyOne.")
    finally:
        db.close()

if __name__ == "__main__":
    schedule_top_candidate()
