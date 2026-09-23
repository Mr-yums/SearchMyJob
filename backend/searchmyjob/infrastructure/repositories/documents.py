"""Persistence operations for documents."""


class DocumentsRepository:
    def __init__(self, db):
        self.db = db

    def find(self, document_id):
        return [
            dict(row)
            for row in self.db.execute("SELECT * FROM documents WHERE id=?", (document_id,))
        ]

    def add(self, document_id, offer_id, kind, text, approved, created):
        return self.db.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?)",
            (
                document_id,
                offer_id,
                kind,
                text,
                approved,
                created,
            ),
        )
