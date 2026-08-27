import json
import sqlite3
import datetime
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MAX_BODY_BYTES = 16 * 1024
MAX_COMMENT_LENGTH = 500
MAX_DISPLAY_NAME_LENGTH = 40
VALID_SEEN_BEFORE = {"NEVER_SEEN", "SEEN_BEFORE", "KNEW_ALREADY"}

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def fetch_outcomes(cursor):
    """Every featured pick with its frozen score breakdown, view delta, and feedback tallies.
    This is the dataset for judging incrementality and tuning Diamond Score weights."""
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    cursor.execute(
        "SELECT h.id AS hourly_id, h.publish_time, h.theme, h.views_at_feature, "
        "h.views_after_7d, h.outcome_checked_at, "
        "c.id AS candidate_id, c.title, c.creator_name, c.source_type, c.url, "
        "c.diamond_score, c.quality_score, c.interestingness_score, c.rarity_score, "
        "c.originality_score, c.outlier_score, c.clickbait_penalty, "
        "c.trustworthiness_score, c.expertise_score, c.subscriber_count "
        "FROM hourly_ones h LEFT JOIN content_candidates c ON c.id = h.candidate_id "
        "WHERE h.publish_time <= ? ORDER BY h.publish_time DESC LIMIT 200",
        (now_str,))
    outcomes = cursor.fetchall()

    cursor.execute("SELECT hourly_one_id, seen_before, COUNT(*) AS n FROM feedback "
                   "GROUP BY hourly_one_id, seen_before")
    feedback = {}
    for row in cursor.fetchall():
        feedback.setdefault(row['hourly_one_id'], {})[row['seen_before']] = row['n']

    for outcome in outcomes:
        tallies = feedback.get(outcome['hourly_id'], {})
        outcome['never_seen'] = tallies.get('NEVER_SEEN', 0)
        outcome['knew_already'] = tallies.get('KNEW_ALREADY', 0) + tallies.get('SEEN_BEFORE', 0)
        at_feature = outcome['views_at_feature']
        after = outcome['views_after_7d']
        outcome['growth_ratio'] = round(after / at_feature, 2) if at_feature and after else None
    return outcomes


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

    def _is_admin(self):
        """Admin endpoints require ADMIN_TOKEN to be configured AND presented."""
        token = os.getenv("ADMIN_TOKEN")
        return bool(token) and self.headers.get('X-Admin-Token') == token

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

            elif parsed_path.path == '/archive':
                # Past Diamonds: every previously featured item, newest first.
                now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
                cursor.execute(
                    "SELECT h.id AS hourly_id, h.publish_time, h.theme, h.editorial_explanation, "
                    "c.id AS candidate_id, c.title, c.creator_name, c.creator_url, c.url, "
                    "c.thumbnail_url, c.source_type, c.source_id "
                    "FROM hourly_ones h LEFT JOIN content_candidates c ON c.id = h.candidate_id "
                    "WHERE h.publish_time <= ? ORDER BY h.publish_time DESC LIMIT 100",
                    (now_str,))
                self._send_json(cursor.fetchall())

            elif parsed_path.path == '/admin/queue':
                if not self._is_admin():
                    self._send_json({"detail": "Admin token required"}, 403)
                    return
                query = parse_qs(parsed_path.query)
                try:
                    limit = min(50, max(1, int(query.get('limit', ['10'])[0])))
                except ValueError:
                    limit = 10
                cursor.execute(
                    "SELECT id, title, creator_name, url, source_type, theme, view_count, "
                    "subscriber_count, upload_date, diamond_score, quality_score, "
                    "interestingness_score, rarity_score, originality_score, outlier_score, "
                    "clickbait_penalty, trustworthiness_score, ai_explanation "
                    "FROM content_candidates WHERE status = 'PENDING_REVIEW' "
                    "ORDER BY diamond_score DESC LIMIT ?",
                    (limit,))
                self._send_json(cursor.fetchall())

            elif parsed_path.path == '/admin/outcomes':
                if not self._is_admin():
                    self._send_json({"detail": "Admin token required"}, 403)
                    return
                self._send_json(fetch_outcomes(cursor))

            elif parsed_path.path == '/admin/sources':
                # Per-source scoreboard: is this source finding unnoticed diamonds,
                # or content people would have seen anyway?
                if not self._is_admin():
                    self._send_json({"detail": "Admin token required"}, 403)
                    return

                cursor.execute(
                    "SELECT creator_name, source_type, COUNT(*) AS candidates, "
                    "AVG(diamond_score) AS avg_diamond, "
                    "SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) AS rejected "
                    "FROM content_candidates GROUP BY creator_name, source_type")
                sources = {}
                for row in cursor.fetchall():
                    key = (row['creator_name'], row['source_type'])
                    sources[key] = {
                        "creator_name": row['creator_name'],
                        "source_type": row['source_type'],
                        "candidates": row['candidates'],
                        "avg_diamond": round(row['avg_diamond'], 1) if row['avg_diamond'] is not None else None,
                        "rejected": row['rejected'],
                        "picks_featured": 0,
                        "never_seen": 0,
                        "knew_already": 0,
                        "growth_ratios": [],
                        "blowups": 0,
                    }

                for outcome in fetch_outcomes(cursor):
                    key = (outcome['creator_name'], outcome['source_type'])
                    if key not in sources:
                        continue
                    stats = sources[key]
                    stats['picks_featured'] += 1
                    stats['never_seen'] += outcome['never_seen']
                    stats['knew_already'] += outcome['knew_already']
                    ratio = outcome['growth_ratio']
                    if ratio is not None:
                        stats['growth_ratios'].append(ratio)
                        if ratio >= 3.0:
                            stats['blowups'] += 1

                result = []
                for stats in sources.values():
                    ratios = stats.pop('growth_ratios')
                    stats['avg_growth_ratio'] = round(sum(ratios) / len(ratios), 2) if ratios else None
                    stats['outcomes_checked'] = len(ratios)
                    total_feedback = stats['never_seen'] + stats['knew_already']
                    stats['never_seen_rate'] = round(stats['never_seen'] / total_feedback, 2) if total_feedback else None
                    result.append(stats)
                result.sort(key=lambda s: (s['picks_featured'], s['candidates']), reverse=True)
                self._send_json(result)
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

            display_name = (data.get('display_name') or "").strip()[:MAX_DISPLAY_NAME_LENGTH] or None

            conn = sqlite3.connect('sql_app_v2.db')
            cursor = conn.cursor()
            try:
                c_id = str(uuid.uuid4())
                created_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
                cursor.execute("INSERT INTO comments (id, content, display_name, created_at) VALUES (?, ?, ?, ?)",
                               (c_id, content, display_name, created_at))
                conn.commit()
                self._send_json({"id": c_id, "content": content, "display_name": display_name}, 201)
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

        elif parsed_path.path == '/admin/schedule':
            # Phase A override: feature this candidate for the CURRENT hour,
            # replacing whatever the auto-scheduler picked.
            if not self._is_admin():
                self._send_json({"detail": "Admin token required"}, 403)
                return
            data, error = self._read_json_body()
            if error:
                self._send_json({"detail": error[1]}, error[0])
                return
            candidate_id = data.get('candidate_id')
            if not candidate_id or not isinstance(candidate_id, str):
                self._send_json({"detail": "candidate_id is required"}, 400)
                return

            conn = sqlite3.connect('sql_app_v2.db')
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM content_candidates WHERE id = ?", (candidate_id,))
                candidate = cursor.fetchone()
                if not candidate:
                    self._send_json({"detail": "Candidate not found"}, 404)
                    return

                hour_start = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:00:00.000000")
                cursor.execute("SELECT * FROM hourly_ones WHERE publish_time = ?", (hour_start,))
                existing = cursor.fetchone()
                if existing:
                    # The displaced candidate goes back into the review pool
                    cursor.execute("UPDATE content_candidates SET status = 'PENDING_REVIEW' WHERE id = ?",
                                   (existing['candidate_id'],))
                    cursor.execute(
                        "UPDATE hourly_ones SET candidate_id = ?, theme = ?, editorial_explanation = ?, "
                        "views_at_feature = ?, views_after_7d = NULL, outcome_checked_at = NULL WHERE id = ?",
                        (candidate_id, candidate['theme'] or 'RANDOM',
                         candidate['ai_explanation'], candidate['view_count'], existing['id']))
                    hourly_id = existing['id']
                else:
                    hourly_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO hourly_ones (id, publish_time, theme, candidate_id, editorial_explanation, is_bandit_winner, views_at_feature) "
                        "VALUES (?, ?, ?, ?, ?, 0, ?)",
                        (hourly_id, hour_start, candidate['theme'] or 'RANDOM',
                         candidate_id, candidate['ai_explanation'], candidate['view_count']))
                cursor.execute("UPDATE content_candidates SET status = 'PUBLISHED' WHERE id = ?", (candidate_id,))
                conn.commit()
                self._send_json({"hourly_id": hourly_id, "candidate_id": candidate_id,
                                 "publish_time": hour_start}, 201)
            finally:
                conn.close()

        elif parsed_path.path == '/admin/reject':
            if not self._is_admin():
                self._send_json({"detail": "Admin token required"}, 403)
                return
            data, error = self._read_json_body()
            if error:
                self._send_json({"detail": error[1]}, error[0])
                return
            candidate_id = data.get('candidate_id')
            if not candidate_id or not isinstance(candidate_id, str):
                self._send_json({"detail": "candidate_id is required"}, 400)
                return

            conn = sqlite3.connect('sql_app_v2.db')
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE content_candidates SET status = 'REJECTED', admin_notes = 'Rejected by admin' WHERE id = ?",
                    (candidate_id,))
                conn.commit()
                if cursor.rowcount == 0:
                    self._send_json({"detail": "Candidate not found"}, 404)
                else:
                    self._send_json({"id": candidate_id, "status": "REJECTED"})
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
