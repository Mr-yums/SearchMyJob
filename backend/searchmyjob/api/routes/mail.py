"""Mail operations for the workspace."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.mail import MailService
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.mail import MailError
from searchmyjob.domain.models import EmailCreate, EmailDraftIn, EmailSend, MailPrefs

router = APIRouter()


@router.post("/api/mail/connect")
async def mail_connect(file: UploadFile, *, E: WorkspaceContext = Depends(get_engine)):
    raw = await file.read(MailService.MAX_CLIENT_JSON + 1)
    try:
        url = await asyncio.to_thread(E.mail.connect, raw)
    except MailError as e:
        raise HTTPException(422, str(e))
    return {"auth_url": url}


@router.post("/api/mail/disconnect")
async def mail_disconnect(*, E: WorkspaceContext = Depends(get_engine)):
    await asyncio.to_thread(E.mail.disconnect)
    return {"ok": True}


@router.post("/api/mail/prefs")
async def mail_prefs(body: MailPrefs, *, E: WorkspaceContext = Depends(get_engine)):
    E.set("mail_prefs", body.model_dump())
    return {"ok": True}


@router.post("/api/mail/test")
async def mail_test(*, E: WorkspaceContext = Depends(get_engine)):
    try:
        receipt = await asyncio.to_thread(E.mail.send_test, E.get("mail_prefs")["sender_name"])
    except MailError as e:
        raise HTTPException(422, str(e))
    return {"ok": True, "to": receipt.to}


@router.post("/api/emails")
async def email_create(body: EmailCreate, *, E: WorkspaceContext = Depends(get_engine)):
    offer_id, title, text = body.offer_id, "", ""
    if body.document_id:
        row = E.records.document(body.document_id)
        if not row:
            raise HTTPException(404, "Document introuvable")
        text = row["text"]
        offer_id = offer_id or row["offer_id"] or ""
    if offer_id:
        rows = [row] if (row := E.records.offer(offer_id)) else []
        if not rows and not body.document_id:
            raise HTTPException(404, "Offre introuvable")
        title = json.loads(rows[0]["data"]).get("title", "") if rows else ""
    return E.outbox.propose(
        "Candidature" + (" — " + title if title else ""),
        text,
        offer_id=offer_id,
        document_id=body.document_id,
        origin="toi",
    )


@router.post("/api/emails/{eid}")
async def email_update(eid: str, body: EmailDraftIn, *, E: WorkspaceContext = Depends(get_engine)):
    try:
        return E.outbox.update(eid, body.to, body.subject, body.body)
    except LookupError:
        raise HTTPException(404)
    except MailError as e:
        raise HTTPException(409, str(e))


@router.post("/api/emails/{eid}/send")
async def email_send(eid: str, body: EmailSend, *, E: WorkspaceContext = Depends(get_engine)):
    try:
        return await asyncio.to_thread(
            E.outbox.send, eid, E.mail, body.confirm, E.get("mail_prefs")["sender_name"]
        )
    except LookupError:
        raise HTTPException(404)
    except MailError as e:
        raise HTTPException(422, str(e))


@router.post("/api/emails/{eid}/discard")
async def email_discard(eid: str, *, E: WorkspaceContext = Depends(get_engine)):
    try:
        return E.outbox.discard(eid)
    except LookupError:
        raise HTTPException(404)
    except MailError as e:
        raise HTTPException(409, str(e))
