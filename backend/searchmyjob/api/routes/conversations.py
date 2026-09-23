"""Conversations operations for the workspace."""

from fastapi import APIRouter, Depends, HTTPException

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.models import ConversationTitle

router = APIRouter()


@router.get("/api/conversations")
async def conversations(*, E: WorkspaceContext = Depends(get_engine)):
    return E.conversations.list()


@router.post("/api/conversations")
async def create_conversation(
    body: ConversationTitle, *, E: WorkspaceContext = Depends(get_engine)
):
    if not body.title.strip():
        raise HTTPException(422, "Le titre ne peut pas être vide")
    return E.conversations.create(body.title.strip())


@router.post("/api/conversations/{cid}/rename")
async def rename_conversation(
    cid: str, body: ConversationTitle, *, E: WorkspaceContext = Depends(get_engine)
):
    if not body.title.strip():
        raise HTTPException(422, "Le titre ne peut pas être vide")
    return E.conversations.rename(cid, body.title.strip())


@router.post("/api/conversations/{cid}/reset")
async def reset_conversation(cid: str, *, E: WorkspaceContext = Depends(get_engine)):
    return E.conversations.reset(cid)
