"""Admin Dashboard Routes - Unified view of all Ospra OS data."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from ospra_os.core.settings import Settings, get_settings
from typing import Dict, Any
import asyncio

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


async def get_email_stats(settings: Settings) -> Dict[str, Any]:
    """Get email automation statistics."""
    try:
        from app.analytics import get_analytics_summary
        return get_analytics_summary(settings.database_url)
    except Exception as e:
        print(f"⚠️  Email stats error: {e}")
        return {
            "total_processed": 0,
            "total_replied": 0,
            "labels_applied": {},
            "error": str(e)
        }


async def get_product_discoveries(settings: Settings) -> Dict[str, Any]:
    """Get latest product discoveries."""
    try:
        from ospra_os.product_research.pipeline import ProductDiscoveryPipeline

        pipeline = ProductDiscoveryPipeline(
            reddit_client_id=getattr(settings, "REDDIT_CLIENT_ID", None),
            reddit_secret=getattr(settings, "REDDIT_SECRET", None),
            aliexpress_api_key=getattr(settings, "ALIEXPRESS_API_KEY", None),
            aliexpress_app_secret=getattr(settings, "ALIEXPRESS_APP_SECRET", None)
        )

        # Quick discovery with caching
        products = await pipeline.discover_products(
            niche="smart home",
            max_results=6,
            min_score=3.0,
            include_reddit=True,
            include_trends=True,
            include_aliexpress=False  # Skip for speed
        )

        return {
            "total": len(products),
            "products": products[:6]  # Top 6 for dashboard
        }
    except Exception as e:
        print(f"⚠️  Product discovery error: {e}")
        return {"total": 0, "products": [], "error": str(e)}


async def get_reddit_sentiment(settings: Settings) -> Dict[str, Any]:
    """Get Reddit trending sentiment."""
    try:
        from ospra_os.product_research.connectors.social.reddit import RedditConnector

        reddit = RedditConnector(
            client_id=getattr(settings, "REDDIT_CLIENT_ID", None),
            client_secret=getattr(settings, "REDDIT_SECRET", None)
        )

        if not reddit.is_available():
            return {"trending": [], "error": "Reddit not configured"}

        products = await reddit.get_trending(category="smart home", limit=5)

        return {
            "trending": [
                {
                    "name": p.name,
                    "score": p.trend_score,
                    "upvotes": p.social_mentions,
                    "comments": p.social_engagement,
                    "url": p.url
                }
                for p in products[:5]
            ]
        }
    except Exception as e:
        print(f"⚠️  Reddit sentiment error: {e}")
        return {"trending": [], "error": str(e)}


@router.get("/dashboard/data")
async def get_dashboard_data(settings: Settings = Depends(get_settings)):
    """
    Aggregate all dashboard data in one API call.

    Returns:
        - Email automation stats
        - Product discoveries with images
        - Reddit sentiment
        - System status
    """
    # Fetch all data in parallel
    email_stats, products, reddit = await asyncio.gather(
        get_email_stats(settings),
        get_product_discoveries(settings),
        get_reddit_sentiment(settings)
    )

    # Check API statuses
    from ospra_os.product_research.connectors.social.reddit import RedditConnector
    from ospra_os.product_research.connectors.suppliers.aliexpress import AliExpressConnector

    reddit_connector = RedditConnector(
        client_id=getattr(settings, "REDDIT_CLIENT_ID", None),
        client_secret=getattr(settings, "REDDIT_SECRET", None)
    )

    aliexpress_connector = AliExpressConnector(
        api_key=getattr(settings, "ALIEXPRESS_API_KEY", None),
        app_secret=getattr(settings, "ALIEXPRESS_APP_SECRET", None)
    )

    return {
        "email": email_stats,
        "products": products,
        "reddit": reddit,
        "status": {
            "reddit_api": reddit_connector.is_available(),
            "aliexpress_api": aliexpress_connector.is_available(),
            "email_automation": True,  # Always running via scheduler
        }
    }


@router.get("/dashboard/v2", response_class=HTMLResponse)
async def dashboard_v2():
    """New comprehensive Ospra OS Dashboard with 5 tabs."""
    from pathlib import Path
    dashboard_path = Path(__file__).parent.parent.parent / "static" / "ospra_dashboard.html"
    if not dashboard_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
    with open(dashboard_path, "r") as f:
        return HTMLResponse(content=f.read())


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """
    Unified Ospra OS Dashboard.

    Shows email automation, product discoveries, and Reddit sentiment in one view.
    """
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ospra OS Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }

        .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .card h2 {
            font-size: 1.4rem;
            margin-bottom: 15px;
            color: #667eea;
        }

        .stat {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }

        .stat:last-child {
            border-bottom: none;
        }

        .stat-label {
            color: #666;
        }

        .stat-value {
            font-weight: bold;
            color: #333;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }

        .status-active {
            background: #10b981;
            color: white;
        }

        .status-inactive {
            background: #ef4444;
            color: white;
        }

        .product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .product-card {
            background: #f9fafb;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            transition: transform 0.2s;
        }

        .product-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .product-image {
            width: 100%;
            height: 120px;
            object-fit: cover;
            border-radius: 6px;
            margin-bottom: 10px;
            background: #e5e7eb;
        }

        .product-name {
            font-size: 0.9rem;
            font-weight: 500;
            margin-bottom: 8px;
            color: #333;
            min-height: 40px;
        }

        .product-score {
            font-size: 0.85rem;
            color: #667eea;
            font-weight: bold;
        }

        .reddit-item {
            padding: 12px;
            background: #f9fafb;
            border-radius: 6px;
            margin-bottom: 10px;
        }

        .reddit-title {
            font-weight: 500;
            margin-bottom: 5px;
            color: #333;
        }

        .reddit-stats {
            font-size: 0.85rem;
            color: #666;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }

        .error {
            background: #fee2e2;
            color: #991b1b;
            padding: 12px;
            border-radius: 6px;
            margin: 10px 0;
        }

        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            margin-top: 10px;
        }

        .refresh-btn:hover {
            background: #5568d3;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Ospra OS Dashboard</h1>
            <p class="subtitle">Autonomous E-commerce Command Center</p>
        </header>

        <div id="dashboard-content">
            <div class="loading">Loading dashboard data...</div>
        </div>

        <div style="text-align: center;">
            <button class="refresh-btn" onclick="loadDashboard()">🔄 Refresh Data</button>
        </div>
    </div>

    <script>
        async function loadDashboard() {
            const content = document.getElementById('dashboard-content');
            content.innerHTML = '<div class="loading">Loading dashboard data...</div>';

            try {
                const response = await fetch('/admin/dashboard/data');
                const data = await response.json();

                content.innerHTML = `
                    <!-- Status Overview -->
                    <div class="grid">
                        <div class="card">
                            <h2>📧 Email Automation</h2>
                            <div class="stat">
                                <span class="stat-label">Total Processed</span>
                                <span class="stat-value">${data.email.total_processed || 0}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Auto-Replied</span>
                                <span class="stat-value">${data.email.total_replied || 0}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Status</span>
                                <span class="status-badge status-active">Active</span>
                            </div>
                        </div>

                        <div class="card">
                            <h2>🔌 API Status</h2>
                            <div class="stat">
                                <span class="stat-label">Reddit API</span>
                                <span class="status-badge ${data.status.reddit_api ? 'status-active' : 'status-inactive'}">
                                    ${data.status.reddit_api ? 'Connected' : 'Disconnected'}
                                </span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">AliExpress API</span>
                                <span class="status-badge ${data.status.aliexpress_api ? 'status-active' : 'status-inactive'}">
                                    ${data.status.aliexpress_api ? 'Connected' : 'Pending'}
                                </span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Email Scheduler</span>
                                <span class="status-badge status-active">Running</span>
                            </div>
                        </div>

                        <div class="card">
                            <h2>📊 Product Discoveries</h2>
                            <div class="stat">
                                <span class="stat-label">Products Found</span>
                                <span class="stat-value">${data.products.total || 0}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Reddit Trending</span>
                                <span class="stat-value">${data.reddit.trending?.length || 0}</span>
                            </div>
                            <div class="stat">
                                <span class="stat-label">Last Updated</span>
                                <span class="stat-value">Just now</span>
                            </div>
                        </div>
                    </div>

                    <!-- Product Discoveries -->
                    <div class="card" style="margin-bottom: 20px;">
                        <h2>🎯 Top Product Opportunities</h2>
                        ${data.products.products && data.products.products.length > 0 ? `
                            <div class="product-grid">
                                ${data.products.products.map(p => `
                                    <div class="product-card">
                                        ${p.product.image_url ?
                                            `<img src="${p.product.image_url}" class="product-image" alt="${p.product.name}">` :
                                            '<div class="product-image"></div>'
                                        }
                                        <div class="product-name">${p.product.name}</div>
                                        <div class="product-score">Score: ${p.score.toFixed(1)}/10</div>
                                        ${p.product.price ? `<div style="color: #10b981; font-weight: bold; margin-top: 5px;">$${p.product.price}</div>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        ` : '<p style="color: #666;">No products discovered yet. Try running a search!</p>'}
                    </div>

                    <!-- Reddit Sentiment -->
                    <div class="card">
                        <h2>💬 Reddit Community Trending</h2>
                        ${data.reddit.trending && data.reddit.trending.length > 0 ? `
                            ${data.reddit.trending.map(item => `
                                <div class="reddit-item">
                                    <div class="reddit-title">${item.name}</div>
                                    <div class="reddit-stats">
                                        ⬆️ ${item.upvotes} upvotes • 💬 ${item.comments} comments • Score: ${item.score?.toFixed(1) || 'N/A'}
                                    </div>
                                </div>
                            `).join('')}
                        ` : '<p style="color: #666;">No Reddit data available. Check API configuration.</p>'}
                    </div>
                `;

            } catch (error) {
                content.innerHTML = `
                    <div class="card">
                        <div class="error">
                            ⚠️ Error loading dashboard: ${error.message}
                        </div>
                    </div>
                `;
            }
        }

        // Load dashboard on page load
        loadDashboard();

        // Auto-refresh every 60 seconds
        setInterval(loadDashboard, 60000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
