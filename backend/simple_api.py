import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

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

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        conn = sqlite3.connect('sql_app_v2.db')
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        try:
            if parsed_path.path == '/hourly':
                cursor.execute("SELECT * FROM hourly_ones ORDER BY publish_time DESC LIMIT 1")
                hourly = cursor.fetchone()
                if hourly:
                    cursor.execute("SELECT * FROM content_candidates WHERE id = ?", (hourly['candidate_id'],))
                    candidate = cursor.fetchone()
                    self._set_headers()
                    self.wfile.write(json.dumps({
                        "hourly": hourly,
                        "candidate": candidate
                    }).encode('utf-8'))
                else:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"detail": "No hourly one found"}).encode('utf-8'))
                    
            elif parsed_path.path == '/comments':
                cursor.execute("SELECT * FROM comments ORDER BY created_at ASC LIMIT 50")
                comments = cursor.fetchall()
                self._set_headers()
                self.wfile.write(json.dumps(comments).encode('utf-8'))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"detail": "Not found"}).encode('utf-8'))
        finally:
            conn.close()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/comments':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            conn = sqlite3.connect('sql_app_v2.db')
            cursor = conn.cursor()
            try:
                import uuid, datetime
                c_id = str(uuid.uuid4())
                created_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
                cursor.execute("INSERT INTO comments (id, content, created_at) VALUES (?, ?, ?)", 
                               (c_id, data['content'], created_at))
                conn.commit()
                self._set_headers(201)
                self.wfile.write(json.dumps({"id": c_id, "content": data['content']}).encode('utf-8'))
            finally:
                conn.close()
        else:
            self._set_headers(404)

def run(server_class=HTTPServer, handler_class=APIHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting simple API server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
