"""Jobs operations for the workspace."""

import asyncio
import time
import uuid

from searchmyjob.domain.errors import WorkspaceError as HTTPException
from searchmyjob.integrations.search.providers import ProviderError


class JobsService:
    """Jobs use cases sharing the workspace unit of work."""

    def __init__(self, engine):
        self.engine = engine

    def start(self, kind, provider, fn, conversation_id=None):
        if self.engine.task and not self.engine.task.done():
            raise HTTPException(
                409, "Une tâche est déjà en cours. Son résultat apparaîtra dans le journal."
            )
        cid = conversation_id or self.engine.conversation_id()
        self.engine.conversations.get(cid, writable=True)
        rid = uuid.uuid4().hex
        self.engine.runs.add(rid, kind, provider, "running", time.time(), cid)

        async def work():
            scope = self.engine.conversation_scope.set(cid)
            self.engine.current_run = rid
            self.engine.phase("Préparation de la demande")
            try:
                output = await fn()
                self.engine.phase("Terminé")
                self.engine.runs.complete(str(output), time.time(), rid)
            except asyncio.CancelledError:
                self.engine.phase("Arrêté")
                self.engine.runs.cancel(time.time(), rid)
                raise
            except Exception as exc:
                self.engine.phase("Échec")
                error = (
                    str(exc)
                    if isinstance(exc, (ProviderError, ValueError, RuntimeError))
                    else f"Opération impossible ({type(exc).__name__})."
                )
                self.engine.runs.fail(error[:1000], time.time(), rid)
                self.engine.message("system", "système", error[:1000])
            finally:
                self.engine.current_run = None
                self.engine.conversation_scope.reset(scope)

        self.engine.task = asyncio.create_task(work())
        return {"run_id": rid}

    def phase(self, text):
        # [Sol] The single active job owns its progress until its final response.
        if self.engine.current_run:
            self.engine.runs.set_phase(text, self.engine.current_run)
