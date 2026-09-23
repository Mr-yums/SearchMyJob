from searchmyjob.integrations.search import providers as source_providers

"""Connections operations for the workspace."""
import asyncio
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.countries import COUNTRIES
from searchmyjob.domain.models import BrightBudget, Credentials, Criteria
from searchmyjob.infrastructure import bright_budget, vault
from searchmyjob.integrations.search.providers import ProviderError

router = APIRouter()


@router.get("/api/search/options")
async def search_options():
    return {"countries": list(COUNTRIES)}


@router.get("/api/bright/usage")
async def bright_monthly_usage(*, E: WorkspaceContext = Depends(get_engine)):
    return await E.bright_monthly.get()


@router.post("/api/bright/budget")
async def bright_local_budget(payload: BrightBudget, *, E: WorkspaceContext = Depends(get_engine)):
    """[OXIO] Plafond local d'appels facturants. Sans effet sur le quota mensuel réel du compte."""
    if payload.reset:
        bright_budget.reset()
    if payload.limit is not None:
        try:
            return bright_budget.set_limit(payload.limit)
        except bright_budget.BrightError as e:
            raise HTTPException(400, str(e))
    return bright_budget.status()


@router.get("/api/connections")
async def connection_status(*, E: WorkspaceContext = Depends(get_engine)):
    keys = vault.read()
    return {
        "france": bool(keys.get("ft_client_id") and keys.get("ft_client_secret")),
        "bright": bool(keys.get("bright_key")),
        "checks": E.get("connections"),
    }


@router.post("/api/connections/{source}/test")
async def test_source(
    source: Literal["france", "bright"],
    body: Criteria | None = None,
    *,
    E: WorkspaceContext = Depends(get_engine),
):
    if E.task and not E.task.done():
        raise HTTPException(409, "Une tâche est en cours.")
    criteria = (body or Criteria.model_validate(E.get("criteria"))).model_dump()
    criteria["keywords"] = criteria["keywords"] or "jobs"
    if source == "france" and criteria["country"] != "fr":
        raise HTTPException(422, "France Travail couvre la France.")
    try:
        if source == "france":
            rows = await source_providers.france_travail(criteria, 1)
        else:
            from searchmyjob.domain.search_quality import search_plan

            rows = []
            for plan in search_plan(
                {**criteria, "axes": [], "keywords": criteria["keywords"].replace(",", " ")}
            ):
                rows.extend(await source_providers.bright(plan))
        states = E.get("connections")
        name = "France Travail" if source == "france" else "Bright Data"
        states[name] = {
            "ok": True,
            "message": "Connexion vérifiée par une recherche de test",
            "checked": time.time(),
        }
        E.set("connections", states)
        return {"ok": True, "results": len(rows)}
    except ProviderError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(422, "Source indisponible ou réponse illisible.") from None


@router.post("/api/connections")
async def connections(body: Credentials, *, E: WorkspaceContext = Depends(get_engine)):
    await asyncio.to_thread(vault.save, body.model_dump())
    E.bright_monthly.invalidate()
    return {"ok": True}


@router.post("/api/connections/test")
async def connection_test(*, E: WorkspaceContext = Depends(get_engine)):
    async def test():
        criteria = E.get("criteria")
        states = {}
        for name, fn in [
            (
                "France Travail",
                lambda: source_providers.france_travail(criteria, 1),
            ),
            ("Bright Data", source_providers.bright_status),
        ]:
            try:
                result = await fn()
                message = "Connexion vérifiée"
                if name == "Bright Data":
                    message = result["status"]
                states[name] = {"ok": True, "message": message, "checked": time.time()}
            except Exception as e:
                states[name] = {
                    "ok": False,
                    "message": str(e)
                    if isinstance(e, ProviderError)
                    else "Échec réseau ou coffre inaccessible",
                    "checked": time.time(),
                }
        E.set("connections", states)
        return "\n".join(k + " : " + v["message"] for k, v in states.items())

    return E.start("connections", "sources", test)
