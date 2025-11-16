# Ospra Intelligence

**AI-Powered E-Commerce Automation Platform**

Complete dropshipping automation with intelligent product discovery, performance tracking, and AI-driven decision making.

---

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start the platform
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload

# 4. Access the platform
# API: http://localhost:8001
# Docs: http://localhost:8001/docs
```

---

## Features

### Level 1: Data Collection
- **AliExpress Integration**: Direct API access for product discovery
- **Multi-Niche Support**: Smart Home, Fitness, Beauty, Pet Care, Kitchen, Gaming
- **Real-Time Data**: Live product metrics, pricing, and inventory

### Level 2: AI Analysis
- **Claude-Powered Research**: Deep market analysis using Anthropic's Claude API
- **Product Scoring**: Intelligent ranking based on 10+ factors
- **Trend Detection**: Identify rising products before they peak
- **Competitive Analysis**: Track market positioning and opportunities

### Level 3: Autonomous Intelligence (NEW)
- **Background Monitoring**: Automated 24/7 product performance tracking
- **AI Alerts**: Proactive notifications for underperformers and opportunities
- **Scheduled Analysis**: Automatic jobs for products, competitors, trends, and reports
- **Smart Recommendations**: AI-generated action items with predicted outcomes

### Dashboard & Analytics
- **Real-Time Metrics**: Live product performance data
- **Niche Overview**: Category-level insights and trends
- **Product Discovery**: Find winning products in any niche
- **Velocity Tracking**: Monitor product momentum and growth

### Integrations
- **Shopify**: Direct store management and order tracking
- **Gmail**: Email automation and customer support
- **TikTok**: Social media integration (in development)

---

## API Endpoints

### Product Intelligence

```bash
# Get all niches
GET /api/dashboard/v2/niches

# Get products by niche
GET /api/dashboard/v2/products?niche=smart_home&page=1&per_page=20

# Get niche overview
GET /api/dashboard/v2/overview?niche=fitness

# Discover new products
POST /api/intelligence/discover
```

### Level 3 AI - Scheduler & Alerts

```bash
# Get AI-generated alerts
GET /api/dashboard/v2/intelligence/alerts?limit=50&severity=warning

# Clear all alerts
DELETE /api/dashboard/v2/intelligence/alerts

# Get scheduler status
GET /api/dashboard/v2/intelligence/scheduler/status

# Start background jobs
POST /api/dashboard/v2/intelligence/scheduler/start

# Stop background jobs
POST /api/dashboard/v2/intelligence/scheduler/stop

# Manually trigger job
POST /api/dashboard/v2/intelligence/scheduler/run-now/{job_name}
# Valid jobs: analyze_products, monitor_competitors, track_trends, weekly_report
```

### Shopify Integration

```bash
# Get store info
GET /api/dashboard/shopify

# Import products to Shopify
POST /api/dashboard/shopify/import
```

---

## Configuration

### Environment Variables

Create `.env` file with:

```bash
# AI & Intelligence
ANTHROPIC_API_KEY=sk-ant-...          # Claude API for Level 2 & 3 AI

# AliExpress Integration
ALIEXPRESS_APP_KEY=...                # AliExpress API credentials
ALIEXPRESS_APP_SECRET=...
ALIEXPRESS_SESSION_KEY=...

# Shopify Integration
SHOPIFY_STORE=yourstore.myshopify.com
SHOPIFY_API_TOKEN=shpat_...

# Gmail Integration (Legacy MailBot)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# OpenAI (Legacy MailBot)
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///./data/ospra.db
```

### Directory Structure

```
ospra_os/
├── main.py                    # Application entry point
├── core/
│   └── settings.py           # Configuration management
├── intelligence/
│   ├── ai_research_agent.py  # Level 2 AI - Claude integration
│   ├── background_jobs.py    # Level 3 AI - Autonomous monitoring
│   ├── product_intelligence_v3.py  # Product discovery engine
│   └── product_discovery_REALTIME.py
├── dashboard/
│   └── routes_v2_REALTIME.py # API endpoints
├── integrations/
│   ├── aliexpress_api.py     # AliExpress client
│   └── shopify_client.py     # Shopify client
└── database/
    ├── db.py                 # Database session management
    └── models.py             # SQLAlchemy models

app/                          # Legacy MailBot
├── gmail_client.py           # Gmail API wrapper
├── ai_reply.py               # OpenAI reply drafting
└── rules.py                  # Email classification

frontend/                     # React Dashboard (separate)
scripts/                      # Utility scripts
tests/                        # Test files
docs/                         # Documentation
```

---

## Testing

### Test Level 3 AI System

```bash
# Comprehensive test script
bash scripts/TEST_LEVEL3_AI.sh

# Manual testing
curl http://localhost:8001/api/dashboard/v2/intelligence/scheduler/status
curl -X POST http://localhost:8001/api/dashboard/v2/intelligence/scheduler/start
curl http://localhost:8001/api/dashboard/v2/intelligence/alerts
```

### Test Product Discovery

```bash
# Test multi-niche discovery
bash scripts/TEST_PRODUCTS.sh

# Test specific niche
curl "http://localhost:8001/api/dashboard/v2/products?niche=smart_home&page=1"
```

### Run Unit Tests

```bash
uv run pytest
```

---

## Level 3 AI - Background Jobs

The autonomous intelligence system runs 4 scheduled jobs:

| Job | Schedule | Function |
|-----|----------|----------|
| `analyze_products` | Every 6 hours | Analyzes product performance, identifies underperformers and top performers, generates AI recommendations |
| `monitor_competitors` | Every 12 hours | Tracks competitor pricing and market changes, alerts on significant shifts |
| `track_trends` | Daily at 9am | Monitors market trends, identifies emerging niches and seasonal patterns |
| `weekly_report` | Sundays at 6pm | Generates comprehensive weekly performance summary with strategic recommendations |

### Alert System

Alerts are categorized by severity:

- **Critical**: Scheduler errors, system failures
- **Warning**: Underperforming products requiring intervention
- **Info**: Top performers, trend updates, reports

Access alerts via API:
```bash
# Get all alerts
curl http://localhost:8001/api/dashboard/v2/intelligence/alerts

# Get only warnings
curl "http://localhost:8001/api/dashboard/v2/intelligence/alerts?severity=warning&limit=10"
```

---

## Development

### Start Development Servers

```bash
# Backend (OspraOS)
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (React Dashboard)
cd frontend
npm run dev

# Legacy MailBot (if needed)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Code Quality

```bash
# Lint and format
uv run ruff check .
uv run ruff format .

# Type checking
uv run mypy ospra_os/
```

---

## Architecture

### Three-Tier Intelligence System

**Level 1: Data Collection**
- Real-time product data from AliExpress API
- Multi-source integration (AliExpress, Shopify, TikTok)
- Structured data storage in SQLite/PostgreSQL

**Level 2: AI Analysis**
- On-demand deep analysis using Claude API
- Product failure diagnosis with recommendations
- Market research and competitor analysis
- Confidence scoring and improvement predictions

**Level 3: Autonomous Operations**
- Background job scheduler using `schedule` library
- Thread-based execution for non-blocking operation
- Singleton pattern for scheduler instance management
- Deque-based alert storage (last 1000 alerts)
- Graceful degradation when AI unavailable

### Integration Points

- **AliExpress**: OAuth-based product discovery with intelligent fallbacks
- **Shopify**: Admin API for store management and order tracking
- **Claude API**: Advanced AI analysis and recommendations
- **Gmail**: OAuth 2.0 flow for email automation (legacy)

---

## Production Deployment

### Render.com Deployment

The platform is deployed at: `https://oubon-mailbot.onrender.com`

### Environment Setup

1. Set all environment variables in Render dashboard
2. Ensure `ANTHROPIC_API_KEY` is set for Level 3 AI
3. Configure health check endpoint: `/health`
4. Set build command: `uv sync`
5. Set start command: `uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port $PORT`

### Monitoring

- **Health Check**: `GET /health`
- **API Docs**: `GET /docs`
- **Scheduler Status**: `GET /api/dashboard/v2/intelligence/scheduler/status`
- **Logs**: View in Render dashboard or via `tail -f logs/`

---

## Troubleshooting

### Level 3 AI Not Starting

1. Check logs for startup messages: `grep "Level 3" /tmp/level3_test.log`
2. Verify `ANTHROPIC_API_KEY` is set (optional but recommended)
3. Ensure `schedule` library is installed: `uv pip list | grep schedule`
4. Manually start: `POST /api/dashboard/v2/intelligence/scheduler/start`

### Products Not Loading

1. Check AliExpress API credentials in `.env`
2. Test API connection: `curl http://localhost:8001/api/dashboard/v2/niches`
3. Review logs for API errors
4. Verify database exists: `ls -la data/ospra.db`

### Frontend Blank Page

1. Check backend is running: `curl http://localhost:8001/health`
2. Verify CORS settings in `main.py`
3. Check browser console for errors (F12)
4. Ensure frontend env variables are set

### Frontend Development Issues

**Common fixes documented:**

- **Runtime Errors (undefined data)**: See `RUNTIME_ERROR_FIXES_COMPLETE.md`
  - Undefined stores.map() errors
  - Missing safety checks
  - Prop name mismatches

- **Import Errors (lucide-react)**: See `LUCIDE_ICON_FIX_COMPLETE.md`
  - LucideIcon doesn't exist in lucide-react
  - Use React.ComponentType<{ className?: string }> for icon props

- **Data Structure Mismatch**: See `DATA_STRUCTURE_FIX_COMPLETE.md`
  - Backend uses snake_case (store_name, monthly_revenue)
  - Frontend must match backend format
  - No camelCase transformation layer

---

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Level 1 - Data Collection | ✅ Production | AliExpress API integrated with OAuth |
| Level 2 - AI Analysis | ✅ Production | Claude API integration complete |
| Level 3 - Autonomous AI | ✅ Production | Background jobs operational |
| Dashboard V2 API | ✅ Production | All endpoints functional |
| React Frontend | ✅ Production | Real-time data display |
| Shopify Integration | ✅ Production | Store management active |
| Gmail Integration | ⚠️ Legacy | Original MailBot (port 8000) |
| TikTok Integration | 🚧 Development | Placeholder routes |

---

## Documentation

### Platform Documentation
- **Level 3 AI Status**: `LEVEL3_AI_STATUS.md`
- **Quick Start Guide**: `QUICK_START.md`
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **API Documentation**: `API_DOCUMENTATION.md`

### Integration Guides
- **AliExpress Integration**: `AFFILIATE_API_GUIDE.md`
- **TikTok Integration**: `TIKTOK_INTEGRATION_COMPLETE.md`
- **Shopify Setup**: `WEBSITE_COMPLETE.md`

### Frontend Development Fixes
- **Runtime Error Fixes**: `RUNTIME_ERROR_FIXES_COMPLETE.md`
  - Handling undefined data
  - Safety checks and optional props
  - Loading and error states

- **Lucide Icon Fix**: `LUCIDE_ICON_FIX_COMPLETE.md`
  - Correct icon prop types
  - Import best practices

- **Data Structure Fix**: `DATA_STRUCTURE_FIX_COMPLETE.md`
  - snake_case vs camelCase alignment
  - API-to-UI mapping

---

## Contributing

This is a private project for Oubon e-commerce automation. For issues or feature requests, contact the development team.

---

## License

Proprietary - All rights reserved

---

**Built with**: FastAPI, React, Claude AI, AliExpress API, Shopify API, SQLAlchemy

**Maintained by**: Oubon Development Team

**Last Updated**: November 14, 2025
