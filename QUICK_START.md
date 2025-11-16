# Oubon Platform - Quick Start Guide

## 🚀 Starting All Services

### Option 1: One-Click Start (Recommended)
```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
./START_SERVERS.sh
```

### Option 2: Manual Start (Individual Terminals)

**Terminal 1 - Legacy MailBot:**
```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - OspraOS Platform:**
```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 3 - Frontend Dashboard:**
```bash
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot/frontend"
npm run dev
```

---

## 🌐 Access URLs

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:5173 | Product Intelligence Dashboard |
| **OspraOS API** | http://0.0.0.0:8001/docs | Swagger API Documentation |
| **Legacy MailBot** | http://0.0.0.0:8000/docs | Gmail Automation API |

---

## 🛑 Stopping Services

```bash
./STOP_SERVERS.sh
```

Or manually:
```bash
lsof -ti:8000,8001,5173 | xargs kill -9
```

---

## ✅ Check Service Status

```bash
./CHECK_STATUS.sh
```

---

## ⚠️ Important Notes

### Your Original Commands Had an Error:
```bash
# ❌ WRONG - Both can't use main:app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# ✅ CORRECT - Different entry points
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload
```

### Gmail OAuth Errors (Safe to Ignore)
You'll see periodic errors like:
```
google.auth.exceptions.RefreshError: deleted_client: The OAuth client was deleted
```

**This is normal!** The background scheduler tries to process Gmail but the OAuth client needs reconfiguration. The API servers work perfectly regardless.

---

## 📚 Features Available

### Frontend Dashboard (Port 5173)
✅ Multi-niche product intelligence  
✅ Auto-scrolling live market ticker  
✅ Portrait product cards with AliExpress links  
✅ Velocity filtering & sorting  
✅ Claude AI assistant integration  
✅ Gradient loading states  

### OspraOS Platform (Port 8001)
✅ Product Research V2  
✅ AliExpress OAuth  
✅ Gmail OAuth  
✅ TikTok integration  
✅ Multi-source market data  

### Legacy MailBot (Port 8000)
✅ Gmail automation  
✅ Email classification  
✅ Auto-reply system  
✅ Order tracking  
✅ Shopify integration  

---

## 🎯 Quick Access

**Open Dashboard:**
```bash
open http://localhost:5173
```

**View API Docs:**
```bash
open http://0.0.0.0:8001/docs
open http://0.0.0.0:8000/docs
```

---

## 📝 Recent Updates

✅ Auto-scrolling ticker (60s smooth animation)  
✅ AliExpress link buttons on product cards  
✅ Enhanced gradient loading states  
✅ Removed horizontal scrolling  
✅ Velocity score "HOT" badges  
✅ Improved responsive layout  

---

Generated: $(date)
