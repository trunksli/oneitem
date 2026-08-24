import json
import sqlite3
import datetime
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse

MAX_BODY_BYTES = 16 * 1024
MAX_COMMENT_LENGTH = 500
VALID_SEEN_BEFORE = {"NEVER_SEEN", "SEEN_BEFORE", "KNEW_ALREADY"}

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class APIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def _send_json(self, payload, status_code=200):
        self._set_headers(status_code)
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def _read_json_body(self):
        """Returns (data, error). error is a (status, message) tuple if the body is bad."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            return None, (400, "Invalid Content-Length")
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            return None, (400, "Body missing or too large")
        try:
            data = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return None, (400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, (400, "Expected a JSON object")
        return data, None

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed_path = urlparse(self.path)

        conn = sqlite3.connect('sql_app_v2.db')
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        try:
            if parsed_path.path == '/hourly':
                # Prefer the item scheduled for the current hour; fall back to the
                # most recent one (flagged stale) so the site never goes blank.
                now = datetime.datetime.utcnow()
                hour_start = now.strftime("%Y-%m-%d %H:00:00")
                now_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")
                cursor.execute(
                    "SELECT * FROM hourly_ones WHERE publish_time >= ? AND publish_time <= ? "
                    "ORDER BY publish_time DESC LIMIT 1",
                    (hour_start, now_str))
                hourly = cursor.fetchone()
                is_stale = False
                if not hourly:
                    cursor.execute("SELECT * FROM hourly_ones ORDER BY publish_time DESC LIMIT 1")
                    hourly = cursor.fetchone()
                    is_stale = True
                if hourly:
                    cursor.execute("SELECT * FROM content_candidates WHERE id = ?", (hourly['candidate_id'],))
                    candidate = cursor.fetchone()
                    self._send_json({
                        "hourly": hourly,
                        "candidate": candidate,
                        "is_stale": is_stale
                    })
                else:
                    self._send_json({"detail": "No hourly one found"}, 404)

            elif parsed_path.path == '/comments':
                # "Daily Lobby": only today's comments (UTC midnight cutoff), and the
                # NEWEST 50 (oldest-first for display) so the chat never freezes at 50.
                today_start = datetime.datetime.utcnow().strftime("%Y-%m-%d 00:00:00")
                cursor.execute(
                    "SELECT * FROM comments WHERE created_at >= ? ORDER BY created_at DESC LIMIT 50",
                    (today_start,))
                comments = cursor.fetchall()
                comments.reverse()
                self._send_json(comments)
            else:
                self._send_json({"detail": "Not found"}, 404)
        finally:
            conn.close()

    def do_POST(self):
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/comments':
            data, error = self._read_json_body()
            if error:
                self._send_json({"detail": error[1]}, error[0])
                return

            content = (data.get('content') or "").strip()
            if not content:
                self._send_json({"detail": "Comment content is required"}, 400)
                return
            if len(content) > MAX_COMMENT_LENGTH:
                self._send_json({"detail": f"Comment too long (max {MAX_COMMENT_LENGTH} chars)"}, 400)
                return

            conn = sqlite3.connect('sql_app_v2.db')
            cursor = conn.cursor()
            try:
                c_id = str(uuid.uuid4())
                created_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
                cursor.execute("INSERT INTO comments (id, content, created_at) VALUES (?, ?, ?)",
                               (c_id, content, created_at))
                conn.commit()
                self._send_json({"id": c_id, "content": content}, 201)
            finally:
                conn.close()

        elif parsed_path.path == '/feedback':
            data, error = self._read_json_body()
            if error:
                self._send_json({"detail": error[1]}, error[0])
                return

            seen_before = data.get('seen_before')
            hourly_one_id = data.get('hourly_one_id')
            if seen_before not in VALID_SEEN_BEFORE:
                self._send_json({"detail": f"seen_before must be one of {sorted(VALID_SEEN_BEFORE)}"}, 400)
                return
            if not hourly_one_id or not isinstance(hourly_one_id, str):
                self._send_json({"detail": "hourly_one_id is required"}, 400)
                return

            conn = sqlite3.connect('sql_app_v2.db')
            cursor = conn.cursor()
            try:
                f_id = str(uuid.uuid4())
                created_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
                cursor.execute(
                    "INSERT INTO feedback (id, hourly_one_id, seen_before, created_at) VALUES (?, ?, ?, ?)",
                    (f_id, hourly_one_id, seen_before, created_at))
                conn.commit()
                self._send_json({"id": f_id, "seen_before": seen_before}, 201)
            finally:
                conn.close()
        else:
            self._send_json({"detail": "Not found"}, 404)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """One slow client should not block everyone (http.server.ThreadingHTTPServer needs 3.7+)."""
    daemon_threads = True

def run(server_class=ThreadingHTTPServer, handler_class=APIHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting simple API server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
