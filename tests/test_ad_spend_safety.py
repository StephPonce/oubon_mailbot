"""
Ad-spend safety regression tests (Section B band 1: T21-T25).

The optimizer previously applied budget*1.20 every 6 hours with no ceiling
(compounding ≈ +107%/day), never wrote to the platform (T22 TODO), lost all
campaign tracking on restart (T23), had no kill switch (T24), and Google
created ad groups/ads ENABLED under the paused campaign (T25). Every test
here fails if its guard is reverted.
"""

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-ad-safety")

from ospra_os.advertising.scheduler import AdScheduler, MIN_DAILY_BUDGET


def make_settings(**overrides):
    base = dict(
        ADS_AUTOMATION_ENABLED=True,
        ADS_MAX_DAILY_BUDGET=100.0,
        ADS_MAX_ACCOUNT_DAILY_BUDGET=500.0,
        ADS_BUDGET_INCREASE_COOLDOWN_HOURS=24,
        ADS_KILL_SWITCH=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def scheduler(monkeypatch):
    """AdScheduler with no real platform managers and no real DB."""
    sched = AdScheduler.__new__(AdScheduler)
    sched.scheduler = MagicMock()
    sched.settings = make_settings()
    sched.meta_manager = None
    sched.tiktok_manager = None
    sched.google_manager = None
    sched.creative_generator = None
    sched.active_campaigns = {}

    # Record persistence calls instead of hitting the DB.
    sched._persisted = []
    monkeypatch.setattr(sched, "_persist_campaign", lambda key: sched._persisted.append(key))

    # Record platform budget writes; default: platform accepts.
    sched._budget_writes = []

    async def fake_update(platform, campaign_id, daily_budget):
        sched._budget_writes.append((platform, campaign_id, daily_budget))
        return True

    monkeypatch.setattr(sched, "_update_campaign_budget", fake_update)
    return sched


def add_campaign(sched, key="meta_c1", budget=50.0, budget_limit=None, status="active", **extra):
    platform, campaign_id = key.split("_", 1)
    sched.active_campaigns[key] = {
        "user_id": 1,
        "product_id": 1,
        "platform": platform,
        "campaign_id": campaign_id,
        "daily_budget": budget,
        "budget_limit": budget_limit,
        "status": status,
        "created_at": datetime.now(timezone.utc),
        **extra,
    }
    return sched.active_campaigns[key]


def set_metrics(monkeypatch, sched, ctr=0.05, spend=0.0):
    async def fake_metrics(platform, campaign_id):
        return {"ctr": ctr, "spend": spend}

    monkeypatch.setattr(sched, "_get_campaign_metrics", fake_metrics)


# ---------------------------------------------------------------------------
# T21 — caps and throttles
# ---------------------------------------------------------------------------

class TestT21BudgetCaps:
    @pytest.mark.asyncio
    async def test_increase_capped_by_campaign_budget_limit(self, scheduler, monkeypatch):
        """budget_limit (the DB column) is a hard per-campaign cap."""
        c = add_campaign(scheduler, budget=50.0, budget_limit=55.0)
        set_metrics(monkeypatch, scheduler, ctr=0.05)  # high CTR → wants 60.0

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == 55.0  # not 60.0

    @pytest.mark.asyncio
    async def test_increase_capped_by_global_max(self, scheduler, monkeypatch):
        c = add_campaign(scheduler, budget=95.0)  # wants 114.0
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == scheduler.settings.ADS_MAX_DAILY_BUDGET

    @pytest.mark.asyncio
    async def test_compounding_is_throttled_to_one_increase_per_cooldown(self, scheduler, monkeypatch):
        """The 6-hourly job may only raise a campaign once per cooldown window.
        Without the throttle 4 runs would compound 50 → 103.68."""
        c = add_campaign(scheduler, budget=50.0)
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        for _ in range(4):  # a day's worth of 6-hourly runs
            await scheduler.optimize_budgets()

        assert c["daily_budget"] == pytest.approx(60.0)  # exactly one +20%

    @pytest.mark.asyncio
    async def test_increase_allowed_again_after_cooldown(self, scheduler, monkeypatch):
        c = add_campaign(scheduler, budget=50.0)
        c["last_budget_increase_at"] = datetime.now(timezone.utc) - timedelta(hours=25)
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == pytest.approx(60.0)

    @pytest.mark.asyncio
    async def test_account_wide_cap_blocks_increase(self, scheduler, monkeypatch):
        """Sum of active daily budgets may not exceed ADS_MAX_ACCOUNT_DAILY_BUDGET."""
        scheduler.settings = make_settings(ADS_MAX_ACCOUNT_DAILY_BUDGET=120.0)
        c1 = add_campaign(scheduler, key="meta_c1", budget=60.0)
        add_campaign(scheduler, key="tiktok_c2", budget=60.0)  # account fully committed
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        await scheduler.optimize_budgets()

        assert c1["daily_budget"] == 60.0  # no headroom → no increase
        assert scheduler._budget_writes == []

    @pytest.mark.asyncio
    async def test_decrease_floors_at_min_budget(self, scheduler, monkeypatch):
        c = add_campaign(scheduler, budget=1.1)
        set_metrics(monkeypatch, scheduler, ctr=0.001, spend=5.0)  # low CTR

        await scheduler.optimize_budgets()

        assert c["daily_budget"] >= MIN_DAILY_BUDGET


# ---------------------------------------------------------------------------
# T22 — the value sent to the platform is the capped one; fail-closed
# ---------------------------------------------------------------------------

class TestT22PlatformWrite:
    @pytest.mark.asyncio
    async def test_platform_receives_capped_value(self, scheduler, monkeypatch):
        add_campaign(scheduler, budget=95.0)  # uncapped would be 114.0
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        await scheduler.optimize_budgets()

        assert len(scheduler._budget_writes) == 1
        _, _, sent = scheduler._budget_writes[0]
        assert sent == scheduler.settings.ADS_MAX_DAILY_BUDGET  # capped, not 114.0

    @pytest.mark.asyncio
    async def test_state_unchanged_when_platform_rejects(self, scheduler, monkeypatch):
        """If the platform write fails, local + DB budget must NOT change —
        otherwise tracking drifts from real spend settings."""
        c = add_campaign(scheduler, budget=50.0)
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        async def rejecting_update(platform, campaign_id, daily_budget):
            return False

        monkeypatch.setattr(scheduler, "_update_campaign_budget", rejecting_update)

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == 50.0
        assert scheduler._persisted == []


# ---------------------------------------------------------------------------
# Automation gate — increases require ADS_AUTOMATION_ENABLED
# ---------------------------------------------------------------------------

class TestAutomationGate:
    @pytest.mark.asyncio
    async def test_no_increase_when_automation_disabled(self, scheduler, monkeypatch):
        scheduler.settings = make_settings(ADS_AUTOMATION_ENABLED=False)
        c = add_campaign(scheduler, budget=50.0)
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == 50.0
        assert scheduler._budget_writes == []

    @pytest.mark.asyncio
    async def test_protective_decrease_still_applies_when_automation_disabled(self, scheduler, monkeypatch):
        scheduler.settings = make_settings(ADS_AUTOMATION_ENABLED=False)
        c = add_campaign(scheduler, budget=50.0)
        set_metrics(monkeypatch, scheduler, ctr=0.001, spend=30.0)

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# T24 — kill switch
# ---------------------------------------------------------------------------

class TestT24KillSwitch:
    @pytest.mark.asyncio
    async def test_kill_switch_stops_optimization(self, scheduler, monkeypatch):
        scheduler.settings = make_settings(ADS_KILL_SWITCH=True)
        c = add_campaign(scheduler, budget=50.0)
        set_metrics(monkeypatch, scheduler, ctr=0.05)

        await scheduler.optimize_budgets()

        assert c["daily_budget"] == 50.0

    @pytest.mark.asyncio
    async def test_kill_switch_refuses_activation(self, scheduler):
        scheduler.settings = make_settings(ADS_KILL_SWITCH=True)
        add_campaign(scheduler, status="paused")

        assert await scheduler.activate_campaign("meta", "c1") is False

    @pytest.mark.asyncio
    async def test_kill_switch_refuses_creation(self, scheduler):
        scheduler.settings = make_settings(ADS_KILL_SWITCH=True)

        result = await scheduler.create_multi_platform_campaign(
            product_id=1, product_name="x", product_description="d",
            product_url="https://example.com",
        )

        assert result["status"] == "refused_kill_switch"
        assert result["campaigns"] == {}

    @pytest.mark.asyncio
    async def test_pause_all_pauses_every_active_campaign(self, scheduler, monkeypatch):
        c1 = add_campaign(scheduler, key="meta_c1")
        c2 = add_campaign(scheduler, key="google_c2")
        add_campaign(scheduler, key="tiktok_c3", status="paused")

        pause_calls = []

        async def fake_pause(platform, campaign_id):
            pause_calls.append((platform, campaign_id))
            return True

        monkeypatch.setattr(scheduler, "_pause_campaign", fake_pause)

        result = await scheduler.pause_all_campaigns(reason="test")

        assert result == {"paused": 2, "failed": 0, "failed_campaigns": []}
        assert c1["status"] == "paused" and c2["status"] == "paused"
        assert sorted(pause_calls) == [("google", "c2"), ("meta", "c1")]
        assert sorted(scheduler._persisted) == ["google_c2", "meta_c1"]

    @pytest.mark.asyncio
    async def test_pause_all_reports_platform_failures(self, scheduler, monkeypatch):
        add_campaign(scheduler, key="meta_c1")
        c2 = add_campaign(scheduler, key="google_c2")

        async def fake_pause(platform, campaign_id):
            return platform != "google"  # google refuses

        monkeypatch.setattr(scheduler, "_pause_campaign", fake_pause)

        result = await scheduler.pause_all_campaigns(reason="test")

        assert result["paused"] == 1
        assert result["failed"] == 1
        assert result["failed_campaigns"] == ["google_c2"]
        assert c2["status"] == "active"  # honestly reported as NOT paused

    @pytest.mark.asyncio
    async def test_creation_clamps_budget(self, scheduler, monkeypatch):
        """A caller asking for $10k/day gets the ceiling, not $10k."""
        received = {}

        async def fake_create(platform, **kwargs):
            received[platform] = kwargs["daily_budget"]
            return {"success": True, "campaign_id": f"{platform}-1"}

        async def fake_platform_create(**kwargs):
            received[kwargs["platform"]] = kwargs["daily_budget"]
            return {"success": True, "campaign_id": "x-1"}

        monkeypatch.setattr(
            scheduler, "_create_platform_campaign",
            lambda **kw: fake_platform_create(**kw),
        )

        await scheduler.create_multi_platform_campaign(
            product_id=1, product_name="x", product_description="d",
            product_url="https://example.com", platforms=["meta"],
            daily_budget=10_000.0,
        )

        assert received["meta"] == scheduler.settings.ADS_MAX_DAILY_BUDGET


# ---------------------------------------------------------------------------
# T23 — campaign tracking survives restarts (DB-backed)
# ---------------------------------------------------------------------------

class TestT23Persistence:
    @pytest.fixture
    def db_session_factory(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from ospra_os.database.base import Base
        from ospra_os.database.advertising_models import AdCampaign

        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(engine, tables=[AdCampaign.__table__])
        factory = sessionmaker(bind=engine)

        import ospra_os.database as db_pkg
        monkeypatch.setattr(db_pkg, "get_multi_store_session", factory)
        return factory

    def _seed(self, factory, status="active", budget=42.0, budget_limit=80.0):
        from ospra_os.database.advertising_models import AdCampaign

        session = factory()
        row = AdCampaign(
            user_id=1, campaign_id="camp-1", platform="meta",
            campaign_name="seeded", daily_budget=budget,
            budget_limit=budget_limit, status=status,
        )
        session.add(row)
        session.commit()
        session.close()

    def test_load_campaigns_from_db(self, scheduler, db_session_factory):
        """After a restart, tracking is rebuilt from the DB — the auto-pause
        monitor keeps protecting campaigns created before the deploy."""
        self._seed(db_session_factory)

        scheduler.active_campaigns = {}
        scheduler._load_campaigns_from_db()

        assert "meta_camp-1" in scheduler.active_campaigns
        loaded = scheduler.active_campaigns["meta_camp-1"]
        assert loaded["daily_budget"] == 42.0
        assert loaded["budget_limit"] == 80.0
        assert loaded["status"] == "active"

    @pytest.mark.asyncio
    async def test_auto_pause_persists_to_db(self, monkeypatch, db_session_factory):
        """An auto-pause must survive a restart via the DB row."""
        from ospra_os.database.advertising_models import AdCampaign

        self._seed(db_session_factory)

        sched = AdScheduler.__new__(AdScheduler)
        sched.scheduler = MagicMock()
        sched.settings = make_settings()
        sched.meta_manager = sched.tiktok_manager = sched.google_manager = None
        sched.creative_generator = None
        sched.active_campaigns = {}
        sched._load_campaigns_from_db()

        async def fake_metrics(platform, campaign_id):
            return {"ctr": 0.001, "impressions": 500, "conversions": 0, "roas": 0}

        async def fake_pause(platform, campaign_id):
            return True

        monkeypatch.setattr(sched, "_get_campaign_metrics", fake_metrics)
        monkeypatch.setattr(sched, "_pause_campaign", fake_pause)

        await sched.auto_pause_poor_performers()

        session = db_session_factory()
        row = session.query(AdCampaign).filter_by(campaign_id="camp-1").one()
        session.close()
        assert row.status == "paused"
        assert "Low CTR" in row.pause_reason


# ---------------------------------------------------------------------------
# T25 — Google creates the whole tree PAUSED
# ---------------------------------------------------------------------------

class TestT25GoogleCreatesPaused:
    def _manager_with_fake_client(self):
        from ospra_os.advertising.google.google_ads import GoogleAdsManager

        mgr = GoogleAdsManager.__new__(GoogleAdsManager)
        mgr.client = MagicMock()
        mgr.customer_id = "123"
        return mgr

    def test_ad_group_created_paused(self):
        mgr = self._manager_with_fake_client()
        op = mgr._build_ad_group_operation("campaigns/1", "group")
        assert op.create.status is mgr.client.enums.AdGroupStatusEnum.PAUSED

    def test_ad_created_paused(self):
        mgr = self._manager_with_fake_client()
        op = mgr._build_ad_operation("adGroups/1", "prod", "copy", "https://x.com")
        assert op.create.status is mgr.client.enums.AdGroupAdStatusEnum.PAUSED

    def test_campaign_still_created_paused(self):
        mgr = self._manager_with_fake_client()
        op = mgr._build_campaign_operation("name", 10.0)
        assert op.create.status is mgr.client.enums.CampaignStatusEnum.PAUSED
