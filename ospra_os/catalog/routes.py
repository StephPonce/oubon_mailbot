from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from ospra_os.integrations.shopify import Shopify

router = APIRouter(prefix="/catalog", tags=["catalog"])

# in-memory queue (persist later)
_CANDIDATES: dict[str, dict] = {}


class CandidateIn(BaseModel):
    id: str = Field(..., description="Your candidate UUID/string")
    title: str
    description_html: Optional[str] = ""
    vendor: Optional[str] = "Oubon"
    tags: List[str] = []
    product_type: Optional[str] = ""
    images: List[str] = []
    variants: List[dict] = []


@router.post("/ingest")
async def ingest_candidate(item: CandidateIn):
    _CANDIDATES[item.id] = item.model_dump()
    return {"ok": True, "count": len(_CANDIDATES)}


@router.get("/candidates")
async def list_candidates():
    return {"items": list(_CANDIDATES.values())}


class ApproveIn(BaseModel):
    id: str
    publish: bool = False


@router.post("/approve")
async def approve_candidate(body: ApproveIn):
    c = _CANDIDATES.get(body.id)
    if not c:
        raise HTTPException(status_code=404, detail="candidate not found")

    s = Shopify()
    created = await s.create_draft_product(
        title=c["title"],
        body_html=c.get("description_html") or "",
        vendor=c.get("vendor") or "Oubon",
        tags=c.get("tags") or [],
        product_type=c.get("product_type") or "",
        variants=c.get("variants") or None,
        images=c.get("images") or None,
    )
    product = (created or {}).get("product") or {}
    pid = product.get("id")
    if not pid:
        raise HTTPException(status_code=500, detail="failed to create product")

    if body.publish:
        await s.publish_product(pid)
        product = (await s.get_product(pid)).get("product", product)

    # remove from queue on success
    _CANDIDATES.pop(body.id, None)
    return {"ok": True, "product_id": pid, "status": product.get("status")}
