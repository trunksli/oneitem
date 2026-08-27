"""
Standalone scheduler process: keeps ONE actually hourly.

Every hour it refreshes stale candidates (ingest + score), promotes the next
HourlyOne, and records 7-day view outcomes.

    venv/Scripts/python.exe run_hourly.py

On Render this is optional: setting RUN_SCHEDULER=1 on the web service runs the
same loop in a background thread, so no separate worker is needed.
"""
from dotenv import load_dotenv
load_dotenv()

from app import database, models
from app.jobs import scheduler_loop

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=database.engine)
    scheduler_loop()
