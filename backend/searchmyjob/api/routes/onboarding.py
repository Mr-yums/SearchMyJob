"""Onboarding operations for the workspace."""

from fastapi import APIRouter, Depends

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.models import Activation

router = APIRouter()


@router.get("/api/activation")
async def activation_status(*, E: WorkspaceContext = Depends(get_engine)):
    return E.get("activation")


@router.post("/api/activation")
async def activate(body: Activation, *, E: WorkspaceContext = Depends(get_engine)):
    return E.onboarding.complete(body)
