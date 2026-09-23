import json
import time
from contextlib import contextmanager


class ConfigurationRepository:
    def __init__(self, db):
        self.db = db

    def get(self, k):
        r = self.db.execute("SELECT value FROM config WHERE key=?", (k,)).fetchone()
        return json.loads(r[0]) if r else None

    def set(self, k, v):
        value = json.dumps(v, ensure_ascii=False)
        self.db.execute("SAVEPOINT config_write")
        try:
            if k in ("criteria", "settings", "profile", "preferences") and self.get(k) != v:
                self.db.execute(
                    "INSERT INTO config_history(key,value,created) VALUES (?,?,?)",
                    (k, value, time.time()),
                )
            self.db.execute("INSERT OR REPLACE INTO config VALUES (?,?)", (k, value))
            self.db.execute("RELEASE config_write")
        except Exception:
            self.db.execute("ROLLBACK TO config_write")
            self.db.execute("RELEASE config_write")
            raise

    def has_records(self, table):
        if table not in {"offers", "messages", "documents", "runs", "emails"}:
            raise ValueError("Unsupported workspace table")
        return bool(self.db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone())

    @contextmanager
    def transaction(self, name):
        if name != "activation":
            raise ValueError("Unsupported transaction")
        self.db.execute("SAVEPOINT activation")
        try:
            yield
            self.db.execute("RELEASE activation")
        except BaseException:
            self.db.execute("ROLLBACK TO activation")
            self.db.execute("RELEASE activation")
            raise
