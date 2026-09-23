from __future__ import annotations

import time
import uuid

from searchmyjob.domain.mail import Envelope, MailError, MailSender


class Outbox:
    """Brouillons d'e-mail persistants (SQLite) et leur cycle de vie."""

    DRAFT, SENT, DISCARDED = "draft", "sent", "discarded"

    def __init__(self, db):
        self.db = db
        self.db.execute("""CREATE TABLE IF NOT EXISTS emails(id TEXT PRIMARY KEY,offer_id TEXT,document_id TEXT,
            origin TEXT,to_addr TEXT,subject TEXT,body TEXT,status TEXT,error TEXT DEFAULT '',
            message_id TEXT DEFAULT '',created REAL,updated REAL,sent_at REAL)""")

    def propose(self, subject, body, to="", offer_id="", document_id="", origin="agent"):
        eid = uuid.uuid4().hex
        stamp = time.time()
        self.db.execute(
            "INSERT INTO emails(id,offer_id,document_id,origin,to_addr,subject,body,status,created,updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, offer_id, document_id, origin, to, subject, body, self.DRAFT, stamp, stamp),
        )
        return self.get(eid)

    def all(self):
        return [
            self._row(r)
            for r in self.db.execute("SELECT * FROM emails ORDER BY created DESC LIMIT 200")
        ]

    def get(self, eid):
        row = self.db.execute("SELECT * FROM emails WHERE id=?", (eid,)).fetchone()
        if not row:
            raise LookupError("Brouillon introuvable.")
        return self._row(row)

    def update(self, eid, to, subject, body):
        draft = self.get(eid)
        if draft["status"] != self.DRAFT:
            raise MailError("Cet e-mail est déjà parti ou a été écarté : il ne se modifie plus.")
        self.db.execute(
            "UPDATE emails SET to_addr=?,subject=?,body=?,updated=?,error=? WHERE id=?",
            (to.strip(), subject.strip(), body, time.time(), "", eid),
        )
        return self.get(eid)

    def discard(self, eid):
        if self.get(eid)["status"] == self.SENT:
            raise MailError("Un e-mail envoyé ne peut pas être écarté.")
        self.db.execute(
            "UPDATE emails SET status=?,updated=? WHERE id=?", (self.DISCARDED, time.time(), eid)
        )
        return self.get(eid)

    def send(self, eid, service: MailSender, confirm: bool, name=""):
        """Seule voie d'envoi : confirmation explicite, brouillon encore ouvert, transport injecté."""
        if not confirm:
            raise MailError("Coche « J’ai relu et validé cet e-mail » avant d’envoyer.")
        draft = self.get(eid)
        if draft["status"] == self.SENT:
            raise MailError("Cet e-mail est déjà parti.")
        if draft["status"] != self.DRAFT:
            raise MailError("Ce brouillon a été écarté.")
        envelope = Envelope(
            draft["to"], draft["subject"], draft["body"], name=name, identifier="email-" + eid
        )
        try:
            receipt = service.send(envelope)
        except MailError as exc:
            self.db.execute(
                "UPDATE emails SET error=?,updated=? WHERE id=?", (str(exc)[:500], time.time(), eid)
            )
            raise
        self.db.execute(
            "UPDATE emails SET status=?,message_id=?,sent_at=?,updated=?,error=? WHERE id=?",
            (self.SENT, receipt.message_id, receipt.at, receipt.at, "", eid),
        )
        return self.get(eid)

    @staticmethod
    def _row(row):
        d = dict(row)
        d["to"] = d.pop("to_addr")
        return d

    def raw_email(self, email_id):
        return [
            dict(row) for row in self.db.execute("SELECT * FROM emails WHERE id=?", (email_id,))
        ]

    def for_offer(self, offer_id):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,subject,status,created FROM emails WHERE offer_id=? ORDER BY created DESC",
                (offer_id,),
            )
        ]
