"""Ai operations for the workspace."""

from fastapi import APIRouter, Depends, HTTPException

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.infrastructure import vault
from searchmyjob.integrations.ai.provider import Configuration
from searchmyjob.integrations.ai.provider import models as ai_models
from searchmyjob.integrations.ai.provider import status as ai_status
from searchmyjob.integrations.ai.provider import test_and_save as ai_test

router = APIRouter()


@router.get("/api/ai")
async def ai_configuration(*, E: WorkspaceContext = Depends(get_engine)):
    return ai_status()


@router.post("/api/ai/models")
async def ai_catalog(body: Configuration, *, E: WorkspaceContext = Depends(get_engine)):
    try:
        return {"models": await ai_models(body)}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/api/ai/test")
async def ai_connection_test(body: Configuration, *, E: WorkspaceContext = Depends(get_engine)):
    if E.task and not E.task.done():
        raise HTTPException(409, "Attends la fin de la tâche avant de changer de modèle.")
    try:
        usage = await ai_test(body)
        E.usage.record(body.provider, usage)
        return {"ok": True, "provider": body.provider, "model": body.model}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, str(exc)) from None


@router.post("/api/ai/disconnect")
async def ai_disconnect(body: Configuration, *, E: WorkspaceContext = Depends(get_engine)):
    if E.task and not E.task.done():
        raise HTTPException(409, "Une tâche est en cours.")
    vault.save({"ai_" + body.provider: None})
    return {"ok": True}
