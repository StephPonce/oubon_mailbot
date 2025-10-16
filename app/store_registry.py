"""
Lightweight store registry to support multi-niche Shopify configurations.

Persists metadata to data/stores.json while keeping sensitive tokens on disk only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


_STORE_REGISTRY_PATH = Path("data/stores.json")


def set_registry_path(path: Path) -> None:
    """
    Override registry path (primarily for tests).
    """
    global _STORE_REGISTRY_PATH
    _STORE_REGISTRY_PATH = path


def _load_registry() -> List[Dict[str, str]]:
    if not _STORE_REGISTRY_PATH.exists():
        return []
    try:
        return json.loads(_STORE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _write_registry(entries: List[Dict[str, str]]) -> None:
    _STORE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_REGISTRY_PATH.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")


class StoreCreate(BaseModel):
    store_domain: str = Field(..., min_length=3, description="Shopify store domain (e.g. example.myshopify.com)")
    niche: str = Field(..., min_length=2, description="Primary niche label (e.g. baby, home)")
    shopify_token: str = Field(..., min_length=10, description="Private Admin API access token for the store")
    template_pack: str = Field(..., min_length=2, description="Template pack identifier to avoid branding dilution")
    brand_name: Optional[str] = Field(None, description="Friendly brand label for internal dashboards")

    @field_validator("store_domain")
    def _normalize_domain(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("niche", "template_pack", mode="before")
    def _strip_strings(cls, value: str) -> str:
        return value.strip()


class StorePublic(BaseModel):
    id: str
    store_domain: str
    niche: str
    template_pack: str
    brand_name: Optional[str]
    created_at: datetime
    has_token: bool = True


def add_store(payload: StoreCreate) -> StorePublic:
    """
    Persist a new store entry and return a safe representation omitting the raw token.
    """
    entries = _load_registry()
    domain = payload.store_domain.lower()
    for entry in entries:
        if entry.get("store_domain", "").lower() == domain:
            raise ValueError(f"Store '{payload.store_domain}' already registered.")

    record = {
        "id": str(uuid4()),
        "store_domain": payload.store_domain,
        "niche": payload.niche,
        "shopify_token": payload.shopify_token,
        "template_pack": payload.template_pack,
        "brand_name": payload.brand_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(record)
    _write_registry(entries)

    return StorePublic(
        id=record["id"],
        store_domain=record["store_domain"],
        niche=record["niche"],
        template_pack=record["template_pack"],
        brand_name=record["brand_name"],
        created_at=datetime.fromisoformat(record["created_at"]),
        has_token=bool(record["shopify_token"]),
    )


def list_stores() -> List[StorePublic]:
    """
    Return sanitized entries for presentation layers.
    """
    entries = _load_registry()
    public_entries: List[StorePublic] = []
    for entry in entries:
        try:
            created_at = datetime.fromisoformat(entry.get("created_at")) if entry.get("created_at") else None
        except ValueError:
            created_at = None
        public_entries.append(
            StorePublic(
                id=entry.get("id", ""),
                store_domain=entry.get("store_domain", ""),
                niche=entry.get("niche", ""),
                template_pack=entry.get("template_pack", ""),
                brand_name=entry.get("brand_name"),
                created_at=created_at or datetime.fromtimestamp(0, tz=timezone.utc),
                has_token=bool(entry.get("shopify_token")),
            )
        )
    return public_entries


__all__ = ["StoreCreate", "StorePublic", "add_store", "list_stores", "set_registry_path"]
