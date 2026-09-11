"""
Local development server for Python environments too old for FastAPI.

This machine runs Python 3.6.0, which predates typing.Deque (3.6.1) and so
cannot import pydantic -- meaning app/main.py will not start here. SQLAlchemy
works fine, so this stdlib HTTP server exposes the exact same endpoints by
delegating to app/queries.py, the same tested module main.py uses.

It is a routing shim only: no business logic lives here, so local and deployed
behaviour cannot drift.

    venv/Scripts/python.exe dev_server.py

Production uses app/main.py under uvicorn (see DEPLOY.md).
"""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv()

from app import auth, database, models, queries, ratelimit, share, visitors
from app.migrations import ensure_schema

MAX_BODY_BYTES = 16 * 1024


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_raw(self, body, content_type, status=200, cache=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return None, "Invalid Content-Length"
        if length <= 0 or length > MAX_BODY_BYTES:
            return None, "Body missing or too large"
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None, "Invalid JSON"
        if not isinstance(data, dict):
            return None, "Expected a JSON object"
        return data, None

    def _visitor(self, db):
        """Daily-salted visitor hash; the address is used to compute it and discarded."""
        ip = visitors.client_ip(self.headers.get("X-Forwarded-For"),
                                self.client_address[0] if self.client_address else "")
        return visitors.visitor_key(db, ip, self.headers.get("User-Agent"))

    def _is_admin(self):
        return auth.verify_token(self.headers.get("X-Admin-Token"))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)

        def as_int(name, default):
            try:
                return int(query.get(name, [str(default)])[0])
            except (TypeError, ValueError):
                return default

        db = database.SessionLocal()
        try:
            if path == "/health":
                self._send({"status": "ok"})
            elif path == "/status":
                self._send(queries.get_status(db))
            elif path == "/":
                self._send({"message": "Welcome to ONE API (dev server)"})
            elif path == "/hourly":
                self._send(queries.get_hourly(db))
            elif path == "/comments":
                # Chat is off unless CHAT_ENABLED=1; see app/main.py
                if os.getenv("CHAT_ENABLED") != "1":
                    self._send({"detail": "Chat is not available."}, 404)
                else:
                    self._send(queries.get_comments(db, as_int("limit", 50)))
            elif path.startswith("/p/"):
                self._send_raw(share.share_page(db, path[3:].strip("/")).encode("utf-8"),
                               "text/html; charset=utf-8", cache="public, max-age=300")
            elif path.startswith("/og/") and path.endswith(".png"):
                try:
                    png = share.render_card(db, path[4:-4])
                except share.CardUnavailable as e:
                    self._send({"detail": str(e)}, 503)
                else:
                    self._send_raw(png, "image/png", cache="public, max-age=86400")
            elif path.startswith("/pick/"):
                self._send(queries.get_pick(db, path[len("/pick/"):]))
            elif path == "/archive":
                self._send(queries.get_archive(db, as_int("limit", 100)))
            elif path.startswith("/admin/"):
                if not self._is_admin():
                    self._send({"detail": "Admin token required"}, 403)
                elif path == "/admin/queue":
                    self._send(queries.get_queue(db, as_int("limit", 10)))
                elif path == "/admin/outcomes":
                    self._send(queries.get_outcomes(db))
                elif path == "/admin/sources":
                    self._send(queries.get_source_stats(db))
                elif path == "/admin/schedule":
                    self._send(queries.get_schedule(db, as_int("count", None)))
                else:
                    self._send({"detail": "Not found"}, 404)
            else:
                self._send({"detail": "Not found"}, 404)
        except queries.NotFound as e:
            self._send({"detail": str(e)}, 404)
        except Exception as e:
            print("ERROR handling GET %s: %s" % (path, e))
            self._send({"detail": "Internal error"}, 500)
        finally:
            db.close()

    def do_POST(self):
        path = urlparse(self.path).path
        data, error = self._body()
        if error:
            self._send({"detail": error}, 400)
            return

        db = database.SessionLocal()
        try:
            if path == "/comments":
                if os.getenv("CHAT_ENABLED") != "1":
                    self._send({"detail": "Chat is not available."}, 404)
                elif not ratelimit.allow("comments", self._visitor(db)):
                    self._send({"detail": "Too many requests; please slow down."}, 429)
                else:
                    self._send(queries.create_comment(
                        db, data.get("content"), data.get("display_name")), 201)
            elif path == "/feedback":
                key = self._visitor(db)
                if not ratelimit.allow("feedback", key):
                    self._send({"detail": "Too many requests; please slow down."}, 429)
                else:
                    self._send(queries.create_feedback(
                        db, data.get("hourly_one_id"), data.get("seen_before"), key), 201)
            elif path == "/events":
                key = self._visitor(db)
                if not ratelimit.allow("events", key):
                    self._send({"detail": "Too many requests; please slow down."}, 429)
                else:
                    self._send(queries.record_event(
                        db, data.get("hourly_one_id"), data.get("event_type"), key), 202)
            elif path == "/admin/login":
                if not auth.is_configured():
                    self._send({"detail": "Admin access is not configured "
                                          "(set ADMIN_USERNAME and ADMIN_PASSWORD)"}, 503)
                elif auth.check_credentials(data.get("username"), data.get("password")):
                    token, expires_at = auth.issue_token()
                    self._send({"token": token, "expires_at": expires_at})
                else:
                    self._send({"detail": "Incorrect username or password"}, 401)
            elif path.startswith("/admin/"):
                if not self._is_admin():
                    self._send({"detail": "Sign in required"}, 403)
                elif path == "/admin/schedule":
                    self._send(queries.feature_candidate(
                        db, data.get("candidate_id"), data.get("publish_time")), 201)
                elif path == "/admin/unschedule":
                    self._send(queries.unschedule(db, data.get("hourly_id")))
                elif path == "/admin/reject":
                    self._send(queries.reject_candidate(db, data.get("candidate_id")))
                else:
                    self._send({"detail": "Not found"}, 404)
            else:
                self._send({"detail": "Not found"}, 404)
        except queries.NotFound as e:
            self._send({"detail": str(e)}, 404)
        except ValueError as e:
            self._send({"detail": str(e)}, 400)
        except Exception as e:
            db.rollback()
            print("ERROR handling POST %s: %s" % (path, e))
            self._send({"detail": "Internal error"}, 500)
        finally:
            db.close()


class ThreadingServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    models.Base.metadata.create_all(bind=database.engine)
    ensure_schema(database.engine)
    # Deliberately not PORT: this repo's .env carries a stale PORT=3000 from an
    # old Express setup, which also collides with the Next.js dev server.
    port = int(os.getenv("ONE_DEV_PORT", "8000"))
    print("ONE dev server on http://localhost:%d  (production uses app/main.py)" % port)
    ThreadingServer(("", port), Handler).serve_forever()
