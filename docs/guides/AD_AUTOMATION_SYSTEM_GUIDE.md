# Complete Ad Automation System - Implementation Guide

## Overview

This guide outlines the complete ad automation system integrating Meta, TikTok, and Google Ads with AI-powered creative generation, scheduling, tracking, and optimization.

## System Architecture

```
ospra_os/
├── advertising/
│   ├── meta/          ✅ COMPLETE
│   ├── tiktok/        ✅ COMPLETE
│   ├── google/        🚧 TO IMPLEMENT
│   ├── creative_generator.py  🚧 TO IMPLEMENT
│   ├── scheduler.py   🚧 TO IMPLEMENT
│   └── __init__.py    ✅ COMPLETE
├── ai/
│   └── factory.py     🚧 NEEDED FOR AI GENERATION
└── database/
    └── multi_store_models.py  🚧 NEEDS AD_CAMPAIGN MODEL
```

## Components Status

### ✅ COMPLETED
1. **Meta Ads Integration** - `ospra_os/advertising/meta/meta_ads.py`
2. **TikTok Ads Integration** - `ospra_os/advertising/tiktok/tiktok_ads.py`
3. **Settings Configuration** - Added Meta & TikTok credentials
4. **Environment Variables** - `.env.example` updated

### 🚧 TO IMPLEMENT

#### 1. Google Ads Integration

**File:** `ospra_os/advertising/google/google_ads.py`

**Dependencies:**
```bash
uv add google-ads==23.1.0
```

**Configuration Required:**
- Create `google-ads.yaml` in project root
- Add credentials to .env:
  ```
  OUBONSHOP_GOOGLE_ADS_CUSTOMER_ID=
  OUBONSHOP_GOOGLE_ADS_DEVELOPER_TOKEN=
  OUBONSHOP_GOOGLE_ADS_CLIENT_ID=
  OUBONSHOP_GOOGLE_ADS_CLIENT_SECRET=
  OUBONSHOP_GOOGLE_ADS_REFRESH_TOKEN=
  ```

**Key Features:**
- Campaign creation (Search Ads)
- Responsive Search Ads (RSA)
- Keyword targeting
- Budget management
- Performance tracking

**Setup Steps:**
1. Create Google Ads account
2. Apply for developer token at https://ads.google.com/aw/apicenter
3. Set up OAuth2 credentials
4. Generate refresh token using OAuth playground

#### 2. AI Creative Generator

**File:** `ospra_os/advertising/creative_generator.py`

**Dependencies:**
- Requires AI factory system (see below)
- Uses existing OpenAI/Claude API keys

**Key Features:**
- Platform-specific ad copy generation
- Headlines, body copy, CTAs
- Character limit enforcement
- A/B testing variations
- Video script generation (for TikTok)

**Platforms Supported:**
- Meta: 40 char headlines, 125 char body
- TikTok: 100 char headlines, energetic tone
- Google: 30 char headlines, 90 char descriptions

#### 3. AI Factory System

**File:** `ospra_os/ai/factory.py`

**Purpose:** Unified interface for AI providers (OpenAI, Claude)

```python
class AIFactory:
    @staticmethod
    def get_provider(provider: str):
        if provider == 'openai':
            return OpenAIProvider()
        elif provider == 'claude':
            return ClaudeProvider()
        # ...
```

**Implementation:**
- Create `ospra_os/ai/` directory
- Create `factory.py`, `openai_provider.py`, `claude_provider.py`
- Implement common interface for `generate_content()`

#### 4. Ad Scheduler & Automation

**File:** `ospra_os/advertising/scheduler.py`

**Dependencies:**
```bash
uv add apscheduler==3.10.4
```

**Key Features:**
- Automated campaign creation
- Daily performance checks
- Budget optimization (every 6 hours)
- Auto-pause underperforming ads
- Platform-agnostic campaign management

**Schedule:**
- **Daily 9 AM:** Check all campaigns
- **Every 6 hours:** Optimize budgets
- **Hourly:** Auto-pause poor performers

**Optimization Logic:**
- High CTR (>2%) → Increase budget 20%
- Low CTR (<0.5%) → Decrease budget 20%
- Poor performance → Auto-pause

#### 5. Database Models

**File:** `ospra_os/database/multi_store_models.py`

**New Model:** `AdCampaign`

```python
class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    # Identity
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    store_id = Column(Integer, ForeignKey('stores.id'))

    # Campaign Details
    campaign_id = Column(String)  # Platform campaign ID
    platform = Column(String)  # meta, tiktok, google
    campaign_name = Column(String)

    # Budget
    daily_budget = Column(Float, default=0.0)
    total_spend = Column(Float, default=0.0)

    # Metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)

    # Calculated
    ctr = Column(Float, default=0.0)
    cpc = Column(Float, default=0.0)
    roas = Column(Float, default=0.0)

    # Status
    status = Column(String, default='paused')
    pause_reason = Column(String)

    # Timestamps
    created_at = Column(DateTime)
    activated_at = Column(DateTime)
    last_updated = Column(DateTime)
```

**Migration Required:**
```bash
# Create migration
alembic revision --autogenerate -m "Add ad_campaigns table"

# Apply migration
alembic upgrade head
```

#### 6. Unified API Endpoints

**File:** `ospra_os/main.py`

**New Endpoints:**

1. **POST /api/ads/create**
   - Create campaigns for product across platforms
   - Auto-generates creative using AI
   - Parameters: product_id, platforms[], daily_budget, auto_launch

2. **GET /api/ads/campaigns**
   - List all campaigns for user
   - Includes performance metrics

3. **POST /api/ads/campaigns/{id}/pause**
   - Pause specific campaign

4. **POST /api/ads/campaigns/{id}/activate**
   - Activate specific campaign

5. **GET /api/ads/analytics**
   - Aggregate analytics across all platforms
   - Total spend, ROAS, CTR, etc.

## Implementation Priority

### Phase 1: Core Infrastructure (Week 1)
1. ✅ Meta Ads (COMPLETE)
2. ✅ TikTok Ads (COMPLETE)
3. 🚧 AI Factory System
4. 🚧 Database Models

### Phase 2: Google & Creative (Week 2)
5. 🚧 Google Ads Integration
6. 🚧 AI Creative Generator

### Phase 3: Automation (Week 3)
7. 🚧 Ad Scheduler
8. 🚧 Unified API Endpoints
9. 🚧 Testing & Optimization

## Dependencies to Install

```bash
# Google Ads
uv add google-ads==23.1.0

# Scheduler
uv add apscheduler==3.10.4

# Already installed
# - facebook-business (Meta)
# - requests (TikTok)
# - openai/anthropic (AI)
```

## Configuration Files Needed

### 1. google-ads.yaml
```yaml
developer_token: "YOUR_DEVELOPER_TOKEN"
client_id: "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret: "YOUR_CLIENT_SECRET"
refresh_token: "YOUR_REFRESH_TOKEN"
login_customer_id: "YOUR_MANAGER_ACCOUNT_ID"
```

### 2. .env additions
```bash
# Google Ads
OUBONSHOP_GOOGLE_ADS_CUSTOMER_ID=1234567890
OUBONSHOP_GOOGLE_ADS_DEVELOPER_TOKEN=
OUBONSHOP_GOOGLE_ADS_CLIENT_ID=
OUBONSHOP_GOOGLE_ADS_CLIENT_SECRET=
OUBONSHOP_GOOGLE_ADS_REFRESH_TOKEN=
```

## Testing Strategy

### 1. Unit Tests
- Test each platform manager independently
- Mock API calls
- Verify creative generation

### 2. Integration Tests
- Test scheduler automation
- Verify database operations
- Test API endpoints

### 3. Manual Testing
- Create test campaign
- Monitor for 24 hours
- Verify auto-optimization

## Monitoring & Observability

### Metrics to Track
- Campaign creation success rate
- AI generation quality
- Scheduler reliability
- API response times
- Budget optimization accuracy

### Logging
- Campaign creation events
- Optimization decisions
- Auto-pause triggers
- API errors

## Security Considerations

1. **API Keys:** Store securely in environment variables
2. **Budget Limits:** Enforce max daily budget caps
3. **Rate Limiting:** Respect platform API limits
4. **Data Privacy:** GDPR compliance for user data

## Cost Considerations

### Platform Costs
- **Meta Ads:** Minimum $1/day per campaign
- **TikTok Ads:** Minimum $20/day per campaign
- **Google Ads:** Flexible, recommend $15/day

### API Costs
- **Meta API:** Free
- **TikTok API:** Free
- **Google Ads API:** Free (developer token required)
- **OpenAI/Claude:** Pay per token for creative generation

### Recommended Starting Budget
- **Total:** $50/day
- **Meta:** $15/day
- **TikTok:** $20/day
- **Google:** $15/day

## Next Steps

1. **Install Dependencies**
   ```bash
   uv add google-ads==23.1.0 apscheduler==3.10.4
   ```

2. **Create AI Factory**
   - Implement `ospra_os/ai/factory.py`
   - Create provider interfaces

3. **Implement Google Ads**
   - Follow Google Ads API setup guide
   - Create `ospra_os/advertising/google/google_ads.py`

4. **Build Creative Generator**
   - Implement `ospra_os/advertising/creative_generator.py`
   - Test with different platforms

5. **Database Migration**
   - Add `AdCampaign` model
   - Run migrations

6. **Scheduler Implementation**
   - Create `ospra_os/advertising/scheduler.py`
   - Test automation logic

7. **API Endpoints**
   - Add routes to `ospra_os/main.py`
   - Test end-to-end flow

## Resources

- **Google Ads API:** https://developers.google.com/google-ads/api
- **Meta Marketing API:** https://developers.facebook.com/docs/marketing-apis
- **TikTok Ads API:** https://ads.tiktok.com/marketing_api/docs
- **APScheduler Docs:** https://apscheduler.readthedocs.io

## Support

For questions or issues:
1. Check API documentation
2. Review error logs
3. Test with smaller budgets first
4. Monitor campaigns closely initially

---

**Status:** 🚧 Partial Implementation
- ✅ Meta & TikTok Ads Complete
- 🚧 Google Ads, AI, Scheduler Pending
- 📝 Full implementation requires additional setup
