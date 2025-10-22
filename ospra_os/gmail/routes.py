from __future__ import annotations

from fastapi import APIRouter

from ospra_os.core.settings import get_settings

from .worker import get_worker

router = APIRouter(prefix="/gmail", tags=["Gmail"])

_settings = get_settings()
_worker = get_worker(_settings)


@router.get("/worker/status")
async def status():
    return _worker.status()


@router.post("/worker/start")
async def start():
    await _worker.start()
    return _worker.status()


@router.post("/worker/stop")
async def stop():
    await _worker.stop()
    return _worker.status()


@router.post("/worker/run-once")
async def run_once():
    await _worker.run_once()
    return _worker.status()
