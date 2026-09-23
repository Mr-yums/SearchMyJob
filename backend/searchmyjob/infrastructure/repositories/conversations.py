"""Conversation repository; resets archive history instead of deleting it."""

import time
import uuid

from searchmyjob.domain.errors import WorkspaceError as HTTPException


class ConversationRepository:
    def __init__(self, db):
        self.db = db
        db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations(
            id TEXT PRIMARY KEY,title TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,
            created REAL NOT NULL,updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS conversation_messages(
            message_id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS conversation_messages_chat ON conversation_messages(conversation_id);
        """)
        now = time.time()
        db.execute(
            "INSERT OR IGNORE INTO conversations VALUES (?,?,?,?,?)",
            ("main", "Conversation initiale", 0, now, now),
        )
        db.execute(
            "INSERT OR IGNORE INTO conversation_messages SELECT id,? FROM messages", ("main",)
        )
        if "conversation_id" not in {r[1] for r in db.execute("PRAGMA table_info(runs)")}:
            db.execute("ALTER TABLE runs ADD COLUMN conversation_id TEXT NOT NULL DEFAULT 'main'")

    def default_id(self):
        return self.db.execute(
            "SELECT id FROM conversations WHERE archived=0 ORDER BY created LIMIT 1"
        ).fetchone()[0]

    def get(self, cid, writable=False):
        row = self.db.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
        if not row:
            raise HTTPException(404, "Conversation introuvable")
        if writable and row["archived"]:
            raise HTTPException(
                409, "Cette conversation est archivée. Crée une nouvelle conversation."
            )
        return dict(row)

    def list(self):
        return [
            dict(r)
            for r in self.db.execute("""SELECT c.*,
          (SELECT count(*) FROM conversation_messages m WHERE m.conversation_id=c.id) message_count
          FROM conversations c ORDER BY c.archived,c.updated DESC,c.id""")
        ]

    def create(self, title="Nouvelle conversation"):
        now = time.time()
        cid = uuid.uuid4().hex
        self.db.execute("INSERT INTO conversations VALUES (?,?,?,?,?)", (cid, title, 0, now, now))
        return self.get(cid)

    def rename(self, cid, title):
        self.get(cid)
        self.db.execute(
            "UPDATE conversations SET title=?,updated=? WHERE id=?", (title, time.time(), cid)
        )
        return self.get(cid)

    def reset(self, cid):
        old = self.get(cid, writable=True)
        if self.db.execute(
            "SELECT 1 FROM runs WHERE conversation_id=? AND status='running'", (cid,)
        ).fetchone():
            raise HTTPException(
                409, "Attends la réponse ou arrête la tâche avant de réinitialiser ce chat."
            )
        self.db.execute("SAVEPOINT reset_conversation")
        try:
            self.db.execute("UPDATE conversations SET archived=1 WHERE id=?", (cid,))
            new = self.create(old["title"])
            self.db.execute("RELEASE reset_conversation")
            return new
        except Exception:
            self.db.execute("ROLLBACK TO reset_conversation")
            self.db.execute("RELEASE reset_conversation")
            raise

    def append(self, cid, role, provider, text):
        self.get(cid, writable=True)
        mid = uuid.uuid4().hex
        now = time.time()
        self.db.execute("SAVEPOINT append_message")
        try:
            self.db.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?)", (mid, role, provider, text, now)
            )
            self.db.execute("INSERT INTO conversation_messages VALUES (?,?)", (mid, cid))
            self.db.execute("UPDATE conversations SET updated=? WHERE id=?", (now, cid))
            if role == "user":
                self.db.execute(
                    "UPDATE conversations SET title=? WHERE id=? AND title='Nouvelle conversation'",
                    (" ".join(text.split())[:65], cid),
                )
            self.db.execute("RELEASE append_message")
        except Exception:
            self.db.execute("ROLLBACK TO append_message")
            self.db.execute("RELEASE append_message")
            raise

    def messages(self, cid, limit=150):
        self.get(cid)
        rows = self.db.execute(
            """SELECT m.* FROM messages m JOIN conversation_messages cm ON cm.message_id=m.id
          WHERE cm.conversation_id=? ORDER BY m.created DESC,m.rowid DESC LIMIT ?""",
            (cid, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
