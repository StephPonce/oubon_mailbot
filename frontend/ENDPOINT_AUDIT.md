# API Endpoint Audit Report

Generated: OspraOS API
Version: 0.1

## Summary

- **Total Backend Endpoints**: 401
- **Total Frontend Calls**: 49
- **✅ Matching**: 33
- **❌ Missing in Backend**: 16
- **🔧 Unused by Frontend**: 368

## ✅ Matching Endpoints

These 33 endpoints exist in both backend and frontend:


### A/B Testing
- `GET /api/abtesting/tests` - List Tests
  - Frontend: `abTestingAPI.getAll`
- `GET /api/abtesting/tests/{param}` - Get Test
  - Frontend: `abTestingAPI.getById`
- `GET /api/abtesting/tests/{param}/results` - Get Test Results
  - Frontend: `abTestingAPI.getResults`
- `POST /api/abtesting/tests` - Create Test
  - Frontend: `abTestingAPI.create`
- `POST /api/abtesting/tests/{param}/pause` - Pause Test
  - Frontend: `abTestingAPI.pause`
- `POST /api/abtesting/tests/{param}/resume` - Resume Test
  - Frontend: `abTestingAPI.resume`

### Analytics
- `GET /api/analytics/revenue` - Get Revenue Over Time
  - Frontend: `analyticsAPI.getRevenue`

### Competitor Intelligence
- `GET /api/competitors/{param}` - Get Competitor
  - Frontend: `competitorsAPI.getById`

### Customer Analytics
- `GET /api/customers/segments` - Get Customer Segments
  - Frontend: `analyticsAPI.getCustomerSegments`

### Dashboard V2
- `GET /api/dashboard/v2/overview` - Get Overview
  - Frontend: `analyticsAPI.getDashboardMetrics`
- `GET /api/dashboard/v2/products` - Get Products
  - Frontend: `productsAPI.getAll`
- `POST /api/dashboard/v2/claude/chat` - Claude Chat
  - Frontend: `intelligenceAPI.chat`
- `POST /api/dashboard/v2/products/{param}/analyze` - Analyze Product
  - Frontend: `productsAPI.analyze`

### Email Sync
- `POST /api/emails/sync` - Sync Emails
  - Frontend: `emailAPI.sync`

### Intelligence Core
- `GET /api/intelligence/briefing/morning` - Get Morning Briefing
  - Frontend: `intelligenceAPI.getInsights`

### Untagged
- `GET /api/dashboard/emails` - Get Dashboard Emails
  - Frontend: `emailAPI.getStats`
- `GET /api/dashboard/overview` - Get Dashboard Overview
  - Frontend: `intelligenceAPI.getContext`
- `GET /api/dashboard/shopify` - Get Dashboard Shopify
  - Frontend: `shopifyAPI.getProducts`
- `GET /api/emails/recent` - Get Recent Emails
  - Frontend: `emailAPI.getAll`
- `GET /api/health/detailed` - Detailed Health Check
  - Frontend: `systemAPI.getServices`
- `GET /api/niches/{param}` - Get Niche Analysis
  - Frontend: `nichesAPI.getById`
- `GET /api/rankings/top` - Get Top Rankings
  - Frontend: `productsAPI.getRankings`
- `GET /api/trends/breakouts` - Get Breakout Products
  - Frontend: `trendsAPI.getBreakouts`
- `GET /api/trends/heatmap` - Get Momentum Heatmap
  - Frontend: `trendsAPI.getHeatmap`
- `GET /api/trends/live` - Get Live Trending Products
  - Frontend: `trendsAPI.getLive`
- `GET /api/trends/movers` - Get Biggest Movers
  - Frontend: `trendsAPI.getMovers`
- `GET /api/trends/product/{param}` - Get Product Momentum
  - Frontend: `trendsAPI.getProductMomentum`
- `GET /health` - Health Check Immediate
  - Frontend: `systemAPI.getHealth`
- `POST /api/intelligence/discover` - Discover Winning Products Unified
  - Frontend: `productsAPI.discover`
- `POST /api/niches/{param}/analyze` - Trigger Niche Analysis
  - Frontend: `nichesAPI.analyze`
- `POST /api/recommendations/smart` - Get Smart Recommendations
  - Frontend: `intelligenceAPI.getRecommendations`
- `POST /api/shopify/bulk-deploy` - Bulk Deploy To Shopify
  - Frontend: `shopifyAPI.bulkDeploy`
- `POST /api/shopify/deploy` - Deploy To Shopify
  - Frontend: `productsAPI.deployToShopify`

## ❌ Missing in Backend (16)

These endpoints are called by the frontend but **DO NOT EXIST** in the backend:

- `GET /api/analytics/funnel`
  - Used by: `analyticsAPI.getConversionFunnel`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /api/analytics/products/performance`
  - Used by: `analyticsAPI.getProductPerformance`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /api/competitors`
  - Used by: `competitorsAPI.getAll`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /api/competitors/prices`
  - Used by: `competitorsAPI.getPriceComparison`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /api/dashboard/v2/products/{param}`
  - Used by: `productsAPI.getById`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /api/niches`
  - Used by: `nichesAPI.getAll`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /api/niches/{param}/products`
  - Used by: `nichesAPI.getProducts`
  - **Action Required**: Implement this endpoint or remove frontend call

- `GET /auth/me`
  - Used by: `authAPI.getProfile`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /api/competitors/{param}/analyze`
  - Used by: `competitorsAPI.analyze`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /api/emails/messages/{param}/ignore`
  - Used by: `emailAPI.markAsIgnored`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /api/emails/messages/{param}/reply`
  - Used by: `emailAPI.reply`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /api/intelligence/analyze/niche/{param}`
  - Used by: `intelligenceAPI.analyzeNiche`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /api/intelligence/analyze/product/{param}`
  - Used by: `intelligenceAPI.analyzeProduct`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /api/reports/generate`
  - Used by: `intelligenceAPI.generateReport`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /auth/register`
  - Used by: `authAPI.register`
  - **Action Required**: Implement this endpoint or remove frontend call

- `POST /auth/token`
  - Used by: `authAPI.login`
  - **Action Required**: Implement this endpoint or remove frontend call


## 🔧 Unused by Frontend (368)

These endpoints exist in the backend but are **NOT USED** by the frontend:


### A/B Testing
- `GET /api/abtesting/recommendations/price`
  - Get Price Recommendations
- `GET /api/abtesting/tests/{param}/significance`
  - Check Significance
- `POST /api/abtesting/events/conversion`
  - Record Conversion
- `POST /api/abtesting/events/impression`
  - Record Impression
- `POST /api/abtesting/events/variant`
  - Get Variant For Visitor
- `POST /api/abtesting/tests/description`
  - Create Description Test
- `POST /api/abtesting/tests/image`
  - Create Image Test
- `POST /api/abtesting/tests/price`
  - Create Price Test
- `POST /api/abtesting/tests/title`
  - Create Title Test
- `POST /api/abtesting/tests/{param}/end`
  - End Test
- `POST /api/abtesting/tests/{param}/start`
  - Start Test

### Admin Dashboard
- `GET /admin/dashboard`
  - Dashboard Page
- `GET /admin/dashboard/v2`
  - Dashboard V2

### Advertising
- `GET /api/ads/analytics`
  - Get Analytics
- `GET /api/ads/campaigns`
  - Get Campaigns
- `GET /api/ads/campaigns/{param}`
  - Get Campaign Detail
- `GET /api/ads/scheduler/status`
  - Get Scheduler Status
- `POST /api/ads/campaigns/{param}/activate`
  - Activate Campaign
- `POST /api/ads/campaigns/{param}/pause`
  - Pause Campaign
- `POST /api/ads/create`
  - Create Campaign

### Analytics
- `GET /api/analytics/export`
  - Export Analytics
- `GET /api/analytics/overview`
  - Get Analytics Overview
- `GET /api/analytics/products`
  - Get Product Performance
- `GET /api/analytics/profit`
  - Get Profit Breakdown
- `GET /api/analytics/stores`
  - Get Store Comparison

### Authentication
- `GET /api/auth/check-email`
  - Check Email
- `GET /api/auth/me`
  - Get Me
- `POST /api/auth/change-password`
  - Change Password
- `POST /api/auth/login`
  - Login
- `POST /api/auth/logout`
  - Logout
- `POST /api/auth/refresh`
  - Refresh Token
- `POST /api/auth/register`
  - Register

### Background Jobs
- `GET /api/jobs/jobs`
  - List Jobs
- `GET /api/jobs/status`
  - Get Scheduler Status
- `POST /api/jobs/jobs/{param}/run`
  - Run Job Now
- `POST /api/jobs/start`
  - Start Scheduler
- `POST /api/jobs/stop`
  - Stop Scheduler

### Competitor Intelligence
- `DELETE /api/competitors/{param}`
  - Delete Competitor
- `GET /api/competitors/`
  - List Competitors
- `GET /api/competitors/activity`
  - Get Activity
- `GET /api/competitors/ad-insights`
  - Get Ad Insights
- `GET /api/competitors/alerts`
  - Get Alerts
- `GET /api/competitors/gaps`
  - Get Competitive Gaps
- `GET /api/competitors/insights`
  - Get Insights
- `GET /api/competitors/jobs/status`
  - Get Intelligence Jobs Status
- `GET /api/competitors/landscape`
  - Get Competitive Landscape
- `GET /api/competitors/market-share`
  - Get Market Share
- `GET /api/competitors/price-changes`
  - Get Price Changes
- `GET /api/competitors/price-comparison`
  - Get Price Comparison
- `GET /api/competitors/pricing-opportunities`
  - Get Pricing Opportunities
- `GET /api/competitors/products/gaps`
  - Get Product Gaps
- `GET /api/competitors/products/overlapping`
  - Get Overlapping Products
- `GET /api/competitors/products/{param}`
  - Get Competitor Product
- `GET /api/competitors/products/{param}/price-history`
  - Get Price History
- `GET /api/competitors/{param}/ads`
  - Get Competitor Ads
- `GET /api/competitors/{param}/products`
  - Get Competitor Products
- `POST /api/competitors/`
  - Add Competitor
- `POST /api/competitors/auto-discover`
  - Auto Discover Competitors
- `POST /api/competitors/{param}/refresh`
  - Refresh Competitor
- `PUT /api/competitors/{param}`
  - Update Competitor Info

### Customer Analytics
- `GET /api/customers/at-risk`
  - Get At Risk Customers
- `GET /api/customers/cohorts`
  - Get Cohort Analysis
- `GET /api/customers/cohorts/best`
  - Get Best Cohorts
- `GET /api/customers/cohorts/ltv`
  - Get Cohort Ltv
- `GET /api/customers/ltv/by-segment`
  - Get Ltv By Segment
- `GET /api/customers/ltv/by-source`
  - Get Ltv By Source
- `GET /api/customers/ltv/distribution`
  - Get Ltv Distribution
- `GET /api/customers/ltv/top-customers`
  - Get Top Customers By Ltv
- `GET /api/customers/overview`
  - Get Customer Overview
- `GET /api/customers/patterns/product-affinity`
  - Get Product Affinity
- `GET /api/customers/patterns/timing`
  - Get Global Timing Patterns
- `GET /api/customers/search`
  - Search Customers
- `GET /api/customers/{param}/churn-risk`
  - Get Customer Churn Risk
- `GET /api/customers/{param}/ltv`
  - Get Customer Ltv
- `GET /api/customers/{param}/profile`
  - Get Customer Profile
- `GET /api/customers/{param}/purchase-patterns`
  - Get Customer Purchase Patterns
- `POST /api/customers/sync/shopify`
  - Sync From Shopify
- `POST /api/customers/sync/shopify/{param}`
  - Sync Single Customer

### Dashboard V2
- `DELETE /api/dashboard/v2/intelligence/alerts`
  - Clear Alerts
- `DELETE /api/dashboard/v2/products/{param}/deployment`
  - Remove Deployment
- `GET /api/dashboard/v2/analytics`
  - Get Analytics
- `GET /api/dashboard/v2/analytics/business`
  - Get Business Analytics
- `GET /api/dashboard/v2/analytics/summary`
  - Get Analytics Summary
- `GET /api/dashboard/v2/deployments`
  - Get Deployments
- `GET /api/dashboard/v2/health`
  - Health Check
- `GET /api/dashboard/v2/intelligence/alerts`
  - Get Alerts
- `GET /api/dashboard/v2/intelligence/drop-candidates`
  - Get Drop Candidates
- `GET /api/dashboard/v2/intelligence/patterns`
  - Get Product Patterns
- `GET /api/dashboard/v2/intelligence/scheduler/status`
  - Get Scheduler Status
- `GET /api/dashboard/v2/live-products`
  - Get Live Products Endpoint
- `GET /api/dashboard/v2/market/trends`
  - Get Market Trends
- `GET /api/dashboard/v2/niches`
  - Get Niches
- `GET /api/dashboard/v2/notifications`
  - Get Notifications
- `GET /api/dashboard/v2/orders`
  - Get Orders
- `GET /api/dashboard/v2/performance/top`
  - Get Top Performers
- `GET /api/dashboard/v2/performance/underperformers`
  - Get Underperformers
- `GET /api/dashboard/v2/products/{param}/deployment-status`
  - Get Deployment Status
- `GET /api/dashboard/v2/products/{param}/performance`
  - Get Product Performance
- `GET /api/dashboard/v2/shopify/status`
  - Shopify Status
- `POST /api/dashboard/v2/intelligence/predict`
  - Predict Product Performance
- `POST /api/dashboard/v2/intelligence/scheduler/run-now/{param}`
  - Run Job Now
- `POST /api/dashboard/v2/intelligence/scheduler/start`
  - Start Scheduler
- `POST /api/dashboard/v2/intelligence/scheduler/stop`
  - Stop Scheduler
- `POST /api/dashboard/v2/notifications/mark-all-read`
  - Mark All Notifications Read
- `POST /api/dashboard/v2/notifications/{param}/read`
  - Mark Notification Read
- `POST /api/dashboard/v2/orders/{param}/tracking`
  - Add Tracking
- `POST /api/dashboard/v2/products/bulk-deploy`
  - Bulk Deploy Products
- `POST /api/dashboard/v2/products/refresh`
  - Refresh Products
- `POST /api/dashboard/v2/products/{param}/deploy-to-shopify`
  - Deploy To Shopify
- `POST /api/dashboard/v2/products/{param}/sync-deployment`
  - Sync Deployment Status
- `POST /api/dashboard/v2/products/{param}/track`
  - Track Product Metric

### Email Analytics
- `GET /api/emails/stats/categories`
  - Get Email Categories
- `GET /api/emails/stats/costs`
  - Get Ai Costs
- `GET /api/emails/stats/performance`
  - Get Performance Metrics
- `GET /api/emails/stats/weekly`
  - Get Weekly Email Stats

### Email Automation
- `DELETE /api/email-automation/labels/{param}`
  - Delete Email Label
- `DELETE /api/email-automation/rules/{param}`
  - Delete Automation Rule
- `DELETE /api/email-automation/templates/{param}`
  - Delete Email Template
- `GET /api/email-automation/labels`
  - Get Email Labels
- `GET /api/email-automation/rules`
  - Get Automation Rules
- `GET /api/email-automation/templates`
  - Get Email Templates
- `POST /api/email-automation/labels`
  - Create Email Label
- `POST /api/email-automation/process`
  - Process Automation Rules
- `POST /api/email-automation/rules`
  - Create Automation Rule
- `POST /api/email-automation/templates`
  - Create Email Template
- `PUT /api/email-automation/labels/{param}`
  - Update Email Label
- `PUT /api/email-automation/rules/{param}`
  - Update Automation Rule
- `PUT /api/email-automation/templates/{param}`
  - Update Email Template

### Email OAuth
- `DELETE /api/email-oauth/accounts/{param}`
  - Delete Email Account
- `GET /api/email-oauth/accounts`
  - Get User Email Accounts
- `GET /api/email-oauth/providers/presets`
  - Get Imap Smtp Presets
- `GET /api/email-oauth/{param}/callback`
  - Email Oauth Callback
- `GET /api/email-oauth/{param}/connect`
  - Connect Email Provider
- `POST /api/email-oauth/accounts/{param}/set-primary`
  - Set Primary Email
- `POST /api/email-oauth/{param}/connect-imap`
  - Connect Imap Smtp Provider

### Email Settings
- `DELETE /api/email-settings`
  - Reset Email Settings
- `GET /api/email-settings`
  - Get Email Settings
- `POST /api/email-settings`
  - Save Email Settings

### Email Sync
- `DELETE /api/emails/{param}`
  - Delete Email
- `GET /api/emails/list`
  - List Emails
- `GET /api/emails/stats/summary`
  - Get Email Stats
- `GET /api/emails/{param}`
  - Get Email Details
- `POST /api/emails/send`
  - Send Composed Email
- `POST /api/emails/{param}/archive`
  - Archive Email
- `POST /api/emails/{param}/label`
  - Apply Label To Email
- `POST /api/emails/{param}/mark-read`
  - Mark Email Read
- `POST /api/emails/{param}/reply`
  - Reply To Email
- `POST /api/emails/{param}/star`
  - Star Email

### Intelligence Core
- `GET /api/intelligence/briefing/on-demand`
  - Get On Demand Briefing
- `GET /api/intelligence/context/full`
  - Get Full Context
- `GET /api/intelligence/context/summary`
  - Get Context Summary
- `GET /api/intelligence/grade/product/{param}`
  - Grade Product
- `GET /api/intelligence/health`
  - Intelligence Health
- `GET /api/intelligence/progress/by-stage/{param}`
  - Get Products By Stage
- `GET /api/intelligence/progress/product/{param}`
  - Get Product Progress
- `GET /api/intelligence/tier/check-feature`
  - Check Feature Access
- `GET /api/intelligence/tier/check-limit`
  - Check Usage Limit
- `GET /api/intelligence/tier/info`
  - Get Tier Info
- `POST /api/intelligence/action/execute`
  - Execute Action
- `POST /api/intelligence/action/preview`
  - Preview Action
- `POST /api/intelligence/action/undo/{param}`
  - Undo Action
- `POST /api/intelligence/context/invalidate`
  - Invalidate Context Cache
- `POST /api/intelligence/grade/bulk`
  - Grade Products Bulk
- `POST /api/intelligence/progress/product/{param}/advance`
  - Advance Product Stage
- `POST /api/intelligence/tier/upgrade`
  - Upgrade Tier

### Multi-Store Portfolio
- `DELETE /api/portfolio/stores/{param}`
  - Delete Store
- `GET /api/portfolio/overview`
  - Get Portfolio Overview
- `GET /api/portfolio/rankings`
  - Get Store Rankings
- `GET /api/portfolio/stores/{param}`
  - Get Store Details
- `GET /api/portfolio/stores/{param}/orders`
  - Get Store Orders
- `GET /api/portfolio/stores/{param}/products`
  - Get Store Products
- `POST /api/portfolio/stores/add`
  - Add Store
- `POST /api/portfolio/stores/{param}/deploy-product`
  - Deploy Product To Store
- `POST /api/portfolio/stores/{param}/switch`
  - Switch Active Store
- `POST /api/portfolio/stores/{param}/sync`
  - Sync Store
- `POST /api/portfolio/stores/{param}/test`
  - Test Store Connection
- `PUT /api/portfolio/stores/{param}`
  - Update Store

### Notifications
- `GET /api/notifications/by-type/{param}`
  - Get Notifications By Type
- `GET /api/notifications/customer/{param}`
  - Get Customer Notifications
- `GET /api/notifications/recent`
  - Get Recent Notifications
- `GET /api/notifications/stats`
  - Get Notification Stats
- `POST /api/notifications/send`
  - Send Custom Notification

### Product Research
- `GET /research/reddit/trending`
  - Get Reddit Trending
- `GET /research/sources`
  - List Sources
- `GET /research/test-aliexpress`
  - Test Aliexpress
- `GET /research/trending`
  - Get Trending Products
- `POST /research/discover`
  - Discover Products
- `POST /research/find-products`
  - Find Products
- `POST /research/twitter-viral`
  - Discover Twitter Viral
- `POST /research/validate`
  - Validate Product

### TikTok Integration
- `GET /api/tiktok/auth/callback`
  - Handle Oauth Callback
- `GET /api/tiktok/auth/url`
  - Get Auth Url
- `GET /api/tiktok/profile`
  - Get User Profile
- `GET /api/tiktok/status`
  - Tiktok Status
- `GET /api/tiktok/videos`
  - Get User Videos
- `POST /api/tiktok/upload`
  - Upload Video

### TikTok OAuth
- `GET /auth/tiktok/authorize`
  - Start Tiktok Oauth
- `GET /auth/tiktok/callback`
  - Tiktok Oauth Callback
- `GET /auth/tiktok/status`
  - Tiktok Status
- `POST /auth/tiktok/test`
  - Test Tiktok Search

### Unified Product Discovery
- `GET /api/discovery/health`
  - Discovery Health Check
- `GET /api/discovery/live-products`
  - Get Live Products
- `GET /api/discovery/multi-niche`
  - Get Multi Niche Products
- `GET /api/discovery/niches`
  - List Available Niches
- `GET /api/discovery/quick/{param}`
  - Quick Discover
- `GET /api/discovery/stats`
  - Get Discovery Stats

### Untagged
- `DELETE /api/schedule/{param}`
  - Cancel Schedule
- `DELETE /api/shopify/products/{param}`
  - Delete Shopify Product
- `GET /admin/dashboard/data`
  - Get Admin Dashboard Data
- `GET /analytics/cache-stats`
  - Cache Stats
- `GET /analytics/costs`
  - Analytics Costs
- `GET /analytics/daily`
  - Analytics Daily
- `GET /analytics/labels`
  - Analytics Labels
- `GET /analytics/weekly`
  - Analytics Weekly
- `GET /api/ai/providers`
  - Get Ai Providers
- `GET /api/dashboard/api-status`
  - Get Api Status
- `GET /api/dashboard/products`
  - Get Dashboard Products
- `GET /api/debug/reddit`
  - Debug Reddit
- `GET /api/debug/reddit-connector-logs`
  - Debug Reddit Connector Logs
- `GET /api/debug/reddit-json`
  - Debug Reddit Json
- `GET /api/debug/reddit-raw`
  - Debug Reddit Raw
- `GET /api/debug/trends-test`
  - Debug Trends Test
- `GET /api/intelligence/stats`
  - Get Intelligence Stats
- `GET /api/learning/report`
  - Get Learning Report
- `GET /api/learning/velocity`
  - Get Velocity Report
- `GET /api/marketing/available-angles`
  - Get Available Angles
- `GET /api/meta/campaign/{param}/insights`
  - Get Campaign Insights
- `GET /api/niches/all`
  - Get All Niches
- `GET /api/niches/declining`
  - Get Declining Niches
- `GET /api/niches/emerging`
  - Get Emerging Niches
- `GET /api/niches/health`
  - Niche Analyzer Health
- `GET /api/niches/trending`
  - Get Trending Niches
- `GET /api/niches/{param}/entry-timing`
  - Evaluate Entry Timing
- `GET /api/niches/{param}/history`
  - Get Niche History
- `GET /api/niches/{param}/predict`
  - Predict Niche Trajectory
- `GET /api/niches/{param}/subcategories`
  - Get Niche Subcategories
- `GET /api/platforms`
  - Get Platforms
- `GET /api/products/test-discovery`
  - Test Product Discovery
- `GET /api/rankings/fallen`
  - Get Fallen Products
- `GET /api/rankings/history/{param}`
  - Get Product Rank History
- `GET /api/rankings/movers`
  - Get Ranking Movers
- `GET /api/rankings/new-entries`
  - Get New Entries
- `GET /api/rankings/product/{param}`
  - Get Product Ranking Details
- `GET /api/recommendations/analytics/{param}`
  - Get Recommendation Analytics
- `GET /api/schedule/calendar/month`
  - Get Month Calendar
- `GET /api/schedule/calendar/week`
  - Get Week Calendar
- `GET /api/schedule/forecast`
  - Get Budget Forecast
- `GET /api/schedule/list`
  - List Schedules
- `GET /api/schedule/{param}`
  - Get Schedule
- `GET /api/shopify/products`
  - List Shopify Products
- `GET /api/tiers/comparison`
  - Get Tier Comparison
- `GET /api/user/tier`
  - Get User Tier Info
- `GET /api/velocity/phase/{param}`
  - Get Products In Phase
- `GET /api/velocity/stats`
  - Get Velocity Stats
- `GET /api/velocity/tier-products`
  - Get Tier Products
- `POST /api/admin/run-discovery-now`
  - Run Discovery Now
- `POST /api/ai/test/{param}`
  - Test Ai Provider
- `POST /api/aliexpress/affiliate-links`
  - Generate Affiliate Links
- `POST /api/aliexpress/fulfill-order`
  - Fulfill Order
- `POST /api/aliexpress/monitor-prices`
  - Monitor Prices
- `POST /api/aliexpress/search`
  - Search Aliexpress
- `POST /api/aliexpress/sync-inventory`
  - Sync Inventory
- `POST /api/claude/chat`
  - Claude Chat
- `POST /api/deploy-to-shopify`
  - Deploy To Shopify
- `POST /api/deploy/product/{param}/to-all-stores`
  - Deploy Product To All
- `POST /api/deploy/product/{param}/to-store/{param}`
  - Deploy Product Endpoint
- `POST /api/discover`
  - Discover Products Api
- `POST /api/discover-multi`
  - Discover Multi Niche
- `POST /api/generate-content`
  - Generate Product Content
- `POST /api/intelligence/discover-enriched`
  - Discover Products Enriched Endpoint
- `POST /api/learning/demo`
  - Run Learning Demo
- `POST /api/learning/train`
  - Train Learning Engine
- `POST /api/marketing/generate-angle`
  - Generate Marketing Angle
- `POST /api/marketing/generate-multiple-angles`
  - Generate Multiple Angles
- `POST /api/meta/adset/{param}/budget`
  - Update Ad Set Budget
- `POST /api/meta/bulk-campaigns`
  - Create Bulk Campaigns
- `POST /api/meta/campaign/{param}/status`
  - Update Campaign Status
- `POST /api/meta/create-campaign`
  - Create Meta Campaign
- `POST /api/niches/compare`
  - Compare Niches
- `POST /api/optimize-price`
  - Optimize Product Price
- `POST /api/platforms/{param}/test`
  - Test Platform Credentials
- `POST /api/schedule/create`
  - Create Ad Schedule
- `POST /api/schedule/process`
  - Manually Process Schedules
- `POST /api/scrape-aliexpress-product`
  - Scrape Aliexpress Product
- `POST /api/user/check-limit`
  - Check Tier Limit
- `POST /api/user/upgrade-tier`
  - Upgrade User Tier
- `POST /api/validate-product`
  - Validate Product Api
- `POST /webhooks/shopify/orders/cancelled`
  - Shopify Order Cancelled Webhook
- `POST /webhooks/shopify/orders/create`
  - Shopify Order Webhook

### aliexpress
- `GET /aliexpress/auth/start`
  - Start Oauth
- `GET /aliexpress/auth/status`
  - Check Auth Status
- `GET /aliexpress/auth/token`
  - Get Access Token
- `GET /aliexpress/callback`
  - Oauth Callback
- `GET /aliexpress/debug/auth-url`
  - Debug Auth Url
- `GET /aliexpress/debug/config`
  - Debug Config
- `GET /api/aliexpress/callback`
  - Oauth Callback
- `GET /api/aliexpress/oauth-callback`
  - Oauth Callback
- `POST /aliexpress/auth/disconnect`
  - Disconnect Aliexpress

### aliexpress-affiliate
- `GET /api/aliexpress-affiliate/callback`
  - Affiliate Oauth Callback
- `GET /api/aliexpress-affiliate/oauth-callback`
  - Affiliate Oauth Callback

### aliexpress-products
- `GET /api/aliexpress/products/bestsellers`
  - Get Bestsellers
- `GET /api/aliexpress/products/debug/raw-response`
  - Debug Raw Response
- `GET /api/aliexpress/products/details`
  - Get Product Details
- `GET /api/aliexpress/products/feed-names`
  - Get Feed Names
- `GET /api/aliexpress/products/hot`
  - Get Hot Products
- `GET /api/aliexpress/products/hybrid-discover`
  - Hybrid Product Discovery
- `GET /api/aliexpress/products/product/{param}`
  - Get Single Product
- `GET /api/aliexpress/products/search`
  - Search Products Affiliate
- `GET /api/aliexpress/products/test/enrichment/{param}`
  - Test Dropship Enrichment
- `GET /api/aliexpress/products/test/order-create-check`
  - Test Order Create Capability

### aliexpress-tokens
- `GET /api/aliexpress/tokens/debug/env`
  - Debug Environment
- `GET /api/aliexpress/tokens/manual-entry`
  - Show Manual Entry Form
- `GET /api/aliexpress/tokens/status`
  - Get Token Status
- `POST /api/aliexpress/tokens/manual-entry`
  - Save Manual Token
- `POST /api/aliexpress/tokens/refresh/affiliate`
  - Refresh Affiliate Token Endpoint
- `POST /api/aliexpress/tokens/refresh/all`
  - Refresh All Tokens Endpoint
- `POST /api/aliexpress/tokens/refresh/dropship`
  - Refresh Dropship Token Endpoint

### gmail
- `GET /gmail/auth/callback`
  - Gmail Oauth Callback
- `GET /gmail/auth/debug`
  - Debug
- `GET /gmail/auth/messages`
  - Get Messages
- `GET /gmail/auth/start`
  - Start
- `GET /gmail/auth/stats`
  - Get Stats
- `GET /gmail/auth/status`
  - Status

### health
- `GET /api/health`
  - Get Overall Health
- `GET /api/health/alerts`
  - Get Alerts
- `GET /api/health/api-performance`
  - Get Api Performance
- `GET /api/health/api-performance/endpoints`
  - Get Endpoint Performance
- `GET /api/health/api-performance/slowest`
  - Get Slowest Endpoints
- `GET /api/health/errors`
  - Get Errors
- `GET /api/health/errors/trends`
  - Get Error Trends
- `GET /api/health/errors/{param}`
  - Get Error
- `GET /api/health/integrations`
  - Get All Integrations
- `GET /api/health/integrations/{param}`
  - Get Integration Status
- `GET /api/health/integrations/{param}/history`
  - Get Integration History
- `GET /api/health/jobs`
  - Get All Jobs
- `GET /api/health/jobs/{param}`
  - Get Job Status
- `GET /api/health/jobs/{param}/history`
  - Get Job History
- `GET /api/health/summary`
  - Get Health Summary
- `POST /api/health/alerts/{param}/acknowledge`
  - Acknowledge Alert
- `POST /api/health/alerts/{param}/resolve`
  - Resolve Alert
- `POST /api/health/errors/{param}/acknowledge`
  - Acknowledge Error
- `POST /api/health/errors/{param}/resolve`
  - Resolve Error
- `POST /api/health/integrations/{param}/test`
  - Test Integration
- `POST /api/health/jobs/{param}/disable`
  - Disable Job
- `POST /api/health/jobs/{param}/enable`
  - Enable Job
- `POST /api/health/jobs/{param}/trigger`
  - Trigger Job

### inventory
- `DELETE /api/inventory/history/cleanup`
  - Cleanup Old Snapshots
- `GET /api/inventory`
  - Get All Inventory
- `GET /api/inventory/alerts/restock`
  - Get Restock Alerts
- `GET /api/inventory/alerts/stockout`
  - Get Stockout Alerts
- `GET /api/inventory/health`
  - Health Check
- `GET /api/inventory/health/summary`
  - Get Inventory Health Summary
- `GET /api/inventory/history/recent`
  - Get Recent Snapshots
- `GET /api/inventory/history/{param}`
  - Get Product History
- `GET /api/inventory/history/{param}/trends`
  - Get Product Trends
- `GET /api/inventory/restock-orders`
  - Get Restock Orders
- `GET /api/inventory/restock-orders/{param}`
  - Get Restock Order
- `GET /api/inventory/shopify/products`
  - Get Shopify Inventory
- `GET /api/inventory/shopify/test-connection`
  - Test Shopify Connection
- `GET /api/inventory/{param}`
  - Get Product Forecast
- `POST /api/inventory/alerts/check-and-send`
  - Check And Send Alerts
- `POST /api/inventory/alerts/send-test`
  - Send Test Alert
- `POST /api/inventory/bulk/alerts`
  - Bulk Configure Alerts
- `POST /api/inventory/bulk/export`
  - Bulk Export Products
- `POST /api/inventory/bulk/reorder`
  - Bulk Reorder Products
- `POST /api/inventory/history/snapshot`
  - Save Forecast Snapshots
- `POST /api/inventory/restock-orders`
  - Create Restock Order
- `POST /api/inventory/shopify/sync`
  - Sync From Shopify

## 📚 Complete Backend API Reference

All available endpoints grouped by router/tag:


### A/B Testing (17 endpoints)
- `GET /api/abtesting/recommendations/price`
- `GET /api/abtesting/tests`
- `GET /api/abtesting/tests/{test_id}`
- `GET /api/abtesting/tests/{test_id}/results`
- `GET /api/abtesting/tests/{test_id}/significance`
- `POST /api/abtesting/events/conversion`
- `POST /api/abtesting/events/impression`
- `POST /api/abtesting/events/variant`
- `POST /api/abtesting/tests`
- `POST /api/abtesting/tests/description`
- `POST /api/abtesting/tests/image`
- `POST /api/abtesting/tests/price`
- `POST /api/abtesting/tests/title`
- `POST /api/abtesting/tests/{test_id}/end`
- `POST /api/abtesting/tests/{test_id}/pause`
- `POST /api/abtesting/tests/{test_id}/resume`
- `POST /api/abtesting/tests/{test_id}/start`

### Admin Dashboard (2 endpoints)
- `GET /admin/dashboard`
- `GET /admin/dashboard/v2`

### Advertising (7 endpoints)
- `GET /api/ads/analytics`
- `GET /api/ads/campaigns`
- `GET /api/ads/campaigns/{campaign_id}`
- `GET /api/ads/scheduler/status`
- `POST /api/ads/campaigns/{campaign_id}/activate`
- `POST /api/ads/campaigns/{campaign_id}/pause`
- `POST /api/ads/create`

### Analytics (6 endpoints)
- `GET /api/analytics/export`
- `GET /api/analytics/overview`
- `GET /api/analytics/products`
- `GET /api/analytics/profit`
- `GET /api/analytics/revenue`
- `GET /api/analytics/stores`

### Authentication (7 endpoints)
- `GET /api/auth/check-email`
- `GET /api/auth/me`
- `POST /api/auth/change-password`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `POST /api/auth/register`

### Background Jobs (5 endpoints)
- `GET /api/jobs/jobs`
- `GET /api/jobs/status`
- `POST /api/jobs/jobs/{job_id}/run`
- `POST /api/jobs/start`
- `POST /api/jobs/stop`

### Competitor Intelligence (24 endpoints)
- `DELETE /api/competitors/{competitor_id}`
- `GET /api/competitors/`
- `GET /api/competitors/activity`
- `GET /api/competitors/ad-insights`
- `GET /api/competitors/alerts`
- `GET /api/competitors/gaps`
- `GET /api/competitors/insights`
- `GET /api/competitors/jobs/status`
- `GET /api/competitors/landscape`
- `GET /api/competitors/market-share`
- `GET /api/competitors/price-changes`
- `GET /api/competitors/price-comparison`
- `GET /api/competitors/pricing-opportunities`
- `GET /api/competitors/products/gaps`
- `GET /api/competitors/products/overlapping`
- `GET /api/competitors/products/{product_id}`
- `GET /api/competitors/products/{product_id}/price-history`
- `GET /api/competitors/{competitor_id}`
- `GET /api/competitors/{competitor_id}/ads`
- `GET /api/competitors/{competitor_id}/products`
- `POST /api/competitors/`
- `POST /api/competitors/auto-discover`
- `POST /api/competitors/{competitor_id}/refresh`
- `PUT /api/competitors/{competitor_id}`

### Customer Analytics (19 endpoints)
- `GET /api/customers/at-risk`
- `GET /api/customers/cohorts`
- `GET /api/customers/cohorts/best`
- `GET /api/customers/cohorts/ltv`
- `GET /api/customers/ltv/by-segment`
- `GET /api/customers/ltv/by-source`
- `GET /api/customers/ltv/distribution`
- `GET /api/customers/ltv/top-customers`
- `GET /api/customers/overview`
- `GET /api/customers/patterns/product-affinity`
- `GET /api/customers/patterns/timing`
- `GET /api/customers/search`
- `GET /api/customers/segments`
- `GET /api/customers/{customer_id}/churn-risk`
- `GET /api/customers/{customer_id}/ltv`
- `GET /api/customers/{customer_id}/profile`
- `GET /api/customers/{customer_id}/purchase-patterns`
- `POST /api/customers/sync/shopify`
- `POST /api/customers/sync/shopify/{customer_id}`

### Dashboard V2 (37 endpoints)
- `DELETE /api/dashboard/v2/intelligence/alerts`
- `DELETE /api/dashboard/v2/products/{product_id}/deployment`
- `GET /api/dashboard/v2/analytics`
- `GET /api/dashboard/v2/analytics/business`
- `GET /api/dashboard/v2/analytics/summary`
- `GET /api/dashboard/v2/deployments`
- `GET /api/dashboard/v2/health`
- `GET /api/dashboard/v2/intelligence/alerts`
- `GET /api/dashboard/v2/intelligence/drop-candidates`
- `GET /api/dashboard/v2/intelligence/patterns`
- `GET /api/dashboard/v2/intelligence/scheduler/status`
- `GET /api/dashboard/v2/live-products`
- `GET /api/dashboard/v2/market/trends`
- `GET /api/dashboard/v2/niches`
- `GET /api/dashboard/v2/notifications`
- `GET /api/dashboard/v2/orders`
- `GET /api/dashboard/v2/overview`
- `GET /api/dashboard/v2/performance/top`
- `GET /api/dashboard/v2/performance/underperformers`
- `GET /api/dashboard/v2/products`
- `GET /api/dashboard/v2/products/{product_id}/deployment-status`
- `GET /api/dashboard/v2/products/{product_id}/performance`
- `GET /api/dashboard/v2/shopify/status`
- `POST /api/dashboard/v2/claude/chat`
- `POST /api/dashboard/v2/intelligence/predict`
- `POST /api/dashboard/v2/intelligence/scheduler/run-now/{job_name}`
- `POST /api/dashboard/v2/intelligence/scheduler/start`
- `POST /api/dashboard/v2/intelligence/scheduler/stop`
- `POST /api/dashboard/v2/notifications/mark-all-read`
- `POST /api/dashboard/v2/notifications/{notification_id}/read`
- `POST /api/dashboard/v2/orders/{shopify_order_id}/tracking`
- `POST /api/dashboard/v2/products/bulk-deploy`
- `POST /api/dashboard/v2/products/refresh`
- `POST /api/dashboard/v2/products/{product_id}/analyze`
- `POST /api/dashboard/v2/products/{product_id}/deploy-to-shopify`
- `POST /api/dashboard/v2/products/{product_id}/sync-deployment`
- `POST /api/dashboard/v2/products/{product_id}/track`

### Email Analytics (4 endpoints)
- `GET /api/emails/stats/categories`
- `GET /api/emails/stats/costs`
- `GET /api/emails/stats/performance`
- `GET /api/emails/stats/weekly`

### Email Automation (13 endpoints)
- `DELETE /api/email-automation/labels/{label_id}`
- `DELETE /api/email-automation/rules/{rule_id}`
- `DELETE /api/email-automation/templates/{template_id}`
- `GET /api/email-automation/labels`
- `GET /api/email-automation/rules`
- `GET /api/email-automation/templates`
- `POST /api/email-automation/labels`
- `POST /api/email-automation/process`
- `POST /api/email-automation/rules`
- `POST /api/email-automation/templates`
- `PUT /api/email-automation/labels/{label_id}`
- `PUT /api/email-automation/rules/{rule_id}`
- `PUT /api/email-automation/templates/{template_id}`

### Email OAuth (7 endpoints)
- `DELETE /api/email-oauth/accounts/{account_id}`
- `GET /api/email-oauth/accounts`
- `GET /api/email-oauth/providers/presets`
- `GET /api/email-oauth/{provider}/callback`
- `GET /api/email-oauth/{provider}/connect`
- `POST /api/email-oauth/accounts/{account_id}/set-primary`
- `POST /api/email-oauth/{provider}/connect-imap`

### Email Settings (3 endpoints)
- `DELETE /api/email-settings`
- `GET /api/email-settings`
- `POST /api/email-settings`

### Email Sync (11 endpoints)
- `DELETE /api/emails/{email_id}`
- `GET /api/emails/list`
- `GET /api/emails/stats/summary`
- `GET /api/emails/{email_id}`
- `POST /api/emails/send`
- `POST /api/emails/sync`
- `POST /api/emails/{email_id}/archive`
- `POST /api/emails/{email_id}/label`
- `POST /api/emails/{email_id}/mark-read`
- `POST /api/emails/{email_id}/reply`
- `POST /api/emails/{email_id}/star`

### Intelligence Core (18 endpoints)
- `GET /api/intelligence/briefing/morning`
- `GET /api/intelligence/briefing/on-demand`
- `GET /api/intelligence/context/full`
- `GET /api/intelligence/context/summary`
- `GET /api/intelligence/grade/product/{product_id}`
- `GET /api/intelligence/health`
- `GET /api/intelligence/progress/by-stage/{stage}`
- `GET /api/intelligence/progress/product/{product_id}`
- `GET /api/intelligence/tier/check-feature`
- `GET /api/intelligence/tier/check-limit`
- `GET /api/intelligence/tier/info`
- `POST /api/intelligence/action/execute`
- `POST /api/intelligence/action/preview`
- `POST /api/intelligence/action/undo/{action_id}`
- `POST /api/intelligence/context/invalidate`
- `POST /api/intelligence/grade/bulk`
- `POST /api/intelligence/progress/product/{product_id}/advance`
- `POST /api/intelligence/tier/upgrade`

### Multi-Store Portfolio (12 endpoints)
- `DELETE /api/portfolio/stores/{store_id}`
- `GET /api/portfolio/overview`
- `GET /api/portfolio/rankings`
- `GET /api/portfolio/stores/{store_id}`
- `GET /api/portfolio/stores/{store_id}/orders`
- `GET /api/portfolio/stores/{store_id}/products`
- `POST /api/portfolio/stores/add`
- `POST /api/portfolio/stores/{store_id}/deploy-product`
- `POST /api/portfolio/stores/{store_id}/switch`
- `POST /api/portfolio/stores/{store_id}/sync`
- `POST /api/portfolio/stores/{store_id}/test`
- `PUT /api/portfolio/stores/{store_id}`

### Notifications (5 endpoints)
- `GET /api/notifications/by-type/{notification_type}`
- `GET /api/notifications/customer/{customer_id}`
- `GET /api/notifications/recent`
- `GET /api/notifications/stats`
- `POST /api/notifications/send`

### Product Research (8 endpoints)
- `GET /research/reddit/trending`
- `GET /research/sources`
- `GET /research/test-aliexpress`
- `GET /research/trending`
- `POST /research/discover`
- `POST /research/find-products`
- `POST /research/twitter-viral`
- `POST /research/validate`

### TikTok Integration (6 endpoints)
- `GET /api/tiktok/auth/callback`
- `GET /api/tiktok/auth/url`
- `GET /api/tiktok/profile`
- `GET /api/tiktok/status`
- `GET /api/tiktok/videos`
- `POST /api/tiktok/upload`

### TikTok OAuth (4 endpoints)
- `GET /auth/tiktok/authorize`
- `GET /auth/tiktok/callback`
- `GET /auth/tiktok/status`
- `POST /auth/tiktok/test`

### Unified Product Discovery (6 endpoints)
- `GET /api/discovery/health`
- `GET /api/discovery/live-products`
- `GET /api/discovery/multi-niche`
- `GET /api/discovery/niches`
- `GET /api/discovery/quick/{niche}`
- `GET /api/discovery/stats`

### Untagged (101 endpoints)
- `DELETE /api/schedule/{schedule_id}`
- `DELETE /api/shopify/products/{product_id}`
- `GET /admin/dashboard/data`
- `GET /analytics/cache-stats`
- `GET /analytics/costs`
- `GET /analytics/daily`
- `GET /analytics/labels`
- `GET /analytics/weekly`
- `GET /api/ai/providers`
- `GET /api/dashboard/api-status`
- `GET /api/dashboard/emails`
- `GET /api/dashboard/overview`
- `GET /api/dashboard/products`
- `GET /api/dashboard/shopify`
- `GET /api/debug/reddit`
- `GET /api/debug/reddit-connector-logs`
- `GET /api/debug/reddit-json`
- `GET /api/debug/reddit-raw`
- `GET /api/debug/trends-test`
- `GET /api/emails/recent`
- `GET /api/health/detailed`
- `GET /api/intelligence/stats`
- `GET /api/learning/report`
- `GET /api/learning/velocity`
- `GET /api/marketing/available-angles`
- `GET /api/meta/campaign/{campaign_id}/insights`
- `GET /api/niches/all`
- `GET /api/niches/declining`
- `GET /api/niches/emerging`
- `GET /api/niches/health`
- `GET /api/niches/trending`
- `GET /api/niches/{niche_id}`
- `GET /api/niches/{niche_id}/entry-timing`
- `GET /api/niches/{niche_id}/history`
- `GET /api/niches/{niche_id}/predict`
- `GET /api/niches/{niche_id}/subcategories`
- `GET /api/platforms`
- `GET /api/products/test-discovery`
- `GET /api/rankings/fallen`
- `GET /api/rankings/history/{product_id}`
- `GET /api/rankings/movers`
- `GET /api/rankings/new-entries`
- `GET /api/rankings/product/{product_id}`
- `GET /api/rankings/top`
- `GET /api/recommendations/analytics/{user_id}`
- `GET /api/schedule/calendar/month`
- `GET /api/schedule/calendar/week`
- `GET /api/schedule/forecast`
- `GET /api/schedule/list`
- `GET /api/schedule/{schedule_id}`
- `GET /api/shopify/products`
- `GET /api/tiers/comparison`
- `GET /api/trends/breakouts`
- `GET /api/trends/heatmap`
- `GET /api/trends/live`
- `GET /api/trends/movers`
- `GET /api/trends/product/{product_id}`
- `GET /api/user/tier`
- `GET /api/velocity/phase/{phase}`
- `GET /api/velocity/stats`
- `GET /api/velocity/tier-products`
- `GET /health`
- `POST /api/admin/run-discovery-now`
- `POST /api/ai/test/{provider}`
- `POST /api/aliexpress/affiliate-links`
- `POST /api/aliexpress/fulfill-order`
- `POST /api/aliexpress/monitor-prices`
- `POST /api/aliexpress/search`
- `POST /api/aliexpress/sync-inventory`
- `POST /api/claude/chat`
- `POST /api/deploy-to-shopify`
- `POST /api/deploy/product/{product_id}/to-all-stores`
- `POST /api/deploy/product/{product_id}/to-store/{store_id}`
- `POST /api/discover`
- `POST /api/discover-multi`
- `POST /api/generate-content`
- `POST /api/intelligence/discover`
- `POST /api/intelligence/discover-enriched`
- `POST /api/learning/demo`
- `POST /api/learning/train`
- `POST /api/marketing/generate-angle`
- `POST /api/marketing/generate-multiple-angles`
- `POST /api/meta/adset/{ad_set_id}/budget`
- `POST /api/meta/bulk-campaigns`
- `POST /api/meta/campaign/{campaign_id}/status`
- `POST /api/meta/create-campaign`
- `POST /api/niches/compare`
- `POST /api/niches/{niche_id}/analyze`
- `POST /api/optimize-price`
- `POST /api/platforms/{platform}/test`
- `POST /api/recommendations/smart`
- `POST /api/schedule/create`
- `POST /api/schedule/process`
- `POST /api/scrape-aliexpress-product`
- `POST /api/shopify/bulk-deploy`
- `POST /api/shopify/deploy`
- `POST /api/user/check-limit`
- `POST /api/user/upgrade-tier`
- `POST /api/validate-product`
- `POST /webhooks/shopify/orders/cancelled`
- `POST /webhooks/shopify/orders/create`

### aliexpress (9 endpoints)
- `GET /aliexpress/auth/start`
- `GET /aliexpress/auth/status`
- `GET /aliexpress/auth/token`
- `GET /aliexpress/callback`
- `GET /aliexpress/debug/auth-url`
- `GET /aliexpress/debug/config`
- `GET /api/aliexpress/callback`
- `GET /api/aliexpress/oauth-callback`
- `POST /aliexpress/auth/disconnect`

### aliexpress-affiliate (2 endpoints)
- `GET /api/aliexpress-affiliate/callback`
- `GET /api/aliexpress-affiliate/oauth-callback`

### aliexpress-products (10 endpoints)
- `GET /api/aliexpress/products/bestsellers`
- `GET /api/aliexpress/products/debug/raw-response`
- `GET /api/aliexpress/products/details`
- `GET /api/aliexpress/products/feed-names`
- `GET /api/aliexpress/products/hot`
- `GET /api/aliexpress/products/hybrid-discover`
- `GET /api/aliexpress/products/product/{product_id}`
- `GET /api/aliexpress/products/search`
- `GET /api/aliexpress/products/test/enrichment/{product_id}`
- `GET /api/aliexpress/products/test/order-create-check`

### aliexpress-tokens (7 endpoints)
- `GET /api/aliexpress/tokens/debug/env`
- `GET /api/aliexpress/tokens/manual-entry`
- `GET /api/aliexpress/tokens/status`
- `POST /api/aliexpress/tokens/manual-entry`
- `POST /api/aliexpress/tokens/refresh/affiliate`
- `POST /api/aliexpress/tokens/refresh/all`
- `POST /api/aliexpress/tokens/refresh/dropship`

### gmail (6 endpoints)
- `GET /gmail/auth/callback`
- `GET /gmail/auth/debug`
- `GET /gmail/auth/messages`
- `GET /gmail/auth/start`
- `GET /gmail/auth/stats`
- `GET /gmail/auth/status`

### health (23 endpoints)
- `GET /api/health`
- `GET /api/health/alerts`
- `GET /api/health/api-performance`
- `GET /api/health/api-performance/endpoints`
- `GET /api/health/api-performance/slowest`
- `GET /api/health/errors`
- `GET /api/health/errors/trends`
- `GET /api/health/errors/{error_id}`
- `GET /api/health/integrations`
- `GET /api/health/integrations/{name}`
- `GET /api/health/integrations/{name}/history`
- `GET /api/health/jobs`
- `GET /api/health/jobs/{job_name}`
- `GET /api/health/jobs/{job_name}/history`
- `GET /api/health/summary`
- `POST /api/health/alerts/{alert_id}/acknowledge`
- `POST /api/health/alerts/{alert_id}/resolve`
- `POST /api/health/errors/{error_id}/acknowledge`
- `POST /api/health/errors/{error_id}/resolve`
- `POST /api/health/integrations/{name}/test`
- `POST /api/health/jobs/{job_name}/disable`
- `POST /api/health/jobs/{job_name}/enable`
- `POST /api/health/jobs/{job_name}/trigger`

### inventory (22 endpoints)
- `DELETE /api/inventory/history/cleanup`
- `GET /api/inventory`
- `GET /api/inventory/alerts/restock`
- `GET /api/inventory/alerts/stockout`
- `GET /api/inventory/health`
- `GET /api/inventory/health/summary`
- `GET /api/inventory/history/recent`
- `GET /api/inventory/history/{product_id}`
- `GET /api/inventory/history/{product_id}/trends`
- `GET /api/inventory/restock-orders`
- `GET /api/inventory/restock-orders/{order_id}`
- `GET /api/inventory/shopify/products`
- `GET /api/inventory/shopify/test-connection`
- `GET /api/inventory/{product_id}`
- `POST /api/inventory/alerts/check-and-send`
- `POST /api/inventory/alerts/send-test`
- `POST /api/inventory/bulk/alerts`
- `POST /api/inventory/bulk/export`
- `POST /api/inventory/bulk/reorder`
- `POST /api/inventory/history/snapshot`
- `POST /api/inventory/restock-orders`
- `POST /api/inventory/shopify/sync`