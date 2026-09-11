"""
What the background pipeline last did, for /status.

In memory only, so it describes this process since it started -- enough to tell
"scoring ran and failed" from "scoring never ran", which the database alone
cannot. Its own module so both jobs.py and queries.py can use it without a
circular import.
"""
import datetime

LAST_RUN = {
    "started": None,
    "finished": None,
    "ingested": None,
    "scored": 0,
    "score_failures": 0,
    "error": None,
}


def start():
    LAST_RUN.update(started=datetime.datetime.utcnow().isoformat(), finished=None,
                    ingested=None, scored=0, score_failures=0, error=None)


def record(**values):
    LAST_RUN.update(values)


def finish():
    LAST_RUN["finished"] = datetime.datetime.utcnow().isoformat()


def snapshot():
    return dict(LAST_RUN)
