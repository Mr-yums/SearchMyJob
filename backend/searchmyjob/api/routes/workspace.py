"""Workspace operations for the workspace."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.agent_tools import TOOL_LABELS
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.models import HeartbeatDraft, Settings, UIPreferences
from searchmyjob.infrastructure.bright_budget import status as bright_usage

router = APIRouter()


@router.get("/api/state")
async def state(conversation_id: str | None = None, *, E: WorkspaceContext = Depends(get_engine)):
    cid = conversation_id or E.conversations.default_id()
    E.conversations.get(cid)
    return {
        "imports": E.records.imports(),
        "bright_budget": bright_usage(),
        "agent_usage": E.usage.summary(),
        "token": E.token,
        "profile": E.get("profile"),
        "criteria": E.get("criteria"),
        "settings": E.get("settings"),
        "next_heartbeat": E.get("next_heartbeat"),
        "conversation_id": cid,
        "conversations": E.conversations.list(),
        "tool_calls": [
            {**r, "label": TOOL_LABELS.get(r["tool"], r["tool"])} for r in E.records.tool_calls(cid)
        ],
        "messages": E.conversations.messages(cid),
        "offers": E.offers(),
        "runs": E.records.runs(),
        "documents": E.records.documents(),
        "connections": E.get("connections"),
        "models": {x: E.get("model_" + x) for x in ("deepseek", "kimi", "claude", "openai")},
        "emails": E.outbox.all(),
        "mail": {**await asyncio.to_thread(E.mail.status), **E.get("mail_prefs")},
    }


@router.get("/api/workspace-memory")
async def workspace_memory(*, E: WorkspaceContext = Depends(get_engine)):
    return {"preferences": E.get("preferences"), "heartbeat_draft": E.get("heartbeat_draft")}


@router.post("/api/preferences")
async def preferences(body: UIPreferences, *, E: WorkspaceContext = Depends(get_engine)):
    pages = {"conversation", "offers", "documents", "mail", "profile", "heartbeat", "connections"}
    if (
        body.layout not in (1, 2, 4)
        or len(body.panels) != 4
        or len(set(body.panels)) != 4
        or not set(body.panels).issubset(pages)
        or not set(body.tabs).issubset(pages)
    ):
        raise HTTPException(422, "Disposition invalide")
    E.set("preferences", body.model_dump())
    return {"ok": True}


@router.post("/api/heartbeat-draft")
async def heartbeat_draft(body: HeartbeatDraft, *, E: WorkspaceContext = Depends(get_engine)):
    if len(json.dumps(body.values)) > 10000 or not set(body.values).issubset(Settings.model_fields):
        raise HTTPException(422, "Brouillon invalide")
    E.set("heartbeat_draft", None if body.values == E.get("settings") else body.values)
    return {"ok": True}


@router.get("/api/config-history")
async def config_history(*, E: WorkspaceContext = Depends(get_engine)):
    return E.records.history()


@router.get("/api/health")
async def health(*, E: WorkspaceContext = Depends(get_engine)):
    return {"status": "ok", "service": "SearchMyJob", "version": "0.3.8"}
