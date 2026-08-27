import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app import database, models
from app.ingestion import ingest_seed_channels
from app.rss_ingestion import ingest_feeds
from app.ai_scoring import score_candidate

load_dotenv()

SEED_CHANNELS = [
    "UCMOqf8ab-42UUQIdVoKwjlQ", # Practical Engineering
    "UCy0tKL1T7wFoYcxCe0xjN6Q"  # Technology Connections
]

def run_pipeline():
    print("Initializing database...")
    models.Base.metadata.create_all(bind=database.engine)
    
    db = database.SessionLocal()
    
    try:
        print("1. Starting ingestion phase...")
        ingest_seed_channels(db, SEED_CHANNELS)

        print("1b. Ingesting RSS feeds...")
        ingest_feeds(db)


        print("2. Starting scoring phase...")
        # Score all pending candidates
        pending_candidates = db.query(models.ContentCandidate).filter(
            models.ContentCandidate.status == models.Status.PENDING_AI
        ).all()
        
        print(f"Found {len(pending_candidates)} pending candidates.")
        
        for candidate in pending_candidates:
            score_candidate(db, candidate)
            
        print("Pipeline complete.")
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()
