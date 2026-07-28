# Apify Response Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Apify actor responses across processes so identical questions stop costing money, and an Apify outage degrades signal instead of erasing it.

**Architecture:** A single generic cache at `ApifyClient.run_actor` — the choke point every actor call passes through. The existing live-call body is extracted to `_run_actor_live()` returning `(items, ok)`; `run_actor` becomes a cache-aware wrapper that reads fresh → calls live → writes → falls back to stale on failure. Cache logic lives in one new module (`response_cache.py`) backed by one new table (`apify_response_cache`).

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x, Alembic, pytest + pytest-asyncio, `uv` for all commands.

## Global Constraints

- Package manager is `uv`, never `pip`: `uv run pytest`, `uv run ruff check .`
- The cache must never cause the outage it prevents: every DB failure logs a warning and falls through to a live call. No exception from cache code may escape `run_actor`.
- Google Trends actor (`apify/google-trends-scraper`, env `APIFY_GOOGLE_TRENDS_ACTOR`) is TTL 0 = bypass. `trend_warm` exists to fetch *fresh* trends; caching it would feed the warm job its own previous answer forever. Comment this reason in code.
- Meta actor default is `curious_coder/facebook-ads-library-scraper`, overridable via `APIFY_META_ADS_LIBRARY_ACTOR` (note: `LIBRARY` in the name).
- Existing behavior must be preserved when `APIFY_CACHE_ENABLED=false`.
- Do not change which actors run, sub-query counts, or discovery cadence.
- Spec: `docs/superpowers/specs/2026-07-28-apify-response-cache-design.md`

---

### Task 1: Cache model and migration

**Files:**
- Create: `ospra_os/database/apify_cache_models.py`
- Create: `alembic/versions/20260728_1500_009_apify_response_cache.py`
- Test: `tests/test_apify_response_cache.py`

**Interfaces:**
- Consumes: `ospra_os.database.base.Base`
- Produces: `ApifyResponseCache` model with columns `cache_key`, `actor_id`, `run_input_summary`, `items`, `item_count`, `fetched_at`, `hit_count`, `last_hit_at`, `created_at`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_apify_response_cache.py
"""Apify response cache — key stability, TTL policy, stale-serve, failure isolation."""
from datetime import datetime, timedelta

import pytest


def test_model_roundtrips(engine):
    from ospra_os.database.base import Base
    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from sqlalchemy.orm import Session

    Base.metadata.create_all(bind=engine, tables=[ApifyResponseCache.__table__])
    with Session(engine) as s:
        s.add(ApifyResponseCache(
            cache_key="k1", actor_id="acme/actor", run_input_summary="{}",
            items=[{"a": 1}], item_count=1, fetched_at=datetime.utcnow(),
        ))
        s.commit()
        row = s.query(ApifyResponseCache).filter_by(cache_key="k1").one()
        assert row.items == [{"a": 1}]
        assert row.item_count == 1
        assert row.hit_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_apify_response_cache.py::test_model_roundtrips -v`
Expected: FAIL — `ModuleNotFoundError: ospra_os.database.apify_cache_models`

- [ ] **Step 3: Write the model**

```python
# ospra_os/database/apify_cache_models.py
"""
Apify response cache (#57 follow-up)
====================================

Persists Apify actor responses across processes so identical questions stop
costing money. Mirrors the ``cached_google_trends`` pattern: one row per
distinct question, ``fetched_at`` drives staleness.

Key insight this exists to fix: catalog_warm asked ~25 DISTINCT Meta sub-queries
~60 times a month (5 niches x 5 sub-queries x 2 runs/day) because nothing
persisted between cron processes.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from ospra_os.database.base import Base


class ApifyResponseCache(Base):
    __tablename__ = "apify_response_cache"

    id = Column(Integer, primary_key=True)

    # SHA-256 of (actor_id, canonical run_input, max_items) — the lookup.
    cache_key = Column(String(64), unique=True, nullable=False, index=True)

    # Kept separate from the hash so per-actor TTL and spend reporting can
    # filter/aggregate without decoding keys.
    actor_id = Column(String(128), nullable=False, index=True)

    # Truncated readable input so a human can eyeball a row.
    run_input_summary = Column(String(512), nullable=True)

    # Exactly what run_actor returned.
    items = Column(JSON, nullable=False)
    item_count = Column(Integer, nullable=False, default=0)

    fetched_at = Column(DateTime, nullable=False, index=True)

    # Proves the cache earns its keep.
    hit_count = Column(Integer, nullable=False, default=0)
    last_hit_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ApifyResponseCache actor={self.actor_id!r} "
            f"items={self.item_count} fetched_at={self.fetched_at}>"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_apify_response_cache.py::test_model_roundtrips -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

Read `alembic/versions/20260716_0000_007_discovery_jobs.py` first and copy its header/revision style. The new file must set `down_revision` to the revision id of migration 008 (`20260722_1200_008_purge_seeded_learning.py`) — open that file and read its `revision = "..."` value; do not guess.

```python
"""009: apify_response_cache — persist Apify actor responses across processes

Revision ID: 009_apify_response_cache
Revises: <REVISION ID READ FROM 008 FILE>
"""
import sqlalchemy as sa
from alembic import op

revision = "009_apify_response_cache"
down_revision = "<REVISION ID READ FROM 008 FILE>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "apify_response_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("run_input_summary", sa.String(512), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_apify_response_cache_cache_key", "apify_response_cache",
                    ["cache_key"], unique=True)
    op.create_index("ix_apify_response_cache_actor_id", "apify_response_cache",
                    ["actor_id"])
    op.create_index("ix_apify_response_cache_fetched_at", "apify_response_cache",
                    ["fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_apify_response_cache_fetched_at", table_name="apify_response_cache")
    op.drop_index("ix_apify_response_cache_actor_id", table_name="apify_response_cache")
    op.drop_index("ix_apify_response_cache_cache_key", table_name="apify_response_cache")
    op.drop_table("apify_response_cache")
```

- [ ] **Step 6: Verify migration imports cleanly**

Run: `uv run python -c "import importlib.util,glob; p=glob.glob('alembic/versions/*009_apify*.py')[0]; spec=importlib.util.spec_from_file_location('m',p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('revision:', m.revision, '| down_revision:', m.down_revision)"`
Expected: prints both ids; `down_revision` matches 008's `revision`

- [ ] **Step 7: Commit**

```bash
git add ospra_os/database/apify_cache_models.py alembic/versions/20260728_1500_009_apify_response_cache.py tests/test_apify_response_cache.py
git commit -m "feat(apify-cache): apify_response_cache model + migration 009"
```

---

### Task 2: The cache module

**Files:**
- Create: `ospra_os/product_research/connectors/apify/response_cache.py`
- Test: `tests/test_apify_response_cache.py` (append)

**Interfaces:**
- Consumes: `ApifyResponseCache` (Task 1)
- Produces:
  - `CACHE_MARKER = "_ospra_cache"`
  - `cache_enabled() -> bool`
  - `cache_key(actor_id: str, run_input: dict, max_items: int | None) -> str`
  - `ttl_for(actor_id: str, *, empty: bool = False) -> timedelta | None` (None = bypass)
  - `get(actor_id, run_input, max_items, *, allow_stale: bool = False) -> CacheHit | None`
  - `put(actor_id, run_input, max_items, items: list[dict]) -> None`
  - `stamp_stale(items: list[dict], fetched_at: datetime) -> list[dict]`
  - `prune(older_than_days: int | None = None) -> int`
  - `get_cache_stats() -> dict` / `reset_cache_stats() -> None`
  - `CacheHit` dataclass with `.items`, `.fetched_at`, `.is_stale`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_apify_response_cache.py

def _fresh_cache(engine):
    """Create the table and hand back the module with counters reset."""
    from ospra_os.database.base import Base
    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.product_research.connectors.apify import response_cache as rc

    Base.metadata.create_all(bind=engine, tables=[ApifyResponseCache.__table__])
    rc.reset_cache_stats()
    return rc


def test_key_ignores_dict_ordering(engine):
    rc = _fresh_cache(engine)
    a = rc.cache_key("acme/actor", {"b": 2, "a": 1}, None)
    b = rc.cache_key("acme/actor", {"a": 1, "b": 2}, None)
    assert a == b


def test_key_separates_max_items(engine):
    rc = _fresh_cache(engine)
    assert rc.cache_key("acme/actor", {"a": 1}, 25) != rc.cache_key("acme/actor", {"a": 1}, 100)


def test_put_then_get_is_a_hit(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "smart plug"}, None, [{"ad": 1}])
    hit = rc.get("acme/actor", {"q": "smart plug"}, None)
    assert hit is not None
    assert hit.items == [{"ad": 1}]
    assert hit.is_stale is False
    assert rc.get_cache_stats()["cache_hits"] == 1


def test_expired_entry_is_a_miss_but_stale_serves(engine, monkeypatch):
    from datetime import datetime, timedelta
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "old"}, None, [{"ad": 2}])

    # Age the row past its TTL.
    from sqlalchemy.orm import Session
    from ospra_os.database.apify_cache_models import ApifyResponseCache
    with Session(engine) as s:
        row = s.query(ApifyResponseCache).filter_by(
            cache_key=rc.cache_key("acme/actor", {"q": "old"}, None)).one()
        row.fetched_at = datetime.utcnow() - timedelta(hours=48)
        s.commit()

    assert rc.get("acme/actor", {"q": "old"}, None) is None
    stale = rc.get("acme/actor", {"q": "old"}, None, allow_stale=True)
    assert stale is not None and stale.is_stale is True
    assert rc.get_cache_stats()["stale_served"] == 1


def test_trends_actor_is_bypassed(engine):
    rc = _fresh_cache(engine)
    trends = "apify/google-trends-scraper"
    assert rc.ttl_for(trends) is None
    rc.put(trends, {"q": "led mask"}, None, [{"t": 1}])
    assert rc.get(trends, {"q": "led mask"}, None) is None


def test_empty_result_uses_short_ttl(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_EMPTY", "6")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    assert rc.ttl_for("acme/actor", empty=True).total_seconds() == 6 * 3600
    assert rc.ttl_for("acme/actor", empty=False).total_seconds() == 24 * 3600


def test_oversized_response_not_cached(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_MAX_BYTES", "100")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "big"}, None, [{"blob": "x" * 500}])
    assert rc.get("acme/actor", {"q": "big"}, None) is None


def test_db_failure_is_swallowed(engine, monkeypatch):
    rc = _fresh_cache(engine)

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(rc, "_session", boom)
    assert rc.get("acme/actor", {"q": "x"}, None) is None   # no exception
    rc.put("acme/actor", {"q": "x"}, None, [{"a": 1}])       # no exception


def test_disabled_by_env(engine, monkeypatch):
    monkeypatch.setenv("APIFY_CACHE_ENABLED", "false")
    rc = _fresh_cache(engine)
    rc.put("acme/actor", {"q": "off"}, None, [{"a": 1}])
    assert rc.get("acme/actor", {"q": "off"}, None) is None


def test_stamp_stale_marks_copies(engine):
    from datetime import datetime
    rc = _fresh_cache(engine)
    original = [{"ad": 1}]
    stamped = rc.stamp_stale(original, datetime(2026, 7, 1, 12, 0, 0))
    assert stamped[0][rc.CACHE_MARKER]["stale"] is True
    assert "2026-07-01" in stamped[0][rc.CACHE_MARKER]["fetched_at"]
    assert rc.CACHE_MARKER not in original[0], "must not mutate the cached list"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_apify_response_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: ...apify.response_cache`

- [ ] **Step 3: Write the module**

```python
# ospra_os/product_research/connectors/apify/response_cache.py
"""
Apify response cache — persist actor responses across processes.

Why this exists: catalog_warm re-asked ~25 DISTINCT Meta sub-queries ~60x/month
(5 niches x 5 sub-queries x 2 runs/day) because nothing survived the cron
process. That burned the $45 Apify cap three weeks into a four-week cycle, and
the cap blackout then blanked the winner-proof signal entirely.

Design rules:
  * Cache is keyed on the QUESTION (actor + canonical input + max_items), not
    on run options (memory/timeout) which do not change the answer.
  * The cache must NEVER cause the outage it prevents: every failure logs and
    returns as if the cache were empty.
  * Google Trends is BYPASSED (TTL 0). trend_warm's whole job is to fetch fresh
    trends; caching that actor would feed the warm job its own previous answer
    forever. Term-level caching already lives in `cached_google_trends`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_MARKER = "_ospra_cache"

# Per-run counters, surfaced through get_apify_budget_report().
_stats = {"cache_hits": 0, "cache_misses": 0, "stale_served": 0}


@dataclass(frozen=True)
class CacheHit:
    items: List[Dict]
    fetched_at: datetime
    is_stale: bool


def reset_cache_stats() -> None:
    _stats.update({"cache_hits": 0, "cache_misses": 0, "stale_served": 0})


def get_cache_stats() -> Dict[str, int]:
    return dict(_stats)


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes"}


def cache_enabled() -> bool:
    return _env_flag("APIFY_CACHE_ENABLED", "true")


def _session():
    """Indirection so tests can patch the session factory."""
    from ospra_os.database.connection import SessionLocal
    return SessionLocal()


def cache_key(actor_id: str, run_input: Dict, max_items: Optional[int]) -> str:
    """SHA-256 over the QUESTION. sort_keys so dict ordering can't produce two
    keys for one question; max_items included because a 25-item answer is not
    interchangeable with a 100-item one. timeout/memory deliberately excluded."""
    payload = json.dumps(
        {"actor": actor_id, "input": run_input, "max_items": max_items},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ttl_for(actor_id: str, *, empty: bool = False) -> Optional[timedelta]:
    """Hours per actor, env-overridable. None == bypass (never cache)."""
    trends_actor = os.getenv("APIFY_GOOGLE_TRENDS_ACTOR", "apify/google-trends-scraper")
    if actor_id == trends_actor:
        # BYPASS ON PURPOSE — see module docstring. Do not "fix" this.
        return None

    if empty:
        return timedelta(hours=float(os.getenv("APIFY_CACHE_TTL_HOURS_EMPTY", "6")))

    meta_actor = os.getenv(
        "APIFY_META_ADS_LIBRARY_ACTOR", "curious_coder/facebook-ads-library-scraper"
    )
    if actor_id == meta_actor:
        return timedelta(hours=float(os.getenv("APIFY_CACHE_TTL_HOURS_META", "72")))

    return timedelta(hours=float(os.getenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")))


def get(
    actor_id: str,
    run_input: Dict,
    max_items: Optional[int],
    *,
    allow_stale: bool = False,
) -> Optional[CacheHit]:
    """Fresh read by default; allow_stale=True ignores age (outage path)."""
    if not cache_enabled() or ttl_for(actor_id) is None:
        return None

    key = cache_key(actor_id, run_input, max_items)
    try:
        session = _session()
    except Exception as exc:
        logger.warning("[APIFY CACHE] session unavailable (%s) — treating as miss", exc)
        return None

    try:
        from ospra_os.database.apify_cache_models import ApifyResponseCache

        row = session.query(ApifyResponseCache).filter_by(cache_key=key).first()
        if row is None:
            _stats["cache_misses"] += 1
            return None

        items = row.items if isinstance(row.items, list) else []
        ttl = ttl_for(actor_id, empty=(row.item_count == 0))
        age = datetime.utcnow() - row.fetched_at
        fresh = ttl is not None and age < ttl

        if fresh:
            row.hit_count = (row.hit_count or 0) + 1
            row.last_hit_at = datetime.utcnow()
            session.commit()
            _stats["cache_hits"] += 1
            return CacheHit(items=items, fetched_at=row.fetched_at, is_stale=False)

        if allow_stale:
            _stats["stale_served"] += 1
            logger.warning(
                "[APIFY CACHE] serving STALE %s (age %.1fh) — live call unavailable",
                actor_id, age.total_seconds() / 3600.0,
            )
            return CacheHit(items=items, fetched_at=row.fetched_at, is_stale=True)

        _stats["cache_misses"] += 1
        return None
    except Exception as exc:
        logger.warning("[APIFY CACHE] read failed (%s) — treating as miss", exc)
        return None
    finally:
        try:
            session.close()
        except Exception:
            pass


def put(actor_id: str, run_input: Dict, max_items: Optional[int], items: List[Dict]) -> None:
    """Upsert. Never raises."""
    if not cache_enabled() or ttl_for(actor_id) is None:
        return

    payload = items if isinstance(items, list) else []
    try:
        encoded_len = len(json.dumps(payload, default=str))
    except Exception as exc:
        logger.warning("[APIFY CACHE] response not serialisable (%s) — not cached", exc)
        return

    max_bytes = int(os.getenv("APIFY_CACHE_MAX_BYTES", "2000000"))
    if encoded_len > max_bytes:
        logger.warning(
            "[APIFY CACHE] response %d bytes > %d cap — not cached (%s)",
            encoded_len, max_bytes, actor_id,
        )
        return

    key = cache_key(actor_id, run_input, max_items)
    summary = json.dumps(run_input, sort_keys=True, default=str)[:512]

    try:
        session = _session()
    except Exception as exc:
        logger.warning("[APIFY CACHE] session unavailable (%s) — not cached", exc)
        return

    try:
        from ospra_os.database.apify_cache_models import ApifyResponseCache

        row = session.query(ApifyResponseCache).filter_by(cache_key=key).first()
        now = datetime.utcnow()
        if row is None:
            session.add(ApifyResponseCache(
                cache_key=key, actor_id=actor_id, run_input_summary=summary,
                items=payload, item_count=len(payload), fetched_at=now, created_at=now,
            ))
        else:
            row.items = payload
            row.item_count = len(payload)
            row.fetched_at = now
            row.run_input_summary = summary
        session.commit()
    except Exception as exc:
        # Includes the benign concurrent-insert race: two parallel sub-queries
        # with the same key both miss, both run, both write. Worst case is one
        # duplicate actor run — never an exception reaching the caller.
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[APIFY CACHE] write failed (%s) — continuing", exc)
    finally:
        try:
            session.close()
        except Exception:
            pass


def stamp_stale(items: List[Dict], fetched_at: datetime) -> List[Dict]:
    """Copy items and mark them stale so downstream scoring can downgrade
    confidence instead of treating the signal as absent."""
    marker = {"stale": True, "fetched_at": fetched_at.isoformat()}
    stamped: List[Dict] = []
    for item in items or []:
        if isinstance(item, dict):
            copy = dict(item)
            copy[CACHE_MARKER] = marker
            stamped.append(copy)
        else:
            stamped.append(item)
    return stamped


def is_stale_payload(items: Any) -> bool:
    """True when any item carries the stale marker."""
    return any(
        isinstance(i, dict) and (i.get(CACHE_MARKER) or {}).get("stale")
        for i in (items or [])
    )


def prune(older_than_days: Optional[int] = None) -> int:
    """Delete rows older than the retention window. Returns rows deleted."""
    days = older_than_days if older_than_days is not None else int(
        os.getenv("APIFY_CACHE_PRUNE_DAYS", "30")
    )
    cutoff = datetime.utcnow() - timedelta(days=days)
    try:
        session = _session()
    except Exception as exc:
        logger.warning("[APIFY CACHE] prune skipped (%s)", exc)
        return 0
    try:
        from ospra_os.database.apify_cache_models import ApifyResponseCache

        deleted = (
            session.query(ApifyResponseCache)
            .filter(ApifyResponseCache.fetched_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return int(deleted or 0)
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            pass
        logger.warning("[APIFY CACHE] prune failed (%s)", exc)
        return 0
    finally:
        try:
            session.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_apify_response_cache.py -v`
Expected: all PASS

- [ ] **Step 5: Lint**

Run: `uv run ruff check ospra_os/product_research/connectors/apify/response_cache.py ospra_os/database/apify_cache_models.py`
Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add ospra_os/product_research/connectors/apify/response_cache.py tests/test_apify_response_cache.py
git commit -m "feat(apify-cache): response_cache module — key, TTL policy, stale-serve, prune"
```

---

### Task 3: Wire the cache into `run_actor`

**Files:**
- Modify: `ospra_os/product_research/connectors/apify/base_apify.py` (`run_actor` ~line 270-390, `get_apify_budget_report` ~line 59, `reset_apify_budget` ~line 37)
- Test: `tests/test_apify_response_cache.py` (append)

**Interfaces:**
- Consumes: `response_cache.get/put/stamp_stale/get_cache_stats/reset_cache_stats` (Task 2)
- Produces:
  - `ApifyClient._run_actor_live(actor_id, run_input, timeout_secs, memory_mbytes, max_items) -> tuple[list[dict], bool]` — the old body; `bool` is `ok` (True only when the actor SUCCEEDED, including a legitimate empty dataset)
  - `ApifyClient.run_actor(...) -> list[dict]` — unchanged signature, now cache-aware
  - `get_apify_budget_report()` gains `cache_hits`, `cache_misses`, `stale_served`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_apify_response_cache.py

@pytest.mark.asyncio
async def test_run_actor_second_call_hits_cache(engine, monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    from ospra_os.product_research.connectors.apify.base_apify import ApifyClient, reset_apify_budget

    reset_apify_budget()
    client = ApifyClient(api_token="test-token")
    calls = []

    async def fake_live(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        calls.append(actor_id)
        return [{"ad": "one"}], True

    monkeypatch.setattr(client, "_run_actor_live", fake_live)

    first = await client.run_actor("acme/actor", {"q": "smart plug"})
    second = await client.run_actor("acme/actor", {"q": "smart plug"})

    assert first == [{"ad": "one"}] and second == [{"ad": "one"}]
    assert len(calls) == 1, "second call must be served from cache"
    assert rc.get_cache_stats()["cache_hits"] == 1


@pytest.mark.asyncio
async def test_run_actor_serves_stale_when_live_fails(engine, monkeypatch):
    from datetime import datetime, timedelta
    from sqlalchemy.orm import Session
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("APIFY_CACHE_TTL_HOURS_DEFAULT", "24")
    rc = _fresh_cache(engine)
    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.product_research.connectors.apify.base_apify import ApifyClient, reset_apify_budget

    reset_apify_budget()
    rc.put("acme/actor", {"q": "quota"}, None, [{"ad": "old"}])
    with Session(engine) as s:
        row = s.query(ApifyResponseCache).filter_by(
            cache_key=rc.cache_key("acme/actor", {"q": "quota"}, None)).one()
        row.fetched_at = datetime.utcnow() - timedelta(hours=200)
        s.commit()

    client = ApifyClient(api_token="test-token")

    async def failing_live(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        return [], False   # quota 403

    monkeypatch.setattr(client, "_run_actor_live", failing_live)

    items = await client.run_actor("acme/actor", {"q": "quota"})
    assert items and items[0]["ad"] == "old"
    assert items[0][rc.CACHE_MARKER]["stale"] is True


@pytest.mark.asyncio
async def test_successful_empty_result_is_not_replaced_by_stale(engine, monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    rc = _fresh_cache(engine)
    from ospra_os.product_research.connectors.apify.base_apify import ApifyClient, reset_apify_budget

    reset_apify_budget()
    client = ApifyClient(api_token="test-token")

    async def empty_ok(actor_id, run_input, timeout_secs, memory_mbytes, max_items):
        return [], True    # actor SUCCEEDED with no rows

    monkeypatch.setattr(client, "_run_actor_live", empty_ok)
    assert await client.run_actor("acme/actor", {"q": "nothing"}) == []


@pytest.mark.asyncio
async def test_tripped_breaker_serves_stale_instead_of_empty(engine, monkeypatch):
    from datetime import datetime, timedelta
    from sqlalchemy.orm import Session
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    rc = _fresh_cache(engine)
    from ospra_os.database.apify_cache_models import ApifyResponseCache
    from ospra_os.product_research.connectors.apify import base_apify

    base_apify.reset_apify_budget()
    rc.put("acme/actor", {"q": "tripped"}, None, [{"ad": "cached"}])
    with Session(engine) as s:
        row = s.query(ApifyResponseCache).filter_by(
            cache_key=rc.cache_key("acme/actor", {"q": "tripped"}, None)).one()
        row.fetched_at = datetime.utcnow() - timedelta(hours=500)
        s.commit()

    # Trip the breaker.
    base_apify._record_apify_quota_fail("acme/actor")
    base_apify._record_apify_quota_fail("acme/actor")
    assert base_apify.apify_actor_tripped("acme/actor")

    client = base_apify.ApifyClient(api_token="test-token")
    items = await client.run_actor("acme/actor", {"q": "tripped"})
    assert items and items[0]["ad"] == "cached"
    base_apify.reset_apify_budget()


def test_budget_report_includes_cache_counters(engine):
    from ospra_os.product_research.connectors.apify.base_apify import (
        get_apify_budget_report, reset_apify_budget,
    )
    reset_apify_budget()
    report = get_apify_budget_report()
    for field in ("cache_hits", "cache_misses", "stale_served"):
        assert field in report
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_apify_response_cache.py -k "run_actor or budget_report" -v`
Expected: FAIL — `_run_actor_live` does not exist / report lacks the counters

- [ ] **Step 3: Extract the live path**

In `base_apify.py`, rename the existing `async def run_actor(...)` to
`async def _run_actor_live(...)` and change its return type to `tuple`:

- Delete the breaker early-return block from it (lines beginning
  `if apify_actor_tripped(actor_id):` through `return []`) — that moves to the
  wrapper.
- Every `return []` inside it becomes `return [], False`.
- The success line `return results` becomes `return results, True`.
- Update its docstring first line to: `"""Live actor run. Returns (items, ok); ok=False means the run did not succeed."""`

- [ ] **Step 4: Add the cache-aware wrapper**

Insert directly above `_run_actor_live`:

```python
    async def run_actor(
        self,
        actor_id: str,
        run_input: Dict,
        timeout_secs: int = 300,
        memory_mbytes: int = 512,
        max_items: Optional[int] = None,
    ) -> List[Dict]:
        """Run an Apify actor, served from the response cache when possible.

        Cache policy lives in response_cache (per-actor TTL, trends bypassed).
        On any live failure we fall back to an expired entry rather than
        returning nothing — a stale winner-proof signal beats no signal, and
        the items carry a marker so scoring can downgrade confidence.
        """
        from ospra_os.product_research.connectors.apify import response_cache

        hit = response_cache.get(actor_id, run_input, max_items)
        if hit is not None:
            age_h = (datetime.now() - hit.fetched_at).total_seconds() / 3600.0
            print(f"[APIFY CACHE] hit {actor_id} ({len(hit.items)} items, age {age_h:.1f}h)")
            return hit.items

        if apify_actor_tripped(actor_id):
            stale = response_cache.get(actor_id, run_input, max_items, allow_stale=True)
            if stale is not None:
                print(f"[APIFY BREAKER] {actor_id} tripped — serving stale cache")
                return response_cache.stamp_stale(stale.items, stale.fetched_at)
            print(f"[APIFY BREAKER] skipping {actor_id} (tripped this run)")
            return []

        items, ok = await self._run_actor_live(
            actor_id, run_input, timeout_secs, memory_mbytes, max_items
        )
        if ok:
            response_cache.put(actor_id, run_input, max_items, items)
            return items

        stale = response_cache.get(actor_id, run_input, max_items, allow_stale=True)
        if stale is not None:
            return response_cache.stamp_stale(stale.items, stale.fetched_at)
        return items
```

Verify `datetime` is imported at module top in `base_apify.py`; if not, add
`from datetime import datetime`.

- [ ] **Step 5: Extend the budget report and reset**

Replace `get_apify_budget_report` and add the reset hook:

```python
def reset_apify_budget() -> None:
    """Reset per-run Apify counters (call at the start of a cron run)."""
    _apify_run_state["starts"] = 0
    _apify_run_state["fails_by_actor"] = {}
    _apify_run_state["tripped"] = set()
    try:
        from ospra_os.product_research.connectors.apify import response_cache
        response_cache.reset_cache_stats()
    except Exception:
        pass


def get_apify_budget_report() -> Dict:
    """Per-run spend proxy: actor-start count drives metered cost. Cache
    counters show how many starts the response cache avoided."""
    report = {
        "actor_starts": _apify_run_state["starts"],
        "quota_failures": dict(_apify_run_state["fails_by_actor"]),
        "tripped_actors": sorted(_apify_run_state["tripped"]),
    }
    try:
        from ospra_os.product_research.connectors.apify import response_cache
        report.update(response_cache.get_cache_stats())
    except Exception:
        report.update({"cache_hits": 0, "cache_misses": 0, "stale_served": 0})
    return report
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_apify_response_cache.py -v`
Expected: all PASS

- [ ] **Step 7: Verify no other caller broke**

Run: `uv run pytest -k "apify" -v`
Expected: PASS (no caller depends on `run_actor` returning a tuple)

- [ ] **Step 8: Commit**

```bash
git add ospra_os/product_research/connectors/apify/base_apify.py tests/test_apify_response_cache.py
git commit -m "feat(apify-cache): cache-aware run_actor + stale fallback on live failure"
```

---

### Task 4: Propagate staleness into confidence scoring

**Files:**
- Modify: `ospra_os/product_research/connectors/apify/meta_ads_library.py` (success return ~line 400)
- Modify: `ospra_os/intelligence/product_discovery.py` (`_meta_winners_cache` ~line 2995, scoring stamp ~line 5796, `_compute_saturation` ~line 426)
- Test: `tests/test_apify_response_cache.py` (append)

**Interfaces:**
- Consumes: `response_cache.is_stale_payload`, `CACHE_MARKER` (Task 2)
- Produces:
  - `search_active_ads()` result dict gains `"stale": bool`
  - `_meta_winners_cache` gains `"stale": bool`
  - product dict gains `meta_niche_stale: bool`
  - `_compute_saturation` weights a stale Meta signal at 0.125 instead of 0.25

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_apify_response_cache.py

def test_saturation_halves_weight_for_stale_meta():
    from ospra_os.intelligence.product_discovery import _compute_saturation

    fresh = _compute_saturation({"meta_niche_advertiser_count": 10})
    stale = _compute_saturation({"meta_niche_advertiser_count": 10, "meta_niche_stale": True})
    none_ = _compute_saturation({})

    # Same underlying reading, so the score is unchanged...
    assert stale["score"] == fresh["score"]
    # ...but confidence sits strictly between fresh signal and no signal.
    assert none_["confidence"] < stale["confidence"] < fresh["confidence"]
    assert stale["confidence"] == pytest.approx(0.125)
    assert fresh["confidence"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_meta_connector_propagates_stale_flag(monkeypatch):
    from ospra_os.product_research.connectors.apify.meta_ads_library import MetaAdsLibrary
    from ospra_os.product_research.connectors.apify.response_cache import CACHE_MARKER

    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    scraper = MetaAdsLibrary(api_token="test-token")

    stale_raw = {
        "ad_archive_id": "1", "page_id": "p1", "page_name": "Acme",
        "body": "buy now", CACHE_MARKER: {"stale": True, "fetched_at": "2026-07-01T00:00:00"},
    }

    async def fake_run_actor(**kwargs):
        return [stale_raw]

    monkeypatch.setattr(scraper.client, "run_actor", fake_run_actor)
    result = await scraper.search_active_ads(keyword="smart plug")
    assert result["available"] is True
    assert result["stale"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_apify_response_cache.py -k "stale_meta or propagates_stale" -v`
Expected: FAIL — `KeyError: 'stale'` and confidence assertion fails

- [ ] **Step 3: Flag staleness in the Meta connector**

In `meta_ads_library.py`, immediately after the `results = await self.client.run_actor(...)` / `except` block and before `if not results:`, add:

```python
        from ospra_os.product_research.connectors.apify.response_cache import (
            is_stale_payload,
        )

        served_stale = is_stale_payload(results)
```

Then add `"stale": served_stale,` to the success return dict (the one containing
`"available": True`), placed just after `"ad_count": len(ads),`.

- [ ] **Step 4: Carry it through discovery**

In `product_discovery.py`, in `_fetch_meta_ads_trends`, immediately before the
`self._meta_winners_cache = {` assignment, add:

```python
        served_stale = any(
            isinstance(r, dict) and r.get('stale') for r in results
        )
```

and add `'stale': served_stale,` to that dict, right after `'ad_count': total_ad_count,`.

Then in the scoring loop, after the existing line
`meta_niche_advertiser_count = len(meta_cache.get("advertisers") or [])`, add:

```python
        meta_niche_stale = bool(meta_cache.get("stale"))
        if meta_niche_stale and meta_niche_advertiser_count > 0:
            logger.warning(
                "[meta-saturation] advertiser count came from STALE cache — "
                "saturation signal will carry reduced confidence"
            )
```

and inside the `for product in products:` loop, directly after
`product['meta_niche_advertiser_count'] = meta_niche_advertiser_count`, add:

```python
                if meta_niche_stale:
                    product['meta_niche_stale'] = True
```

- [ ] **Step 5: Halve the weight in `_compute_saturation`**

In `_compute_saturation`, replace the two lines
`weighted_sum += sat * 0.25` / `weight_total += 0.25` in the Meta block with:

```python
        # A STALE Meta reading (served from cache during an Apify outage) still
        # tells us the shape of the market — it just tells us about last week.
        # Half weight: the score keeps using it, but confidence lands between
        # "fresh signal" and "no signal at all".
        meta_weight = 0.125 if product.get('meta_niche_stale') else 0.25
        signals['meta_advertiser_density_stale'] = bool(product.get('meta_niche_stale'))
        weighted_sum += sat * meta_weight
        weight_total += meta_weight
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_apify_response_cache.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add ospra_os/product_research/connectors/apify/meta_ads_library.py ospra_os/intelligence/product_discovery.py tests/test_apify_response_cache.py
git commit -m "feat(apify-cache): stale Meta signal scores at half weight, not zero"
```

---

### Task 5: Cron integration — prune and report

**Files:**
- Modify: `ospra_os/tasks/catalog_warm.py` (`_bootstrap_table`, the `[APIFY SPEND]` log line ~line 377)
- Test: `tests/test_apify_response_cache.py` (append)

**Interfaces:**
- Consumes: `response_cache.prune` (Task 2), `ApifyResponseCache` (Task 1)
- Produces: cache table bootstrapped by the cron; prune-on-run; cache counters in the `[APIFY SPEND]` line

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_apify_response_cache.py

def test_prune_deletes_only_old_rows(engine):
    from datetime import datetime, timedelta
    from sqlalchemy.orm import Session
    from ospra_os.database.apify_cache_models import ApifyResponseCache

    rc = _fresh_cache(engine)
    with Session(engine) as s:
        s.query(ApifyResponseCache).delete()
        s.add(ApifyResponseCache(
            cache_key="old", actor_id="a", items=[], item_count=0,
            fetched_at=datetime.utcnow() - timedelta(days=90),
        ))
        s.add(ApifyResponseCache(
            cache_key="new", actor_id="a", items=[], item_count=0,
            fetched_at=datetime.utcnow(),
        ))
        s.commit()

    assert rc.prune(older_than_days=30) == 1
    with Session(engine) as s:
        remaining = [r.cache_key for r in s.query(ApifyResponseCache).all()]
    assert remaining == ["new"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_apify_response_cache.py::test_prune_deletes_only_old_rows -v`
Expected: PASS already if Task 2 is done — if so, keep it as a regression test and continue.

- [ ] **Step 3: Bootstrap the table in the cron**

In `catalog_warm.py` `_bootstrap_table()`, add the import and include the table:

```python
    from ospra_os.database.apify_cache_models import ApifyResponseCache
```

and extend the `tables=[...]` list to
`tables=[DiscoveredProduct.__table__, ProductTimeseries.__table__, ApifyResponseCache.__table__]`.

- [ ] **Step 4: Prune at run start**

In `run()`, immediately after the `reset_apify_budget()` call, add:

```python
    try:
        from ospra_os.product_research.connectors.apify.response_cache import prune
        pruned = prune()
        if pruned:
            logger.info(f"[APIFY CACHE] pruned {pruned} expired rows")
    except Exception as e:
        logger.warning(f"[APIFY CACHE] prune skipped: {e}")
```

- [ ] **Step 5: Report cache savings**

Extend the existing `[APIFY SPEND]` logger.info f-string with:

```python
            f"cache_hits={apify_report.get('cache_hits', 0)} "
            f"stale_served={apify_report.get('stale_served', 0)} "
```

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -q`
Expected: no NEW failures (pre-existing failures documented in CLAUDE.md — bcrypt in `test_security.py`, missing `groq` in `test_differentiation.py`, sqlalchemy fixtures in `test_actions_routes.py` — remain acceptable)

- [ ] **Step 7: Lint everything touched**

Run: `uv run ruff check ospra_os/ tests/test_apify_response_cache.py`
Expected: no NEW errors

- [ ] **Step 8: Commit**

```bash
git add ospra_os/tasks/catalog_warm.py tests/test_apify_response_cache.py
git commit -m "feat(apify-cache): cron bootstrap + prune + cache counters in APIFY SPEND"
```

---

## Verification in production

After deploy, one `catalog_warm` run should show:

- `[APIFY CACHE] hit` lines for repeated sub-queries
- `actor_starts` falling from ~25/run toward ~0-5 once the cache is warm
- `cache_hits=` non-zero in the `[APIFY SPEND]` line
- `data_sources.meta_ads` still populated on products

Rollback: set `APIFY_CACHE_ENABLED=false` on the service — reads and writes stop
immediately, no deploy needed.

## Self-review notes

- Spec coverage: cache layer (T2/T3), key design (T2), schema (T1), TTL policy
  incl. trends bypass and empty-TTL (T2), stale-serve incl. tripped breaker (T3),
  stale marking + half-weight confidence (T4), error handling (T2, tested),
  size guard (T2), retention/prune (T2+T5), observability (T3+T5), migration
  (T1), all 12 spec tests mapped.
- Non-goal respected: no daily spend pacing in this plan.
