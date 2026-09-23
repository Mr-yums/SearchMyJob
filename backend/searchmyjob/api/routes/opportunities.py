from searchmyjob.integrations.search import providers as source_providers

"""Opportunities operations for the workspace."""
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.models import Criteria, Status

router = APIRouter()


@router.get("/api/export/offers.csv")
async def export_offers(*, E: WorkspaceContext = Depends(get_engine)):
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "titre",
            "entreprise",
            "source",
            "url",
            "description",
            "statut",
            "collecte_page",
            "candidature",
            "emails_a_verifier",
        ]
    )

    def cell(value):
        value = str(value or "")
        return (
            "'" + value
            if value.lstrip().startswith(("=", "+", "-", "@"))
            or value.startswith(("\t", "\r", "\n"))
            else value
        )

    for saved in E.records.offers():
        row = json.loads(saved["data"])
        page = E.store.page(saved["id"])
        writer.writerow(
            [
                cell(v)
                for v in [
                    saved["id"],
                    row.get("title"),
                    row.get("company"),
                    row.get("source"),
                    row.get("url"),
                    row.get("description"),
                    saved["status"],
                    page["created"] if page else "",
                    page["application_mode"] if page else "not_checked",
                    ", ".join(c["email"] for c in page["contacts"]) if page else "",
                ]
            ]
        )
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="searchmyjob-offres.csv"'},
    )


@router.get("/api/offers/{oid}/dossier")
async def offer_dossier(oid: str, *, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.dossier(oid)


@router.get("/api/sources/{sid}")
async def source_detail(sid: str, *, E: WorkspaceContext = Depends(get_engine)):
    row = E.records.source(sid)
    if not row:
        raise HTTPException(404)
    return dict(row)


@router.post("/api/offers/{oid}/collect")
async def collect_offer(
    oid: str, force: bool = False, *, E: WorkspaceContext = Depends(get_engine)
):
    row = E.records.offer(oid)
    if not row:
        raise HTTPException(404)
    if not force and E.store.page(oid):
        return {"cached": True}
    data = json.loads(row["data"])
    if data.get("google_redirect"):
        raise HTTPException(422, "Le lien de destination reste à résoudre.")

    async def collect():
        E.phase("Lecture et sauvegarde de la page source")
        text = await source_providers.bright_page(data.get("url", ""))
        E.store.save_page(oid, data.get("url", ""), text)
        return "Page enregistrée dans la fiche. Les coordonnées repérées restent à vérifier."

    return E.start("source", "Bright Data", collect)


@router.post("/api/criteria")
async def criteria(body: Criteria, *, E: WorkspaceContext = Depends(get_engine)):
    E.set("criteria", body.model_dump())
    return {"ok": True}


@router.post("/api/search")
async def search(
    body: Criteria,
    force: bool = False,
    conversation_id: str | None = None,
    *,
    E: WorkspaceContext = Depends(get_engine),
):
    return E.workspace.search(
        body, force=force, save_criteria=True, conversation_id=conversation_id
    )


@router.post("/api/offers/{oid}")
async def offer_status(oid: str, body: Status, *, E: WorkspaceContext = Depends(get_engine)):
    E.records.set_offer_status(oid, body.status)
    return {"ok": True}
