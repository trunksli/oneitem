"""
In-memory sliding-window rate limits for the public write endpoints.

Deliberately simple: the API runs a single worker (see DEPLOY.md), so process
memory is the whole picture. Keys are hashed visitor keys, never raw addresses.
A restart resets the counters, which is acceptable for abuse limits of this size.
"""
import threading
import time
from collections import deque

# bucket -> (requests allowed, per this many seconds)
LIMITS = {
    "comments": (5, 60),
    "feedback": (30, 60),
    "events": (120, 60),
}

_lock = threading.Lock()
_hits = {}


def allow(bucket, key, now=None):
    """True if this request fits the bucket's limit; records it if so."""
    limit, window = LIMITS[bucket]
    now = time.monotonic() if now is None else now
    with _lock:
        recent = _hits.setdefault((bucket, key), deque())
        while recent and now - recent[0] >= window:
            recent.popleft()
        if len(recent) >= limit:
            return False
        recent.append(now)

        # Keep memory bounded: drop keys that have gone quiet.
        if len(_hits) > 10000:
            for stale in [k for k, v in _hits.items() if not v or now - v[-1] >= 3600]:
                _hits.pop(stale, None)
        return True


def reset():
    """Clear all counters (tests)."""
    with _lock:
        _hits.clear()
