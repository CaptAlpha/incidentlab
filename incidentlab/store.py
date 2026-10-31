import json
import sqlite3
from datetime import datetime, timezone

class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS investigations (id TEXT PRIMARY KEY, created TEXT NOT NULL, result TEXT NOT NULL)')
    def connect(self):
        return sqlite3.connect(self.path, timeout=15)
    def save(self, result):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO investigations VALUES (?, ?, ?)', (result['id'], datetime.now(timezone.utc).isoformat(), json.dumps(result)))
        return result
    def list(self):
        with self.connect() as db:
            rows = db.execute('SELECT result FROM investigations ORDER BY created DESC, rowid DESC').fetchall()
        return [json.loads(r[0]) for r in rows]
    def get(self, key):
        with self.connect() as db:
            row = db.execute('SELECT result FROM investigations WHERE id=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None
