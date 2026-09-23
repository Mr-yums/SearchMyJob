"""Agents operations for the workspace."""

from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from searchmyjob.config import PORT, PROJECT_ROOT
from searchmyjob.domain.guidance import guidance, report_format
from searchmyjob.domain.models import AgentSearch, Criteria, Generate
from searchmyjob.infrastructure.bright_budget import status as bright_usage
from searchmyjob.integrations.search.providers import ProviderError

ROOT = PROJECT_ROOT


from fastapi import APIRouter, Depends

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext

router = APIRouter()


@router.get("/api/agent/session")
async def agent_session(*, E: WorkspaceContext = Depends(get_engine)):
    # Local adapter handshake: never forward this token to a model.
    return {
        "token": E.token,
        "search_schema": AgentSearch.model_json_schema(),
        "generate_schema": Generate.model_json_schema(),
        "instructions": guidance(E.objectif()) + "\n" + report_format(E.objectif()),
    }


@router.get("/api/agent/runtime")
async def runtime_catalog(request: Request, *, E: WorkspaceContext = Depends(get_engine)):
    return E.agent_tools.catalog(request.headers.get("x-agent-session", ""))


@router.post("/api/agent/runtime/{tool}")
async def runtime_tool(tool: str, request: Request, *, E: WorkspaceContext = Depends(get_engine)):
    token = request.headers.get("x-agent-session", "")
    E.agent_tools.session(token)
    try:
        return await E.agent_tools.call(token, tool, await request.json())
    except (ValueError, ProviderError) as exc:
        raise HTTPException(422, str(exc)[:600]) from None
    except OSError, RuntimeError:
        raise HTTPException(
            422, "Service ou compte indisponible. Aucun nouvel essai automatique."
        ) from None


@router.get("/api/integrations/mcp-config")
async def mcp_config(*, E: WorkspaceContext = Depends(get_engine)):
    import shutil

    config = {
        "mcpServers": {
            "searchmyjob": {
                "command": shutil.which("node") or "node",
                "args": [str(ROOT / "mcp/workspace-server.mjs")],
                "env": {"SEARCHMYJOB_API": f"http://127.0.0.1:{PORT}"},
            }
        }
    }
    return JSONResponse(
        config, headers={"Content-Disposition": 'attachment; filename="searchmyjob-mcp.json"'}
    )


@router.get("/api/agent/profile")
async def agent_profile(*, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.profile()


@router.get("/api/agent/offers")
async def agent_offers(
    query: str = "",
    status: Literal["new", "saved", "dismissed", "ready"] | None = None,
    limit: int = 20,
    offset: int = 0,
    *,
    E: WorkspaceContext = Depends(get_engine),
):
    if len(query) > 200 or not 1 <= limit <= 50 or not 0 <= offset <= 500:
        raise HTTPException(422, "Pagination ou filtre invalide")
    return E.workspace.offers(query, status, limit, offset)


@router.get("/api/agent/documents/{did}")
async def agent_document(did: str, *, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.document(did)


@router.get("/api/agent/emails/{eid}")
async def agent_email(eid: str, *, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.email(eid)


@router.get("/api/agent/runs/{rid}")
async def agent_run(rid: str, *, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.run(rid)


@router.get("/api/agent/watch")
async def agent_watch(*, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.watch()


@router.get("/api/agent/usage")
async def agent_usage(*, E: WorkspaceContext = Depends(get_engine)):
    return {"bright_local_budget": bright_usage(), "agents": E.usage.summary()}


@router.post("/api/agent/search")
async def agent_search(body: AgentSearch, *, E: WorkspaceContext = Depends(get_engine)):
    # One-off agent searches do not overwrite the user's saved watch preferences.
    values = {
        **E.get("criteria"),
        **(body.criteria.model_dump(exclude_unset=True) if body.criteria else {}),
    }
    return E.workspace.search(Criteria.model_validate(values), force=body.force)
