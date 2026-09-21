"""check_ad_performance — real ad spend, and the ownership rule around it.

This task was a stub that returned {"status": "success", "campaigns_checked":
0} while doing nothing, which is why ProductPerformance.ad_spend has never
held a real number. These tests pin both the implementation and the boundary
that keeps the number alive once written.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from ospra_os.database.advertising_models import AdCampaign
from ospra_os.database.base import Base
from ospra_os.database.performance_models import ProductPerformance
from ospra_os.tasks import analytics_tasks


def _tables(engine):
    Base.metadata.create_all(
        bind=engine,
        tables=[AdCampaign.__table__, ProductPerformance.__table__],
    )


def test_spend_is_attributed_onto_todays_performance_row(engine):
    _tables(engine)
    today = datetime.utcnow().date()
    with Session(engine) as s:
        s.add(ProductPerformance(
            product_id=4242, store_id=1, user_id=1, date=today,
            gross_revenue=500.0, net_revenue=500.0, product_cost=100.0,
            platform_fees=20.0, shipping_cost=0.0, ad_spend=0.0,
        ))
        c = AdCampaign(user_id=1, product_id=4242, campaign_id="c1",
                       platform="meta", campaign_name="x", status="active",
                       total_spend=150.0)
        s.add(c)
        s.commit()

        written = analytics_tasks._attribute_spend_to_products(s, [c])
        s.commit()

        row = s.query(ProductPerformance).one()
    assert written == 1
    assert row.ad_spend == 150.0
    # total_cost must absorb it, or margin still pretends ads were free.
    assert row.total_cost == 270.0          # 100 + 0 + 20 + 150
    assert row.net_profit == 230.0          # 500 - 270


def test_spend_is_set_not_accumulated(engine):
    """`total_spend` is the platform's LIFETIME figure. Adding it every daily
    run would compound a campaign's cost without limit."""
    _tables(engine)
    today = datetime.utcnow().date()
    with Session(engine) as s:
        s.add(ProductPerformance(product_id=77, store_id=1, user_id=1,
                                 date=today, gross_revenue=100.0,
                                 net_revenue=100.0, ad_spend=0.0))
        c = AdCampaign(user_id=1, product_id=77, campaign_id="c2",
                       platform="meta", campaign_name="y", status="active",
                       total_spend=40.0)
        s.add(c)
        s.commit()

        for _ in range(3):
            analytics_tasks._attribute_spend_to_products(s, [c])
            s.commit()
        row = s.query(ProductPerformance).filter_by(product_id=77).one()
    assert row.ad_spend == 40.0, "three runs must not triple the spend"


def test_unreachable_platform_returns_none_not_an_empty_dict():
    """'We could not ask' and 'it spent nothing' are different facts.
    Conflating them writes a zero over real spend."""
    class _C:
        platform = "meta"
        campaign_id = "boom"
    assert analytics_tasks._fetch_campaign_metrics(_C()) is None

    class _Unknown:
        platform = "carrier-pigeon"
        campaign_id = "z"
    assert analytics_tasks._fetch_campaign_metrics(_Unknown()) is None


def test_no_performance_row_means_skip_not_invent(engine):
    """A row conjured from ad spend alone would carry a fabricated
    store_id/user_id. The sales sync creates the real one."""
    _tables(engine)
    with Session(engine) as s:
        c = AdCampaign(user_id=1, product_id=999999, campaign_id="c3",
                       platform="meta", campaign_name="z", status="active",
                       total_spend=25.0)
        s.add(c)
        s.commit()
        assert analytics_tasks._attribute_spend_to_products(s, [c]) == 0
        assert s.query(ProductPerformance).filter_by(product_id=999999).count() == 0


def test_sales_sync_no_longer_hardcodes_ad_spend_to_zero():
    """OWNERSHIP GUARD.

    sales_sync_service owns sales/COGS/fees; ad spend is owned by
    check_ad_performance. The sync used to seed "ad_spend": 0.0 into a metrics
    dict that was then setattr'd field-by-field onto the existing row — so
    every 6-hourly run silently erased the real spend and margins looked like
    advertising was free.
    """
    import pathlib
    src = pathlib.Path("ospra_os/services/sales_sync_service.py").read_text()
    code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert '"ad_spend": 0.0' not in code, (
        "sales sync must not seed a zero ad_spend — it clobbers the real value"
    )
    assert "preserved_ad_spend" in code


def test_the_task_never_pauses_or_scales_on_its_own():
    """Ad budget is propose-then-approve. A scheduled job that could pause or
    scale campaigns by itself is exactly what must not exist here."""
    import inspect
    src = inspect.getsource(analytics_tasks.check_ad_performance)
    for forbidden in ("pause_campaign", "update_budget", "scale_campaign",
                      "set_budget", "remote_update"):
        assert forbidden not in src, f"task must not call {forbidden}"
    assert "suggested_action" in src, "it should RECOMMEND instead"
