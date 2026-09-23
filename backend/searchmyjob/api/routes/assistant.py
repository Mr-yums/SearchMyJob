"""Assistant operations for the workspace."""

import time

from fastapi import APIRouter, Depends, HTTPException

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.models import Chat, Settings

router = APIRouter()


@router.post("/api/settings")
async def settings(body: Settings, *, E: WorkspaceContext = Depends(get_engine)):
    if body.start_hour >= body.end_hour:
        raise HTTPException(422, "La fin doit être après le début")
    if body.enabled and not E.get("criteria")["keywords"].strip():
        raise HTTPException(422, "Définis un métier avant d’activer la veille")
    E.set("settings", body.model_dump())
    E.set("heartbeat_draft", None)
    E.set("next_heartbeat", time.time() + body.interval_hours * 3600)
    return {"ok": True}


@router.post("/api/chat")
async def chat(body: Chat, *, E: WorkspaceContext = Depends(get_engine)):
    return E.start(
        "chat", body.provider, lambda: E.chat(body), conversation_id=body.conversation_id
    )


@router.post("/api/checkup")
async def checkup(conversation_id: str | None = None, *, E: WorkspaceContext = Depends(get_engine)):
    return E.start(
        "checkup", E.get("settings")["provider"], E.heartbeat, conversation_id=conversation_id
    )


@router.post("/api/cancel")
async def cancel(*, E: WorkspaceContext = Depends(get_engine)):
    if E.task:
        E.task.cancel()
    return {"ok": True}
