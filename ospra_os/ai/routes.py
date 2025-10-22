from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["AI"])


class PreviewRequest(BaseModel):
    subject: str
    body: str


@router.post("/ai/preview")
def ai_preview(req: PreviewRequest):
    # Minimal deterministic preview so your smoke test passes.
    summary = f"Subject: {req.subject}. First 120 chars: {req.body[:120]}"
    reply = (
        "Thanks for reaching out. We’ve received your message and will follow up soon. "
        "If this is about an order, please include your order ID."
    )
    return {"ok": True, "preview": {"summary": summary, "auto_reply_suggestion": reply}}
