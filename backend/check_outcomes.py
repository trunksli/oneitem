"""Manual one-shot run of the incrementality outcome check (also runs hourly via run_hourly.py)."""
from dotenv import load_dotenv
load_dotenv()

from app import database
from app.outcomes import check_pick_outcomes

if __name__ == "__main__":
    db = database.SessionLocal()
    try:
        check_pick_outcomes(db)
    finally:
        db.close()
