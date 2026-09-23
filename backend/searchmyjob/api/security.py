"""Security operations for the workspace."""

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from searchmyjob.config import FRONTEND_PORT, PORT


async def boundary(request: Request, call_next):
    allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
    public_port = os.environ.get("SEARCHMYJOB_PUBLIC_PORT", str(PORT))
    allowed.update({f"127.0.0.1:{public_port}", f"localhost:{public_port}"})
    if FRONTEND_PORT.isdigit():
        allowed.update({f"127.0.0.1:{FRONTEND_PORT}", f"localhost:{FRONTEND_PORT}"})
    if request.headers.get("host") not in allowed:
        return JSONResponse({"detail": "Hôte refusé"}, 403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if (
            request.headers.get("origin") not in {f"http://{h}" for h in allowed}
            or request.headers.get("x-workspace-token") != request.app.state.engine.token
        ):
            return JSONResponse({"detail": "Recharger la page : session locale requise"}, 403)
        if int(request.headers.get("content-length", "0")) > 10_000_000:
            return JSONResponse({"detail": "Fichier trop volumineux (10 Mo max)"}, 413)
    response = await call_next(request)
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; frame-ancestors 'none'",
        }
    )
    return response
