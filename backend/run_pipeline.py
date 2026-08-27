"""One-shot ingestion + scoring run (YouTube seed channels and RSS feeds)."""
from dotenv import load_dotenv
load_dotenv()

from app import database, models
from app.jobs import refresh_candidates

def run_pipeline():
    print("Initializing database...")
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    try:
        refresh_candidates(db)
        print("Pipeline complete.")
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()
