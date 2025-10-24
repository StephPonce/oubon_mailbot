from fastapi import APIRouter

router = APIRouter(prefix="/tiktok", tags=["tiktok"])

@router.get("/disabled")
def tiktok_disabled():
    return {"tiktok": "disabled", "reason": "feature not enabled yet"}
