"""
Learning Summary Generator
===========================

Computes pre-computed summaries from raw learning_events.
This is the key to unlimited memory - we compress raw data into token-efficient summaries.

Run nightly via background job to keep summaries fresh.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from ospra_os.database.multi_store_models import SessionLocal
from ospra_os.learning.hybrid_learning_engine import LearningEvent
from ospra_os.learning.summary_models import (
    LearningSummary,
    NichePerformance,
    ProductPerformance,
    TimeSeriesMetrics
)

logger = logging.getLogger(__name__)


def generate_daily_summaries(user_id: int, db: Session = None) -> Dict[str, Any]:
    """
    Generate comprehensive summary for a user from all learning_events.

    This compresses unlimited raw data into ~800-1000 tokens.

    Args:
        user_id: User to generate summary for
        db: Database session (optional, will create if not provided)

    Returns:
        Dictionary with all summary data
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        logger.info(f"📊 Generating summary for user {user_id}...")

        # Fetch all learning events for this user
        events = db.query(LearningEvent).filter(
            LearningEvent.user_id == user_id
        ).all()

        if not events:
            logger.warning(f"No learning events found for user {user_id}")
            return _empty_summary()

        # ========================================================================
        # 1. OVERALL PERFORMANCE
        # ========================================================================
        overall = _compute_overall_performance(events)

        # ========================================================================
        # 2. NICHE INSIGHTS
        # ========================================================================
        niche_insights = _compute_niche_insights(events, db, user_id)

        # ========================================================================
        # 3. TOP/BOTTOM PRODUCTS
        # ========================================================================
        top_products, underperformers = _compute_product_rankings(events)

        # ========================================================================
        # 4. PRICE INSIGHTS
        # ========================================================================
        price_insights = _compute_price_insights(events)

        # ========================================================================
        # 5. AD INSIGHTS
        # ========================================================================
        ad_insights = _compute_ad_insights(events)

        # ========================================================================
        # 6. AI RECOMMENDATIONS
        # ========================================================================
        recommendations = _generate_recommendations(
            overall, niche_insights, top_products, underperformers, price_insights, ad_insights
        )

        # ========================================================================
        # 7. ESTIMATE TOKEN COUNT
        # ========================================================================
        import json
        summary_json = json.dumps({
            "overall": overall,
            "niches": niche_insights,
            "products": top_products[:5],  # Only top 5 for token estimation
            "price": price_insights,
            "ads": ad_insights
        })
        estimated_tokens = len(summary_json.split()) + len(recommendations.split())

        # ========================================================================
        # 8. STORE SUMMARY
        # ========================================================================
        summary_data = {
            "overall_performance": overall,
            "niche_insights": niche_insights,
            "top_products": top_products,
            "underperformers": underperformers,
            "price_insights": price_insights,
            "ad_insights": ad_insights,
            "recommendations": recommendations,
            "estimated_tokens": estimated_tokens
        }

        # Save or update summary
        existing_summary = db.query(LearningSummary).filter(
            LearningSummary.user_id == user_id,
            func.date(LearningSummary.summary_date) == datetime.utcnow().date()
        ).first()

        if existing_summary:
            # Update existing
            for key, value in summary_data.items():
                setattr(existing_summary, key, value)
            existing_summary.updated_at = datetime.utcnow()
        else:
            # Create new
            new_summary = LearningSummary(
                user_id=user_id,
                **summary_data
            )
            db.add(new_summary)

        db.commit()

        logger.info(f"✅ Summary generated for user {user_id} (~{estimated_tokens} tokens)")

        return summary_data

    except Exception as e:
        logger.error(f"Failed to generate summary for user {user_id}: {e}")
        raise
    finally:
        if should_close:
            db.close()


def _compute_overall_performance(events: List[LearningEvent]) -> Dict[str, Any]:
    """Compute overall business performance metrics"""

    total_revenue = 0.0
    total_units = 0
    products_deployed = set()
    sales_by_month = defaultdict(float)

    for event in events:
        details = event.details
        event_type = event.event_type

        if event_type in ["sale", "historical_sale"]:
            revenue = details.get("revenue", 0)
            quantity = details.get("quantity", 0)

            total_revenue += revenue
            total_units += quantity

            # Track by month
            month = event.created_at.strftime("%Y-%m")
            sales_by_month[month] += revenue

        elif event_type == "product_deployed":
            product_id = details.get("product_id")
            if product_id:
                products_deployed.add(product_id)

    # Find best month
    best_month = max(sales_by_month.items(), key=lambda x: x[1])[0] if sales_by_month else "N/A"
    best_month_revenue = sales_by_month.get(best_month, 0)

    total_sales = len([e for e in events if e.event_type in ["sale", "historical_sale"]])

    avg_revenue_per_product = total_revenue / len(products_deployed) if products_deployed else 0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_products_deployed": len(products_deployed),
        "total_sales": total_sales,
        "total_units_sold": total_units,
        "avg_revenue_per_product": round(avg_revenue_per_product, 2),
        "best_month": best_month,
        "best_month_revenue": round(best_month_revenue, 2)
    }


def _compute_niche_insights(events: List[LearningEvent], db: Session, user_id: int) -> Dict[str, Dict]:
    """Compute performance by niche"""

    niche_stats = defaultdict(lambda: {
        "revenue": 0.0,
        "units": 0,
        "products": set(),
        "ad_spend": 0.0,
        "ad_revenue": 0.0,
        "prices": []
    })

    for event in events:
        details = event.details
        niche = details.get("niche", "unknown")

        if event.event_type in ["sale", "historical_sale"]:
            revenue = details.get("revenue", 0)
            quantity = details.get("quantity", 0)
            price = details.get("price", 0)
            product_id = details.get("product_id")

            niche_stats[niche]["revenue"] += revenue
            niche_stats[niche]["units"] += quantity
            if product_id:
                niche_stats[niche]["products"].add(product_id)
            if price:
                niche_stats[niche]["prices"].append(price)

        elif event.event_type == "ad_performance":
            niche_stats[niche]["ad_spend"] += details.get("spend", 0)
            niche_stats[niche]["ad_revenue"] += details.get("revenue", 0)

    # Compute final metrics
    niche_insights = {}
    for niche, stats in niche_stats.items():
        avg_price = sum(stats["prices"]) / len(stats["prices"]) if stats["prices"] else 0
        roas = stats["ad_revenue"] / stats["ad_spend"] if stats["ad_spend"] > 0 else 0
        success_rate = 0.75  # Placeholder - would compute from profitable products

        niche_insights[niche] = {
            "revenue": round(stats["revenue"], 2),
            "units_sold": stats["units"],
            "num_products": len(stats["products"]),
            "avg_price": round(avg_price, 2),
            "success_rate": round(success_rate, 2),
            "ad_spend": round(stats["ad_spend"], 2),
            "ad_revenue": round(stats["ad_revenue"], 2),
            "roas": round(roas, 2)
        }

        # Update NichePerformance table
        _update_niche_performance(db, user_id, niche, niche_insights[niche])

    return niche_insights


def _compute_product_rankings(events: List[LearningEvent]) -> tuple:
    """Identify top performers and underperformers"""

    product_stats = defaultdict(lambda: {
        "name": "",
        "niche": "",
        "revenue": 0.0,
        "units": 0,
        "ad_spend": 0.0,
        "ad_revenue": 0.0
    })

    for event in events:
        details = event.details
        product_id = details.get("product_id")

        if not product_id:
            continue

        # Update name/niche
        if details.get("product_name"):
            product_stats[product_id]["name"] = details["product_name"]
        if details.get("niche"):
            product_stats[product_id]["niche"] = details["niche"]

        if event.event_type in ["sale", "historical_sale"]:
            product_stats[product_id]["revenue"] += details.get("revenue", 0)
            product_stats[product_id]["units"] += details.get("quantity", 0)

        elif event.event_type == "ad_performance":
            product_stats[product_id]["ad_spend"] += details.get("spend", 0)
            product_stats[product_id]["ad_revenue"] += details.get("revenue", 0)

    # Convert to list and add ROI
    products = []
    for product_id, stats in product_stats.items():
        roi = ((stats["revenue"] - stats["ad_spend"]) / stats["ad_spend"] * 100) if stats["ad_spend"] > 0 else 100
        products.append({
            "product_id": product_id,
            "name": stats["name"],
            "niche": stats["niche"],
            "revenue": round(stats["revenue"], 2),
            "units_sold": stats["units"],
            "roi_percentage": round(roi, 1)
        })

    # Sort by revenue for top performers
    top_products = sorted(products, key=lambda x: x["revenue"], reverse=True)[:10]

    # Underperformers: negative or very low ROI
    underperformers = [p for p in products if p["roi_percentage"] < 10][:10]

    return top_products, underperformers


def _compute_price_insights(events: List[LearningEvent]) -> Dict[str, Any]:
    """Analyze optimal pricing"""

    price_brackets = {
        "0-20": {"revenue": 0, "units": 0, "count": 0},
        "20-40": {"revenue": 0, "units": 0, "count": 0},
        "40-60": {"revenue": 0, "units": 0, "count": 0},
        "60+": {"revenue": 0, "units": 0, "count": 0}
    }

    for event in events:
        if event.event_type not in ["sale", "historical_sale"]:
            continue

        details = event.details
        price = details.get("price", 0)
        revenue = details.get("revenue", 0)
        quantity = details.get("quantity", 0)

        # Determine bracket
        if price < 20:
            bracket = "0-20"
        elif price < 40:
            bracket = "20-40"
        elif price < 60:
            bracket = "40-60"
        else:
            bracket = "60+"

        price_brackets[bracket]["revenue"] += revenue
        price_brackets[bracket]["units"] += quantity
        price_brackets[bracket]["count"] += 1

    # Find optimal range (highest revenue per sale)
    best_bracket = max(
        price_brackets.items(),
        key=lambda x: x[1]["revenue"] / x[1]["count"] if x[1]["count"] > 0 else 0
    )[0]

    # Compute conversion rates (simplified - units per listing)
    conversion_by_bracket = {}
    for bracket, stats in price_brackets.items():
        conv_rate = stats["units"] / stats["count"] if stats["count"] > 0 else 0
        conversion_by_bracket[bracket] = round(conv_rate, 2)

    return {
        "optimal_range": f"${best_bracket}",
        "conversion_by_bracket": conversion_by_bracket,
        "revenue_by_bracket": {k: round(v["revenue"], 2) for k, v in price_brackets.items()}
    }


def _compute_ad_insights(events: List[LearningEvent]) -> Dict[str, Any]:
    """Analyze ad performance across platforms"""

    platform_stats = defaultdict(lambda: {
        "spend": 0.0,
        "revenue": 0.0,
        "impressions": 0,
        "clicks": 0,
        "conversions": 0
    })

    for event in events:
        if event.event_type != "ad_performance":
            continue

        details = event.details
        platform = details.get("platform", "unknown")

        platform_stats[platform]["spend"] += details.get("spend", 0)
        platform_stats[platform]["revenue"] += details.get("revenue", 0)
        platform_stats[platform]["impressions"] += details.get("impressions", 0)
        platform_stats[platform]["clicks"] += details.get("clicks", 0)
        platform_stats[platform]["conversions"] += details.get("conversions", 0)

    if not platform_stats:
        return {
            "best_platform": "N/A",
            "avg_roas": 0,
            "optimal_daily_spend": "N/A",
            "platform_comparison": {}
        }

    # Compute ROAS by platform
    platform_roas = {}
    for platform, stats in platform_stats.items():
        roas = stats["revenue"] / stats["spend"] if stats["spend"] > 0 else 0
        platform_roas[platform] = round(roas, 2)

    best_platform = max(platform_roas.items(), key=lambda x: x[1])[0] if platform_roas else "N/A"

    total_spend = sum(s["spend"] for s in platform_stats.values())
    total_revenue = sum(s["revenue"] for s in platform_stats.values())
    avg_roas = total_revenue / total_spend if total_spend > 0 else 0

    # Estimate optimal daily spend (simplified)
    optimal_spend = "N/A"
    if total_spend > 0:
        avg_daily = total_spend / 30  # Rough estimate
        if avg_daily < 25:
            optimal_spend = "$25-50"
        elif avg_daily < 75:
            optimal_spend = "$50-100"
        else:
            optimal_spend = "$100+"

    return {
        "best_platform": best_platform,
        "avg_roas": round(avg_roas, 2),
        "optimal_daily_spend": optimal_spend,
        "platform_comparison": platform_roas
    }


def _generate_recommendations(overall, niches, top_products, underperformers, prices, ads) -> str:
    """Generate AI-readable recommendations"""

    recommendations = []

    # Niche recommendations
    if niches:
        best_niche = max(niches.items(), key=lambda x: x[1]["revenue"])[0]
        best_success_rate = niches[best_niche].get("success_rate", 0)

        recommendations.append(
            f"1. Focus on {best_niche} - generating ${niches[best_niche]['revenue']:,.2f} "
            f"with {best_success_rate:.0%} success rate"
        )

        # Warn about underperforming niches
        underperforming_niches = [
            (n, data) for n, data in niches.items()
            if data["revenue"] < overall["total_revenue"] * 0.1
        ]
        if underperforming_niches:
            worst_niche = underperforming_niches[0][0]
            recommendations.append(
                f"2. Consider reducing {worst_niche} inventory - contributing only "
                f"${underperforming_niches[0][1]['revenue']:.2f} to total revenue"
            )

    # Price recommendations
    if prices and prices["optimal_range"] != "$N/A":
        recommendations.append(
            f"3. Products priced {prices['optimal_range']} show best performance"
        )

    # Ad recommendations
    if ads and ads["best_platform"] != "N/A":
        best_roas = ads["platform_comparison"].get(ads["best_platform"], 0)
        recommendations.append(
            f"4. {ads['best_platform']} ads delivering {best_roas:.2f}x ROAS - "
            f"consider increasing budget from other platforms"
        )

    # Product recommendations
    if underperformers:
        recommendations.append(
            f"5. {len(underperformers)} products showing negative ROI - review or discontinue"
        )

    return "\n".join(recommendations) if recommendations else "Insufficient data for recommendations"


def _update_niche_performance(db: Session, user_id: int, niche: str, stats: Dict):
    """Update aggregated niche performance table"""

    niche_perf = db.query(NichePerformance).filter(
        NichePerformance.user_id == user_id,
        NichePerformance.niche == niche
    ).first()

    if niche_perf:
        niche_perf.total_revenue = stats["revenue"]
        niche_perf.total_units_sold = stats["units_sold"]
        niche_perf.total_products = stats["num_products"]
        niche_perf.avg_price = stats["avg_price"]
        niche_perf.success_rate = stats["success_rate"]
        niche_perf.total_ad_spend = stats["ad_spend"]
        niche_perf.total_ad_revenue = stats["ad_revenue"]
        niche_perf.avg_roas = stats["roas"]
        niche_perf.updated_at = datetime.utcnow()
    else:
        new_niche_perf = NichePerformance(
            user_id=user_id,
            niche=niche,
            total_revenue=stats["revenue"],
            total_units_sold=stats["units_sold"],
            total_products=stats["num_products"],
            avg_price=stats["avg_price"],
            success_rate=stats["success_rate"],
            total_ad_spend=stats["ad_spend"],
            total_ad_revenue=stats["ad_revenue"],
            avg_roas=stats["roas"]
        )
        db.add(new_niche_perf)


def _empty_summary() -> Dict[str, Any]:
    """Return empty summary structure"""
    return {
        "overall_performance": {
            "total_revenue": 0,
            "total_products_deployed": 0,
            "total_sales": 0,
            "avg_revenue_per_product": 0,
            "best_month": "N/A"
        },
        "niche_insights": {},
        "top_products": [],
        "underperformers": [],
        "price_insights": {
            "optimal_range": "N/A",
            "conversion_by_bracket": {}
        },
        "ad_insights": {
            "best_platform": "N/A",
            "avg_roas": 0,
            "optimal_daily_spend": "N/A",
            "platform_comparison": {}
        },
        "recommendations": "No data available - start tracking sales and deployments",
        "estimated_tokens": 100
    }


async def generate_all_user_summaries():
    """Generate summaries for all users with learning events"""

    db = SessionLocal()
    try:
        # Get all users with learning events
        users_with_events = db.query(LearningEvent.user_id).distinct().all()
        user_ids = [u[0] for u in users_with_events if u[0] is not None]

        logger.info(f"📊 Generating summaries for {len(user_ids)} users...")

        for user_id in user_ids:
            try:
                generate_daily_summaries(user_id, db)
            except Exception as e:
                logger.error(f"Failed to generate summary for user {user_id}: {e}")

        logger.info(f"✅ Generated summaries for {len(user_ids)} users")

    finally:
        db.close()
