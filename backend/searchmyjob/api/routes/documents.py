"""Documents operations for the workspace."""

import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from searchmyjob.api.dependencies import get_engine
from searchmyjob.application.ports import WorkspaceContext
from searchmyjob.domain.models import EditDoc, Generate

router = APIRouter()


@router.post("/api/generate")
async def generate(body: Generate, *, E: WorkspaceContext = Depends(get_engine)):
    return E.workspace.prepare(body)


@router.post("/api/documents/{did}")
async def edit_doc(did: str, body: EditDoc, *, E: WorkspaceContext = Depends(get_engine)):
    E.records.revise_document(did, body.text, body.approved)
    return {"ok": True}


@router.get("/api/documents/{did}/download")
async def download(
    did: str, format: Literal["txt", "docx"] = "docx", *, E: WorkspaceContext = Depends(get_engine)
):
    row = E.records.document(did)
    if not row:
        raise HTTPException(404)
    if format == "txt":
        data = row["text"].encode()
        mime = "text/plain; charset=utf-8"
    else:
        from docx import Document

        doc = Document()
        for line in row["text"].splitlines():
            doc.add_paragraph(line)
        buf = io.BytesIO()
        doc.save(buf)
        data = buf.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{row["kind"]}-{did[:8]}.{format}"'},
    )
