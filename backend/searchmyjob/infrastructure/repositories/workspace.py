"""Durable sources, cache, imports and configuration history for a single workspace."""

import hashlib
import json
import re
import time
from urllib.parse import urlsplit


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


class WorkspaceStore:
    def __init__(self, db):
        self.db = db
        db.executescript("""
        CREATE TABLE IF NOT EXISTS config_history(id INTEGER PRIMARY KEY,key TEXT,value TEXT,created REAL);
        CREATE INDEX IF NOT EXISTS config_history_key ON config_history(key,created);
        CREATE TABLE IF NOT EXISTS search_cache(key TEXT PRIMARY KEY,source TEXT,query TEXT,criteria TEXT,payload TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS offer_sources(id TEXT PRIMARY KEY,offer_id TEXT,source TEXT,url TEXT,kind TEXT,content TEXT,created REAL);
        CREATE INDEX IF NOT EXISTS offer_sources_offer ON offer_sources(offer_id,created);
        CREATE TABLE IF NOT EXISTS offer_pages(offer_id TEXT PRIMARY KEY,url TEXT,content TEXT,contacts TEXT,application_mode TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS imported_files(id TEXT PRIMARY KEY,name TEXT,mime TEXT,content BLOB,text TEXT,created REAL);
        """)
        for row in db.execute("SELECT id,data,found FROM offers").fetchall():
            self.source(row["id"], json.loads(row["data"]), row["found"])
        for row in db.execute(
            "SELECT key,value FROM config WHERE key IN ('profile','settings','criteria','preferences')"
        ).fetchall():
            if not db.execute(
                "SELECT 1 FROM config_history WHERE key=? LIMIT 1", (row["key"],)
            ).fetchone():
                db.execute(
                    "INSERT INTO config_history(key,value,created) VALUES (?,?,?)",
                    (row["key"], row["value"], time.time()),
                )

    def source(self, offer_id, row, created=None):
        content = json.dumps(row, ensure_ascii=False)
        identifier = digest([offer_id, row])
        self.db.execute(
            "INSERT OR IGNORE INTO offer_sources VALUES (?,?,?,?,?,?,?)",
            (
                identifier,
                offer_id,
                row.get("source", ""),
                row.get("url", ""),
                "search_result",
                content,
                created or time.time(),
            ),
        )

    def cache_get(self, key, hours):
        row = self.db.execute(
            "SELECT payload,created FROM search_cache WHERE key=?", (key,)
        ).fetchone()
        if not row or hours <= 0 or time.time() - row["created"] >= hours * 3600:
            return None
        return json.loads(row["payload"]), row["created"]

    def cache_put(self, key, source, query, criteria, rows):
        self.db.execute(
            "INSERT OR REPLACE INTO search_cache VALUES (?,?,?,?,?,?)",
            (
                key,
                source,
                query,
                json.dumps(criteria, ensure_ascii=False),
                json.dumps(rows, ensure_ascii=False),
                time.time(),
            ),
        )

    def page(self, offer_id):
        row = self.db.execute("SELECT * FROM offer_pages WHERE offer_id=?", (offer_id,)).fetchone()
        if not row:
            return None
        return {**dict(row), "contacts": json.loads(row["contacts"])}

    def save_page(self, offer_id, url, text, source="Bright Data"):
        # A discovered address is an unverified candidate, never an inferred recipient.
        contacts = []
        for match in re.finditer(
            r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w-]|\.[A-Z0-9])", text, re.I
        ):
            email = match.group().lower()
            if email not in [c["email"] for c in contacts]:
                contacts.append(
                    {
                        "email": email,
                        "source_url": url,
                        "evidence": text[max(0, match.start() - 100) : match.end() + 100],
                        "status": "à vérifier",
                    }
                )
            if len(contacts) >= 20:
                break
        host = (urlsplit(url).hostname or "").lower()
        platform = any(
            host == h or host.endswith("." + h)
            for h in ("upwork.com", "freelancer.com", "malt.fr", "malt.com")
        )
        mode = "platform" if platform else ("contact_found" if contacts else "contact_not_found")
        now = time.time()
        self.db.execute(
            "INSERT OR REPLACE INTO offer_pages VALUES (?,?,?,?,?,?)",
            (offer_id, url, text, json.dumps(contacts, ensure_ascii=False), mode, now),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO offer_sources VALUES (?,?,?,?,?,?,?)",
            (digest([offer_id, url, text]), offer_id, source, url, "page", text, now),
        )
        return self.page(offer_id)

    def dossier(self, offer_id):
        return {
            "page": self.page(offer_id),
            "sources": [
                dict(r)
                for r in self.db.execute(
                    "SELECT id,source,url,kind,created FROM offer_sources WHERE offer_id=? ORDER BY created DESC",
                    (offer_id,),
                )
            ],
            "documents": [
                dict(r)
                for r in self.db.execute(
                    "SELECT id,kind,approved,created FROM documents WHERE offer_id=? ORDER BY created DESC",
                    (offer_id,),
                )
            ],
        }

    def import_file(self, name, mime, content, text):
        identifier = hashlib.sha256(content).hexdigest()
        self.db.execute(
            "INSERT OR IGNORE INTO imported_files VALUES (?,?,?,?,?,?)",
            (identifier, name, mime, content, text, time.time()),
        )
        return identifier

    def source_rows(self, source_id):
        return [
            dict(row)
            for row in self.db.execute("SELECT * FROM offer_sources WHERE id=?", (source_id,))
        ]
