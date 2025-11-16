# 🚀 Ospra Intelligence - Production Deployment Guide

## Prerequisites
- Python 3.11+
- Node.js 18+
- SQLite or PostgreSQL
- Domain with SSL certificate

## Environment Variables

### Required:
```bash
# Database
DATABASE_URL=sqlite:///./ospra.db

# AI Providers (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# Gmail (for email automation)
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...

# Platform Credentials (per store)
# Stored in database, not env vars
```

### Optional:
```bash
# Auto-discovery settings
AUTO_DISCOVERY_ENABLED=true
AUTO_DISCOVERY_SCHEDULE=0 3 * * *  # 3 AM daily

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
```

## Backend Deployment

### 1. Install Dependencies
```bash
cd /path/to/oubon_mailbot
pip install -r requirements.txt
```

### 2. Initialize Database
```bash
python -m ospra_os.database.init_multi_store --init
python -m ospra_os.database.init_multi_store --migrate
```

### 3. Run Backend
```bash
# Development
uvicorn ospra_os.main:app --reload --port 8000

# Production (use gunicorn)
gunicorn ospra_os.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Frontend Deployment

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Build Production
```bash
npm run build
```

### 3. Serve (options)
```bash
# Option 1: Serve with backend (FastAPI static files)
# Option 2: Deploy to Vercel/Netlify
# Option 3: Nginx
```

## Production Checklist

- [ ] SSL certificate configured
- [ ] Database backups enabled
- [ ] Error logging (Sentry, CloudWatch)
- [ ] Rate limiting enabled
- [ ] CORS properly configured
- [ ] API keys encrypted in database
- [ ] Health monitoring enabled
- [ ] Auto-discovery scheduled
- [ ] Email notifications tested
- [ ] All platform integrations tested

## Monitoring

Health endpoint: `GET /health`
Metrics endpoint: `GET /api/metrics`
Logs: Check `logs/` directory

## Troubleshooting

### Issue: Platform sync fails
- Check platform credentials
- Check rate limits
- Review error logs

### Issue: AI provider errors
- Verify API keys
- Check rate limits
- Try different provider

### Issue: Auto-discovery not running
- Check scheduler logs
- Verify cron schedule
- Check user settings
