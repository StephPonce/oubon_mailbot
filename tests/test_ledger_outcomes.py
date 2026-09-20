"""F1 — outcome aggregation, and the join that makes it possible.

The join tests here are the important ones. Before migration 014 there was no
path from a Shopify order line item back to the product Ospra graded: the
webhook filtered `Product.source_product_id` (which holds the SUPPLIER id) with
a SHOPIFY id, and the batch sync read a column that did not exist on Product.
Both failed silently, so per-product sales tracking reported success while
recording nothing. These tests fail if that regresses.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from ospra_os.database.base import Base
from ospra_os.database.ledger_models import (
    CalibrationReport, GradeSnapshot, ProductOutcome,
)
from ospra_os.database.performance_models import ProductPerformance
from ospra_os.database.product_models import Product
from ospra_os.database.product_timeseries import ProductTimeseries, product_identity_key
from ospra_os.tasks import ledger_tasks


@pytest.fixture()
def led(engine, monkeypatch):
    Base.metadata.create_all(
        bind=engine,
        tables=[GradeSnapshot.__table__, ProductOutcome.__table__,
                CalibrationReport.__table__, ProductTimeseries.__table__,
                ProductPerformance.__table__, Product.__table__],
    )
    monkeypatch.setattr(ledger_tasks, "_session", lambda: Session(engine))
    with Session(engine) as s:
        for t in ("grade_snapshots", "product_outcomes", "product_timeseries",
                  "product_performance", "products"):
            s.execute(text(f"DELETE FROM {t}"))
        s.commit()
    return ledger_tasks


# ---------------------------------------------------------------------------
# The join — what was broken
# ---------------------------------------------------------------------------

def test_product_carries_both_ids_so_orders_can_reach_predictions(led, engine):
    """A Product must hold the SHOPIFY id (what webhooks arrive with) and the
    discovery product_key (what grades are filed under). They are different
    id spaces and neither substitutes for the other."""
    source = {"product_id": "AE-123", "title": "Widget"}
    key = product_identity_key(source)

    with Session(engine) as s:
        s.add(Product(
            store_id=1, product_name="Widget",
            source_product_id="AE-123",      # supplier id
            shopify_product_id="99887766",   # Shopify id — a DIFFERENT space
            product_key=key,
        ))
        s.commit()

        # The webhook's actual lookup: by Shopify id.
        found = s.query(Product).filter(
            Product.shopify_product_id == "99887766").first()
        assert found is not None, "order webhook could not find the product"
        assert found.product_key == key

        # And the old broken lookup must NOT match — proving the two ids are
        # genuinely distinct and the original filter could never have worked.
        assert s.query(Product).filter(
            Product.source_product_id == "99887766").first() is None


def test_real_outcome_rolls_shopify_sales_up_to_the_prediction_key(led, engine):
    source = {"product_id": "AE-123", "title": "Widget"}
    key = product_identity_key(source)
    today = datetime.utcnow()

    with Session(engine) as s:
        p = Product(store_id=1, product_name="Widget",
                    shopify_product_id="99887766", product_key=key)
        s.add(p)
        s.flush()
        s.add(ProductPerformance(
            product_id=p.id, store_id=1, user_id=1,
            date=datetime.utcnow().date() - timedelta(days=1),
            orders=3, units_sold=5, gross_revenue=250.0,
            refunds=10.0, total_cost=90.0, ad_spend=40.0,
        ))
        s.commit()

    result = led.aggregate_product_outcomes(period_days=7)
    assert result["success"] is True
    assert result["real_outcomes"] == 1

    with Session(engine) as s:
        out = s.query(ProductOutcome).filter(
            ProductOutcome.product_key == key).one()
    assert out.orders == 3
    assert out.units == 5
    assert out.revenue == 250.0
    assert out.ad_spend == 40.0
    # (250 - 90 - 10) / 250 * 100
    assert out.margin_actual == pytest.approx(60.0)
    assert today - timedelta(days=8) < out.period_start < today


def test_products_without_a_key_are_skipped_not_guessed(led, engine):
    """Products deployed before 014 have NULL keys. Attributing their sales to
    some inferred prediction would fabricate exactly the provenance the ledger
    exists to prove."""
    with Session(engine) as s:
        p = Product(store_id=1, product_name="Legacy",
                    shopify_product_id="111", product_key=None)
        s.add(p)
        s.flush()
        s.add(ProductPerformance(
            product_id=p.id, store_id=1, user_id=1,
            date=datetime.utcnow().date() - timedelta(days=1), orders=9, gross_revenue=900.0,
        ))
        s.commit()

    result = led.aggregate_product_outcomes(period_days=7)
    assert result["real_outcomes"] == 0
    with Session(engine) as s:
        assert s.query(ProductOutcome).count() == 0


# ---------------------------------------------------------------------------
# Proxies — how undeployed products get validated (F8 paper-trade)
# ---------------------------------------------------------------------------

def test_undeployed_products_get_proxy_outcomes(led, engine):
    """Without proxies only deployed products could ever be validated, which is
    survivorship bias baked into the engine's own report card."""
    key = "abc123"
    with Session(engine) as s:
        s.add(GradeSnapshot(
            product_key=key, ts=datetime.utcnow() - timedelta(days=6),
            pipeline_run_id="r1", grade=8.0, source_manifest={},
        ))
        for i, (orders, trend) in enumerate([(100, 40.0), (170, 61.0)]):
            s.add(ProductTimeseries(
                product_key=key, snapshot_date=datetime.utcnow().date() - timedelta(days=7 - i * 6),
                aliexpress_orders=orders, google_trends_interest=trend,
                signal_count=2,
            ))
        s.commit()

    result = led.aggregate_product_outcomes(period_days=7)
    assert result["proxy_outcomes"] == 1

    with Session(engine) as s:
        out = s.query(ProductOutcome).filter(
            ProductOutcome.product_key == key).one()
    # (170-100)/6 days
    assert out.proxy_ae_velocity == pytest.approx(11.6667, abs=0.01)
    assert out.proxy_trend_delta == pytest.approx(3.5, abs=0.01)
    # Never invented: this product sold nothing because it was never deployed.
    assert out.orders is None


def test_single_timeseries_point_yields_no_proxy(led, engine):
    """One reading is a level, not a delta. NULL beats a fabricated zero."""
    key = "onlyone"
    with Session(engine) as s:
        s.add(GradeSnapshot(product_key=key, ts=datetime.utcnow(),
                            pipeline_run_id="r1", grade=7.0, source_manifest={}))
        s.add(ProductTimeseries(
            product_key=key, snapshot_date=datetime.utcnow().date() - timedelta(days=1),
            aliexpress_orders=100, google_trends_interest=50.0, signal_count=1,
        ))
        s.commit()

    assert led.aggregate_product_outcomes(period_days=7)["proxy_outcomes"] == 0


def test_reaggregation_updates_rather_than_duplicates(led, engine):
    """Outcomes are measurements and get restated (late refunds, reconciled ad
    spend). Unlike snapshots they update in place — but must never duplicate."""
    key = "restate"
    with Session(engine) as s:
        s.add(GradeSnapshot(product_key=key, ts=datetime.utcnow(),
                            pipeline_run_id="r1", grade=8.0, source_manifest={}))
        for i, orders in enumerate([10, 40]):
            s.add(ProductTimeseries(
                product_key=key, snapshot_date=datetime.utcnow().date() - timedelta(days=4 - i * 3),
                aliexpress_orders=orders, signal_count=1,
            ))
        s.commit()

    led.aggregate_product_outcomes(period_days=7)
    led.aggregate_product_outcomes(period_days=7)

    with Session(engine) as s:
        assert s.query(ProductOutcome).filter(
            ProductOutcome.product_key == key).count() == 1


def test_aggregation_failure_reports_failure(led, monkeypatch):
    class _Boom:
        def query(self, *a, **k): raise RuntimeError("db down")
        def rollback(self): pass
        def close(self): pass

    monkeypatch.setattr(ledger_tasks, "_session", lambda: _Boom())
    result = ledger_tasks.aggregate_product_outcomes(period_days=7)
    assert result["success"] is False
    assert "db down" in result["error"]


def test_date_columns_are_written_in_utc_not_server_local():
    """Every writer of a date column the F1 window reads must use UTC.

    The aggregation window is computed from utcnow(). A writer using
    `date.today()` files rows under the server's LOCAL day, so on any non-UTC
    server the row lands on the wrong date and can fall outside the window
    entirely — invisible until someone notices outcomes are missing. This bug
    was live in webhook_utils.py and only surfaced because the test machine
    happened to be behind UTC at the time.
    """
    import pathlib
    import re

    for rel in ("ospra_os/webhooks/webhook_utils.py",
                "ospra_os/tasks/catalog_warm.py",
                "ospra_os/tasks/ledger_tasks.py"):
        # Code only — a comment explaining the rule must not trip it.
        code = "\n".join(
            line for line in pathlib.Path(rel).read_text().splitlines()
            if not line.lstrip().startswith("#")
        )
        # `date.today()` / `_date.today()` — but NOT `utcnow().date()`
        offenders = re.findall(r"(?<!utcnow\(\)\.)\b_?date\.today\(\)", code)
        assert not offenders, (
            f"{rel} uses date.today() (server-local). Use "
            f"datetime.utcnow().date() — the F1 window is UTC-based."
        )
