"""
Discovery-reliability step 2 (fail-if-reverted): job+poll for the cold path.

(1) same-niche POST while a job is live returns the existing job — the
    refresh-spam cost guard; (2) an orphaned running job reports error via
    GET; (3) job completion upserts into discovered_catalog (the catalog is
    the single source of truth — no second results store).
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-jobs")

from ospra_os.database.discovery_jobs import DONE, ERROR, QUEUED, RUNNING, DiscoveryJob


@pytest.fixture
def jobs_db(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from ospra_os.database.base import Base
    from ospra_os.database.discovered_catalog import DiscoveredProduct
    from ospra_os.database.product_timeseries import ProductTimeseries

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=[
        DiscoveryJob.__table__, DiscoveredProduct.__table__, ProductTimeseries.__table__,
    ])
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        "ospra_os.database.connection.SessionLocal", factory, raising=False
    )
    return factory


class _NoopBackground:
    def __init__(self):
        self.tasks = []

    def add_task(self, fn, *a, **k):
        self.tasks.append((fn, a, k))


class TestJobIdempotency:
    def test_same_niche_post_joins_existing_run(self, jobs_db):
        """THE cost guard: refresh-spam must not stack discovery runs."""
        from ospra_os.intelligence.unified_discovery_routes import (
            DiscoveryJobRequest, create_discovery_job,
        )

        bg1, bg2 = _NoopBackground(), _NoopBackground()
        first = asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="smart_home", count=20), bg1, None
        ))
        second = asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="smart_home", count=20), bg2, None
        ))

        assert first["joined_existing"] is False
        assert second["joined_existing"] is True
        assert second["job"]["id"] == first["job"]["id"]
        assert len(bg1.tasks) == 1
        assert len(bg2.tasks) == 0          # no second run scheduled

        # a DIFFERENT niche is not blocked
        third = asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="kitchen", count=20), _NoopBackground(), None
        ))
        assert third["joined_existing"] is False


class TestOrphanRecovery:
    def test_stale_running_job_reports_error(self, jobs_db):
        from ospra_os.intelligence.unified_discovery_routes import get_discovery_job

        s = jobs_db()
        job = DiscoveryJob(
            niche="smart_home", count=20, status=RUNNING,
            started_at=datetime.utcnow() - timedelta(minutes=15),
            created_at=datetime.utcnow() - timedelta(minutes=16),
        )
        s.add(job)
        s.commit()
        job_id = job.id
        s.close()

        res = asyncio.run(get_discovery_job(job_id))
        assert res["job"]["status"] == ERROR
        assert "orphaned" in res["job"]["error"].lower()

    def test_recent_running_job_still_running(self, jobs_db):
        from ospra_os.intelligence.unified_discovery_routes import get_discovery_job

        s = jobs_db()
        job = DiscoveryJob(
            niche="smart_home", count=20, status=RUNNING,
            started_at=datetime.utcnow() - timedelta(minutes=2),
            created_at=datetime.utcnow(),
        )
        s.add(job)
        s.commit()
        job_id = job.id
        s.close()

        res = asyncio.run(get_discovery_job(job_id))
        assert res["job"]["status"] == RUNNING


class TestJobRunner:
    def _make_job(self, jobs_db, niche="smart_home"):
        s = jobs_db()
        job = DiscoveryJob(niche=niche, count=5, status=QUEUED,
                           created_at=datetime.utcnow())
        s.add(job)
        s.commit()
        jid = job.id
        s.close()
        return jid

    def test_completion_upserts_into_discovered_catalog(self, jobs_db, monkeypatch):
        """The job writes to the SAME catalog the page reads — no second store."""
        from ospra_os.database.discovered_catalog import DiscoveredProduct
        from ospra_os.intelligence.unified_discovery_routes import _run_discovery_job

        async def fake_discover(niche, count=20, include_captions=True, **kw):
            return [{
                "title": f"Real Product {i}", "product_id": f"jp{i}",
                "oi_score": 70 + i, "image_url": "https://cdn/x.jpg",
            } for i in range(3)]

        import ospra_os.intelligence.product_discovery as pd
        monkeypatch.setattr(pd, "discover_products", fake_discover)

        jid = self._make_job(jobs_db)
        asyncio.run(_run_discovery_job(jid))

        s = jobs_db()
        job = s.query(DiscoveryJob).filter_by(id=jid).first()
        assert job.status == DONE
        assert job.result_count == 3
        assert job.finished_at is not None
        rows = s.query(DiscoveredProduct).filter_by(niche="smart_home").all()
        assert {r.title for r in rows} == {"Real Product 0", "Real Product 1", "Real Product 2"}
        s.close()

    def test_zero_products_is_an_error_not_empty_success(self, jobs_db, monkeypatch):
        from ospra_os.intelligence.unified_discovery_routes import _run_discovery_job

        async def fake_discover(niche, count=20, include_captions=True, **kw):
            return []

        import ospra_os.intelligence.product_discovery as pd
        monkeypatch.setattr(pd, "discover_products", fake_discover)

        jid = self._make_job(jobs_db)
        asyncio.run(_run_discovery_job(jid))

        s = jobs_db()
        job = s.query(DiscoveryJob).filter_by(id=jid).first()
        assert job.status == ERROR
        assert "no products" in job.error_text.lower()
        s.close()

    def test_crash_lands_in_error_text(self, jobs_db, monkeypatch):
        from ospra_os.intelligence.unified_discovery_routes import _run_discovery_job

        async def fake_discover(niche, count=20, include_captions=True, **kw):
            raise RuntimeError("supplier exploded")

        import ospra_os.intelligence.product_discovery as pd
        monkeypatch.setattr(pd, "discover_products", fake_discover)

        jid = self._make_job(jobs_db)
        asyncio.run(_run_discovery_job(jid))

        s = jobs_db()
        job = s.query(DiscoveryJob).filter_by(id=jid).first()
        assert job.status == ERROR
        assert "supplier exploded" in job.error_text
        s.close()


class TestOrphanHardening:
    """Deploy-restart corpses must never brick a niche (post-#9 hardening).

    The original orphan check only covered status=running — a job killed
    while QUEUED (restart in the window between the POST's commit and the
    BackgroundTask starting) matched the POST's queued/running lookup
    forever: every user joined a corpse that would never run.
    """

    def test_stuck_queued_corpse_is_reaped_and_unbricks_the_niche(self, jobs_db):
        from ospra_os.intelligence.unified_discovery_routes import (
            DiscoveryJobRequest, create_discovery_job, get_discovery_job,
        )

        s = jobs_db()
        s.add(DiscoveryJob(
            niche="smart_home", count=20, status=QUEUED,
            created_at=datetime.utcnow() - timedelta(minutes=12),
        ))
        s.commit()
        corpse_id = s.query(DiscoveryJob).first().id
        s.close()

        bg = _NoopBackground()
        res = asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="smart_home", count=20), bg, None
        ))
        # NOT handed the corpse — a fresh job was created and scheduled.
        assert res["joined_existing"] is False
        assert res["job"]["id"] != corpse_id
        assert len(bg.tasks) == 1

        # The corpse itself now reads as a terminal error.
        corpse = asyncio.run(get_discovery_job(corpse_id))
        assert corpse["job"]["status"] == ERROR
        assert "orphaned" in corpse["job"]["error"]

    def test_stuck_queued_corpse_reaped_via_get_too(self, jobs_db):
        from ospra_os.intelligence.unified_discovery_routes import get_discovery_job

        s = jobs_db()
        s.add(DiscoveryJob(
            niche="smart_home", count=20, status=QUEUED,
            created_at=datetime.utcnow() - timedelta(minutes=12),
        ))
        s.commit()
        job_id = s.query(DiscoveryJob).first().id
        s.close()

        res = asyncio.run(get_discovery_job(job_id))
        assert res["job"]["status"] == ERROR

    def test_fresh_queued_job_is_joined_not_reaped(self, jobs_db):
        from ospra_os.intelligence.unified_discovery_routes import (
            DiscoveryJobRequest, create_discovery_job,
        )

        s = jobs_db()
        s.add(DiscoveryJob(
            niche="smart_home", count=20, status=QUEUED,
            created_at=datetime.utcnow(),
        ))
        s.commit()
        live_id = s.query(DiscoveryJob).first().id
        s.close()

        bg = _NoopBackground()
        res = asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="smart_home", count=20), bg, None
        ))
        assert res["joined_existing"] is True
        assert res["job"]["id"] == live_id
        assert len(bg.tasks) == 0

    def test_running_orphan_reaped_on_post_as_well(self, jobs_db):
        from ospra_os.intelligence.unified_discovery_routes import (
            DiscoveryJobRequest, create_discovery_job,
        )

        s = jobs_db()
        s.add(DiscoveryJob(
            niche="smart_home", count=20, status=RUNNING,
            created_at=datetime.utcnow() - timedelta(minutes=15),
            started_at=datetime.utcnow() - timedelta(minutes=14),
        ))
        s.commit()
        s.close()

        bg = _NoopBackground()
        res = asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="smart_home", count=20), bg, None
        ))
        assert res["joined_existing"] is False
        assert len(bg.tasks) == 1


class TestRunnerContracts:
    def test_user_job_skips_absence_pass(self, jobs_db, monkeypatch):
        """A tier-clamped user job is not a full sweep — the runner must call
        warm_niche with include_absences=False so small pools can't write
        false 'gone' timeseries rows for everything they didn't include."""
        from ospra_os.intelligence import unified_discovery_routes as udr
        from ospra_os.tasks import catalog_warm as cw

        calls = []

        async def fake_warm(niche, count=None, include_absences=True):
            calls.append({"niche": niche, "count": count,
                          "include_absences": include_absences})
            return {"niche": niche, "discovered": 3, "new": 3, "seen": 0}

        monkeypatch.setattr(cw, "warm_niche", fake_warm)

        s = jobs_db()
        s.add(DiscoveryJob(niche="smart_home", count=10, status=QUEUED,
                           created_at=datetime.utcnow()))
        s.commit()
        job_id = s.query(DiscoveryJob).first().id
        s.close()

        asyncio.run(udr._run_discovery_job(job_id))

        assert calls and calls[0]["include_absences"] is False
        s = jobs_db()
        assert s.query(DiscoveryJob).first().status == DONE

    def test_requested_by_is_populated_from_user_id(self, jobs_db):
        """TokenPayload has user_id, not .sub — the column was silently NULL
        for every authenticated caller."""
        from types import SimpleNamespace

        from ospra_os.intelligence.unified_discovery_routes import (
            DiscoveryJobRequest, create_discovery_job,
        )

        caller = SimpleNamespace(user_id=42, tier="soar")
        asyncio.run(create_discovery_job(
            DiscoveryJobRequest(niche="smart_home", count=20),
            _NoopBackground(), caller,
        ))

        s = jobs_db()
        assert s.query(DiscoveryJob).first().requested_by == "42"
