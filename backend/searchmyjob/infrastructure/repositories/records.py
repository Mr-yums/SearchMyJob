"""Workspace queries and transactional document edits."""

import time
import uuid

from searchmyjob.domain.errors import WorkspaceError


class RecordsRepository:
    def __init__(self, db):
        self.db = db

    def _rows(self, sql, args=()):
        return [dict(row) for row in self.db.execute(sql, args).fetchall()]

    def imports(self):
        return self._rows(
            "SELECT id,name,mime,created,length(content) size FROM imported_files ORDER BY created DESC"
        )

    def tool_calls(self, conversation_id):
        return self._rows(
            "SELECT * FROM agent_tool_calls WHERE conversation_id=? ORDER BY created DESC LIMIT 30",
            (conversation_id,),
        )

    def runs(self):
        return self._rows("SELECT * FROM runs ORDER BY created DESC LIMIT 60")

    def documents(self):
        return self._rows("SELECT * FROM documents ORDER BY created DESC")

    def history(self):
        return self._rows("SELECT key,value,created FROM config_history ORDER BY id DESC LIMIT 100")

    def offers(self):
        return self._rows("SELECT * FROM offers ORDER BY found DESC")

    def source(self, identifier):
        return self.db.execute("SELECT * FROM offer_sources WHERE id=?", (identifier,)).fetchone()

    def offer(self, identifier):
        return self.db.execute("SELECT * FROM offers WHERE id=?", (identifier,)).fetchone()

    def imported_file(self, identifier):
        return self.db.execute("SELECT * FROM imported_files WHERE id=?", (identifier,)).fetchone()

    def document(self, identifier):
        return self.db.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()

    def set_offer_status(self, identifier, status):
        if not self.db.execute(
            "UPDATE offers SET status=? WHERE id=?", (status, identifier)
        ).rowcount:
            raise WorkspaceError(404)

    def revise_document(self, identifier, text, approved):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.document(identifier)
            if row is None:
                raise WorkspaceError(404)
            self.db.execute(
                "INSERT INTO revisions VALUES (?,?,?,?)",
                (uuid.uuid4().hex, identifier, row["text"], time.time()),
            )
            self.db.execute(
                "UPDATE documents SET text=?,approved=? WHERE id=?",
                (text, int(approved), identifier),
            )
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
