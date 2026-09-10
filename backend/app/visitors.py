"""
Telling repeat actions apart without tracking people.

A visitor key is HMAC-SHA256(daily salt, IP address + User-Agent), truncated. It
is stable for one UTC day, so a second vote or a second view from the same person
that day is recognised -- and that is all it can do:

  - The IP address is used only to compute the hash and is never stored.
  - The salt is random, and each previous day's salt is deleted. Once it is gone,
    even we cannot recompute a key or link yesterday's keys to today's.
  - No cookie, no identifier in the browser, no account.

This is the approach privacy-focused analytics services use to count visitors
without consent banners. Whether that holds under a specific privacy law is a
question for counsel; the technical property is that nothing retained can
identify a person or follow them across days.
"""
import datetime
import hashlib
import hmac
import secrets
import threading

from sqlalchemy.exc import IntegrityError

from . import models

_lock = threading.Lock()
_cache = {}  # {day: salt}; one entry at a time


def _today():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def daily_salt(db, day=None):
    """Today's salt (created on first use), destroying any older ones."""
    day = day or _today()
    with _lock:
        cached = _cache.get(day)
    if cached:
        return cached

    row = db.query(models.DailySalt).filter(models.DailySalt.day == day).first()
    if row is None:
        db.add(models.DailySalt(day=day, salt=secrets.token_hex(32)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # another request created it first
        row = db.query(models.DailySalt).filter(models.DailySalt.day == day).first()

    # Deleting earlier salts is the step that makes old keys unlinkable.
    db.query(models.DailySalt).filter(models.DailySalt.day < day).delete()
    db.commit()

    with _lock:
        _cache.clear()
        _cache[day] = row.salt
    return row.salt


def client_ip(forwarded_for, remote_addr):
    """The caller's address.

    Behind Render's proxy the socket address is the proxy, so the forwarded
    header is needed. The RIGHTMOST entry is used because it is the one the
    trusted proxy appended; the leftmost entries are supplied by the client and
    could be forged to mint fresh keys and stuff votes.
    """
    if forwarded_for:
        hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return remote_addr or ""


def visitor_key(db, ip, user_agent, day=None):
    """A 32-character hex key, stable for one day and unlinkable across days."""
    salt = daily_salt(db, day)
    material = ("%s|%s" % (ip or "", (user_agent or "")[:256])).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), material, hashlib.sha256).hexdigest()[:32]
