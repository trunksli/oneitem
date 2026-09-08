"""
Admin authentication.

Username + password are checked against environment variables, and a successful
login returns a short-lived signed token rather than the long-lived shared
secret. Nothing is stored in the database: there is exactly one admin.

The token is stateless (an expiry plus an HMAC over it), so it needs no session
store and cannot be forged without ADMIN_TOKEN. Because it expires, a token
copied off a machine stops working on its own -- unlike the previous scheme,
where the permanent secret sat in localStorage forever.
"""
import base64
import hashlib
import hmac
import os
import time

SESSION_HOURS = int(os.getenv("ADMIN_SESSION_HOURS", "12"))


def _secret():
    """Signing key. ADMIN_TOKEN doubles as the secret so deployments need one fewer var."""
    return (os.getenv("ADMIN_TOKEN") or "").encode("utf-8")


def is_configured():
    """Admin access is disabled entirely unless credentials exist."""
    return bool(os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD") and _secret())


def _sign(payload):
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def check_credentials(username, password):
    """Constant-time comparison, so response timing does not leak the values."""
    if not is_configured():
        return False
    expected_user = os.getenv("ADMIN_USERNAME", "")
    expected_pass = os.getenv("ADMIN_PASSWORD", "")
    user_ok = hmac.compare_digest(str(username or ""), expected_user)
    pass_ok = hmac.compare_digest(str(password or ""), expected_pass)
    return user_ok and pass_ok


def issue_token():
    """A token of the form <base64 expiry>.<signature>."""
    expires_at = int(time.time()) + SESSION_HOURS * 3600
    payload = base64.urlsafe_b64encode(str(expires_at).encode("utf-8")).decode("ascii").rstrip("=")
    return "%s.%s" % (payload, _sign(payload)), expires_at


def verify_token(token):
    """True for a valid, unexpired session token.

    The raw ADMIN_TOKEN is still accepted so scripts and curl keep working; the
    browser only ever holds a session token.
    """
    if not token or not _secret():
        return False

    if hmac.compare_digest(str(token), os.getenv("ADMIN_TOKEN", "")):
        return True

    try:
        payload, signature = str(token).rsplit(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(payload)):
        return False

    try:
        padded = payload + "=" * (-len(payload) % 4)
        expires_at = int(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except Exception:
        return False
    return time.time() < expires_at
