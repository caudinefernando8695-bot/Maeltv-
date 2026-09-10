#!/usr/bin/env python3
"""MaelTV backend: guest authentication, catalogue, search and favourites.
Runs with Python's standard library; no external packages are required.
"""
import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("MAELTV_DB", os.path.join(ROOT, "data", "maeltv.db"))
PORT = int(os.environ.get("PORT", "8080"))
TOKEN_TTL = 60 * 60 * 24 * 30

SEED_CATALOG = [
    {"title": "Aventura & mistério", "type": "movie", "category": "Ação", "year": 1957, "description": "Cinema clássico de aventura e ficção científica.", "video_url": "https://archive.org/download/the-brain-from-planet-arous-1957-sci-fi-feature/arous_drivein_v2_704x430_rf20.ia.mp4", "source_url": "https://archive.org/details/the-brain-from-planet-arous-1957-sci-fi-feature", "free": True},
    {"title": "Histórias que marcam", "type": "movie", "category": "Drama", "year": 1950, "description": "Seleção de cinema clássico em arquivo aberto.", "video_url": "", "source_url": "https://archive.org/details/publicmovies212", "free": True},
    {"title": "O mundo em foco", "type": "documentary", "category": "Documentários", "year": 2026, "description": "Documentários e vídeos do arquivo aberto.", "video_url": "", "source_url": "https://archive.org/details/movies", "free": True},
    {"title": "Vidas e lugares", "type": "series", "category": "Séries", "year": 2026, "description": "Coleção documental para descobrir novos lugares.", "video_url": "", "source_url": "https://archive.org/details/moviesandfilms", "free": True},
    {"title": "TV Miramar", "type": "channel", "category": "Notícias", "year": 2026, "description": "Canal e conteúdos oficiais da TV Miramar.", "video_url": "", "source_url": "https://www.youtube.com/@TVMiramar", "free": True},
    {"title": "Miramar online", "type": "channel", "category": "Canais", "year": 2026, "description": "Programação e conteúdos oficiais.", "video_url": "", "source_url": "https://miramar.co.mz/", "free": True},
]


def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      kind TEXT NOT NULL DEFAULT 'guest',
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      expires_at INTEGER NOT NULL,
      FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS catalog (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      type TEXT NOT NULL,
      category TEXT NOT NULL,
      year INTEGER,
      description TEXT,
      video_url TEXT,
      source_url TEXT NOT NULL,
      free INTEGER NOT NULL DEFAULT 1,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS favorites (
      user_id TEXT NOT NULL,
      catalog_id INTEGER NOT NULL,
      created_at INTEGER NOT NULL,
      PRIMARY KEY(user_id, catalog_id),
      FOREIGN KEY(user_id) REFERENCES users(id),
      FOREIGN KEY(catalog_id) REFERENCES catalog(id)
    );
    """)
    if conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0] == 0:
        now = int(time.time())
        conn.executemany("""INSERT INTO catalog
          (title,type,category,year,description,video_url,source_url,free,created_at)
          VALUES (:title,:type,:category,:year,:description,:video_url,:source_url,:free,:created_at)""",
          [{**item, "created_at": now} for item in SEED_CATALOG])
    conn.commit()
    conn.close()


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_guest():
    user_id = "guest_" + uuid.uuid4().hex[:16]
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn = db()
    conn.execute("INSERT INTO users(id,kind,created_at) VALUES(?,?,?)", (user_id, "guest", now))
    conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (token_hash(token), user_id, now + TOKEN_TTL))
    conn.commit()
    conn.close()
    return {"token": token, "user": {"id": user_id, "kind": "guest", "expires_at": now + TOKEN_TTL}}


def current_user(headers):
    value = headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        return None
    conn = db()
    row = conn.execute("""SELECT u.id,u.kind FROM sessions s JOIN users u ON u.id=s.user_id
                          WHERE s.token_hash=? AND s.expires_at>?""", (token_hash(value[7:]), int(time.time()))).fetchone()
    conn.close()
    return dict(row) if row else None


def catalog_item(row, favorite=False):
    item = dict(row)
    item["free"] = bool(item["free"])
    item["favorite"] = bool(favorite)
    return item


class Handler(BaseHTTPRequestHandler):
    server_version = "MaelTV/1.0"

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_OPTIONS(self):
        self.send_json({"ok": True})

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "service": "maeltv", "time": int(time.time())})
        if parsed.path == "/api/me":
            user = current_user(self.headers)
            return self.send_json({"authenticated": bool(user), "user": user})
        if parsed.path == "/api/categories":
            conn = db()
            rows = conn.execute("SELECT category,COUNT(*) AS total FROM catalog GROUP BY category ORDER BY category").fetchall()
            conn.close()
            return self.send_json({"categories": [dict(row) for row in rows]})
        if parsed.path == "/api/catalog":
            q = query.get("q", [""])[0].strip()
            category = query.get("category", [""])[0].strip()
            kind = query.get("type", [""])[0].strip()
            user = current_user(self.headers)
            params = []
            where = []
            if q:
                where.append("(LOWER(title) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?) OR LOWER(category) LIKE LOWER(?))")
                like = f"%{q}%"
                params += [like, like, like]
            if category:
                where.append("category=?")
                params.append(category)
            if kind:
                where.append("type=?")
                params.append(kind)
            sql = "SELECT * FROM catalog" + ((" WHERE " + " AND ".join(where)) if where else "") + " ORDER BY created_at DESC, title"
            conn = db()
            rows = conn.execute(sql, params).fetchall()
            favs = set()
            if user:
                favs = {r[0] for r in conn.execute("SELECT catalog_id FROM favorites WHERE user_id=?", (user["id"],)).fetchall()}
            conn.close()
            return self.send_json({"items": [catalog_item(row, row["id"] in favs) for row in rows], "count": len(rows)})
        return self.send_json({"error": "not_found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        data = self.read_json()
        if parsed.path == "/api/auth/guest":
            return self.send_json(create_guest(), 201)
        if parsed.path == "/api/favorites":
            user = current_user(self.headers)
            if not user:
                return self.send_json({"error": "guest_login_required"}, 401)
            try:
                catalog_id = int(data.get("catalog_id"))
            except (TypeError, ValueError):
                return self.send_json({"error": "catalog_id_required"}, 400)
            conn = db()
            exists = conn.execute("SELECT id FROM catalog WHERE id=?", (catalog_id,)).fetchone()
            if not exists:
                conn.close()
                return self.send_json({"error": "catalog_item_not_found"}, 404)
            old = conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND catalog_id=?", (user["id"], catalog_id)).fetchone()
            if old:
                conn.execute("DELETE FROM favorites WHERE user_id=? AND catalog_id=?", (user["id"], catalog_id))
                favorite = False
            else:
                conn.execute("INSERT INTO favorites(user_id,catalog_id,created_at) VALUES(?,?,?)", (user["id"], catalog_id, int(time.time())))
                favorite = True
            conn.commit()
            conn.close()
            return self.send_json({"catalog_id": catalog_id, "favorite": favorite})
        return self.send_json({"error": "not_found"}, 404)


if __name__ == "__main__":
    init_db()
    print(f"MaelTV backend running on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
