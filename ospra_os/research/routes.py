from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ospra_os.core.settings import get_settings
from ospra_os.research.models import (
    enqueue_terms,
    list_candidates,
    list_queue,
    run_research_once,
    update_candidate_status,
)

router = APIRouter(prefix="/admin/research", tags=["admin", "research"])


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


async def _extract_terms(request: Request, terms: Optional[List[str]]) -> List[str]:
    if terms:
        return [t.strip() for t in terms if t and t.strip()]
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        raw = form.get("terms", "")
        return [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
    return []


@router.post("/queue")
async def research_queue(
    request: Request,
    terms: Optional[List[str]] = Body(default=None, embed=True),
):
    clean_terms = await _extract_terms(request, terms)
    count = enqueue_terms(clean_terms)
    payload = {"ok": True, "queued_total": count, "added": len(clean_terms)}
    if _wants_html(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    return JSONResponse(payload)


@router.get("/queue")
def research_queue_list(limit: int = 50):
    rows = list_queue(limit=limit)
    return {"ok": True, "count": len(rows), "items": rows}


@router.post("/run")
async def research_run(
    request: Request,
    max_terms: Optional[int] = Query(default=None, ge=1),
    max_candidates_per_term: Optional[int] = Query(default=None, ge=1),
    terms: Optional[List[str]] = Body(default=None, embed=True),
):
    clean_terms = await _extract_terms(request, terms)
    if clean_terms:
        enqueue_terms(clean_terms)

    settings = get_settings()
    created = run_research_once(
        max_terms=max_terms or settings.RESEARCH_MAX_TERMS,
        max_candidates_per_term=max_candidates_per_term
        or settings.RESEARCH_MAX_CANDIDATES_PER_TERM,
    )
    payload = {"ok": True, "created": created}
    if _wants_html(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    return JSONResponse(payload)


@router.get("/candidates")
def research_candidates(status: Optional[str] = Query(default=None), limit: int = 50):
    rows = list_candidates(status=status, limit=limit)
    return {"ok": True, "count": len(rows), "items": rows}


@router.post("/candidates/{cid}/approve")
async def research_approve(cid: int, request: Request):
    ok = update_candidate_status(cid, "approved")
    payload = {"ok": ok, "id": cid, "status": "approved"}
    if _wants_html(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    return JSONResponse(payload)


@router.post("/candidates/{cid}/reject")
async def research_reject(cid: int, request: Request):
    ok = update_candidate_status(cid, "rejected")
    payload = {"ok": ok, "id": cid, "status": "rejected"}
    if _wants_html(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    return JSONResponse(payload)
