"""Application facade: web and MCP share one engine, store and task queue."""

import json
from typing import Any, Protocol

from searchmyjob.domain.errors import WorkspaceError as HTTPException
from searchmyjob.domain.models import Criteria, Generate


class WorkspaceEngine(Protocol):
    store: Any

    def get(self, key): ...
    def set(self, key, value): ...
    def rows(self, sql, args=()): ...
    def offers(self): ...
    def start(self, kind, provider, fn, conversation_id=None): ...
    async def search_and_report(self, provider, criteria, **kwargs): ...
    async def generate(self, body): ...


class WorkspaceService:
    def __init__(self, engine: WorkspaceEngine):
        self.engine = engine

    def profile(self):
        return {"profile": self.engine.get("profile"), "criteria": self.engine.get("criteria")}

    def offers(self, query="", status=None, limit=20, offset=0):
        # Same qualification as the web interface; never claim missing costs are free.
        rows = self.engine.offers()
        query = query.casefold().strip()
        rows = [
            r
            for r in rows
            if (not status or r["status"] == status)
            and (
                not query
                or query
                in " ".join(
                    str(r.get(k, "")) for k in ("title", "company", "description")
                ).casefold()
            )
        ]
        keys = (
            "id",
            "title",
            "company",
            "url",
            "source",
            "status",
            "result_kind",
            "conditions",
            "verification",
            "page_collected_at",
            "application_mode",
        )
        return {
            "items": [{k: r.get(k) for k in keys} for r in rows[offset : offset + limit]],
            "total": len(rows),
            "offset": offset,
            "next_offset": offset + limit if offset + limit < len(rows) else None,
            "scope": "Les 500 dernières offres enregistrées ; aucune collecte externe.",
        }

    def dossier(self, offer_id):
        rows = self.engine.opportunities.dossier_row(offer_id)
        if not rows:
            raise HTTPException(404, "Offre introuvable")
        return {
            "offer": {**json.loads(rows[0]["data"]), "status": rows[0]["status"]},
            "emails": self.engine.outbox.for_offer(offer_id),
            **self.engine.store.dossier(offer_id),
        }

    def email(self, email_id):
        rows = self.engine.outbox.raw_email(email_id)
        if not rows:
            raise HTTPException(404, "Brouillon introuvable")
        return rows[0]

    def document(self, document_id):
        rows = self.engine.document_store.find(document_id)
        if not rows:
            raise HTTPException(404, "Document introuvable")
        return rows[0]

    def run(self, run_id):
        rows = self.engine.runs.find(run_id)
        if not rows:
            raise HTTPException(404, "Tâche introuvable")
        return rows[0]

    def watch(self):
        return {
            "settings": self.engine.get("settings"),
            "next_heartbeat": self.engine.get("next_heartbeat"),
            "runs": self.engine.runs.recent(),
        }

    def search(self, criteria: Criteria, force=False, save_criteria=False, conversation_id=None):
        if not criteria.keywords.strip() and not criteria.axes:
            raise HTTPException(422, "Un métier ou des mots-clés sont requis")
        provider = self.engine.get("settings")["provider"]
        values = criteria.model_dump()
        result = self.engine.start(
            "search",
            provider,
            lambda: self.engine.search_and_report(
                provider,
                values,
                request="Rechercher des opportunités avec ces critères",
                force=force,
            ),
            conversation_id=conversation_id,
        )
        if save_criteria:
            self.engine.set("criteria", values)
        return result

    def prepare(self, body: Generate):
        self.dossier(body.offer_id)  # Reject missing offers before creating a task.
        return self.engine.start(
            "document",
            body.provider,
            lambda: self.engine.generate(body),
            conversation_id=body.conversation_id,
        )
