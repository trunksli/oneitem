"""
Long-running scheduler loop: keeps ONE actually hourly.

- Every hour (top of the hour): promotes the best candidate to HourlyOne.
- Every PIPELINE_EVERY_HOURS hours: re-runs ingestion + AI scoring to refresh
  the candidate pool.

Run with:  venv\\Scripts\\python.exe run_hourly.py
(or register it with Windows Task Scheduler / cron to survive reboots)
"""
import datetime
import os
import time
import traceback

from dotenv import load_dotenv
load_dotenv()

from run_pipeline import run_pipeline
from auto_schedule import schedule_top_candidate

PIPELINE_EVERY_HOURS = int(os.getenv("PIPELINE_EVERY_HOURS", "6"))

def main():
    last_pipeline_run = None
    print(f"ONE hourly runner started (pipeline every {PIPELINE_EVERY_HOURS}h).")
    while True:
        now = datetime.datetime.utcnow()
        try:
            if (last_pipeline_run is None or
                    (now - last_pipeline_run).total_seconds() >= PIPELINE_EVERY_HOURS * 3600):
                run_pipeline()
                last_pipeline_run = now
        except Exception:
            print("Pipeline run failed:")
            traceback.print_exc()

        try:
            schedule_top_candidate()
        except Exception:
            print("Scheduling failed:")
            traceback.print_exc()

        # Sleep until just past the top of the next hour
        now = datetime.datetime.utcnow()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
        sleep_seconds = max(60, (next_hour - now).total_seconds() + 5)
        print(f"Sleeping {int(sleep_seconds)}s until {next_hour} UTC...")
        time.sleep(sleep_seconds)

if __name__ == "__main__":
    main()
