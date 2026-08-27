"""One-shot promotion of the top candidate into the current hour's slot."""
from dotenv import load_dotenv
load_dotenv()

from app import database
from app.jobs import schedule_top_candidate

def schedule_top():
    print("Auto-scheduling the top candidate for the current hour...")
    db = database.SessionLocal()
    try:
        schedule_top_candidate(db)
    finally:
        db.close()

if __name__ == "__main__":
    schedule_top()
