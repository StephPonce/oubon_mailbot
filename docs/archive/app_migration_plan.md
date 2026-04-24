# Migration Plan: app/ → ospra_os/

**Created:** 2025-12-10
**Status:** In Progress
**Goal:** Consolidate all functionality from `app/` into the main `ospra_os/` application to eliminate duplicate code and create a single source of truth.

## Executive Summary

The `app/` directory contains a well-built email automation service with:
- 18 Python files (~83KB total)
- Gmail OAuth integration
- AI-powered auto-replies (Claude + OpenAI)
- Smart reply system with business hours logic
- Shopify order tracking integration
- Refund automation
- Analytics tracking
- Background job scheduling

**Problem:** Creates duplicate configuration, AI clients, database connections, and maintenance overhead.

**Solution:** Merge all functionality into `ospra_os/` following the established modular architecture.

---

## File Mapping

### Configuration Files

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/settings.py` | `ospra_os/core/settings.py` | **MERGE** | Add Gmail-specific settings (LABEL_AUTO_REPLIED, etc.) |

**Settings to Add:**
```python
# Email automation labels
LABEL_AUTO_REPLIED: str = "Auto Replied"

# Add if missing:
google_client_id: str = ""
google_client_secret: str = ""
google_redirect_uri: str = "http://localhost:8001/oauth2callback"
google_scopes: str = "https://www.googleapis.com/auth/gmail.modify ..."
google_credentials_file: str = ".secrets/credentials.json"
google_token_file: str = ".secrets/gmail_token.json"
```

---

### Email Automation Services

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/gmail_client.py` | `ospra_os/email_automation/gmail_client.py` | **MIGRATE** | Gmail API wrapper (OAuth, send email) |
| `app/email_processor.py` | `ospra_os/email_automation/email_processor.py` | **MIGRATE** | Email processing pipeline |
| `app/smart_reply.py` | `ospra_os/email_automation/smart_reply.py` | **MIGRATE** | Intelligent reply system |
| `app/business_hours.py` | `ospra_os/email_automation/business_hours.py` | **MIGRATE** | Business hours logic |
| `app/refund_processor.py` | `ospra_os/email_automation/refund_processor.py` | **MIGRATE** | Automated refund handling |
| `app/rules.py` | `ospra_os/email_automation/rules.py` | **MIGRATE** | Email classification rules |
| `app/oubonshop_policy.py` | `ospra_os/email_automation/policies.py` | **MIGRATE** | Company policy text |

**Import Path Changes:**
- `from app.gmail_client import GmailClient` → `from ospra_os.email_automation.gmail_client import GmailClient`
- `from app.smart_reply import SmartReplySystem` → `from ospra_os.email_automation.smart_reply import SmartReplySystem`

---

### AI Integration

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/ai_client.py` | `ospra_os/ai/multi_provider_client.py` | **MIGRATE** | Multi-provider AI client (Claude + OpenAI) |
| `app/response_cache.py` | `ospra_os/ai/response_cache.py` | **MIGRATE** | Response caching for AI replies |

**Features in app/ai_client.py:**
- ✅ Claude 3.5 Sonnet support
- ✅ OpenAI GPT-4o-mini support
- ✅ Response caching
- ✅ Cost tracking
- ✅ Smart policy context selection
- ✅ Template fallback

**Existing ospra_os/ai/ modules:**
- `cost_tracker.py` - Cost tracking (may be duplicate)
- `factory.py` - AI provider factory
- `model_router.py` - Model routing

**Action:** Review for feature overlap and consolidate.

---

### Database Models

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/models.py` (EmailFollowup) | `ospra_os/database/multi_store_models.py` | **MIGRATE** | Add EmailFollowup model |
| `app/db.py` | `ospra_os/database/db.py` | **COMPARE** | Async session manager (likely duplicate) |

**EmailFollowup Model:**
```python
class EmailFollowup(Base):
    """Track emails that need AI follow-up during operating hours."""
    __tablename__ = "email_followups"

    gmail_message_id = Column(String, primary_key=True)
    customer_email = Column(String, nullable=False)
    customer_name = Column(String)
    subject = Column(String)
    body = Column(Text)
    label = Column(String)
    needs_followup = Column(Boolean, default=False)
    followup_sent = Column(Boolean, default=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    template_sent_at = Column(DateTime)
    followup_sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

### Background Jobs & Scheduling

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/scheduler.py` | `ospra_os/tasks/email_tasks.py` | **CONVERT** | Convert APScheduler → Celery tasks |

**Current:** APScheduler (BackgroundScheduler)
**Target:** Celery (already in use in ospra_os)

**Jobs to Convert:**
1. `check_emails_job()` - Process inbox every X minutes
2. `process_followups_job()` - Send AI follow-ups during business hours

---

### Analytics

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/analytics.py` | `ospra_os/analytics/email_analytics.py` | **MIGRATE** | Email-specific analytics |

**Features:**
- Track email responses
- AI provider usage
- Cost tracking
- Response time metrics

---

### Legacy/Duplicate Files

| Source (app/) | Destination (ospra_os/) | Action | Notes |
|---------------|-------------------------|--------|-------|
| `app/__init__.py` | N/A | **REMOVE** | Empty init file |
| `app/ai_reply.py` | N/A | **REMOVE** | Legacy AI reply (superseded by ai_client.py) |
| `app/db.py` | N/A | **REMOVE** | Duplicate of ospra_os/database/db.py |
| `app/gmail_watch.py` | ospra_os/email_automation/gmail_watch.py | **EVALUATE** | Gmail push notifications (may be useful) |
| `app/templates/__init__.py` | N/A | **REMOVE** | Empty init file |

---

## Migration Steps

### ✅ Step 1: Audit app/ Directory
**Status:** COMPLETED
**Output:** `scripts/audit_app_directory.py` created and run successfully.

---

### 🔄 Step 2: Create Migration Plan
**Status:** IN PROGRESS
**Output:** This document.

---

### ⏳ Step 3: Backup app/
```bash
cp -r app/ app_backup_$(date +%Y%m%d)
echo "✅ Backed up app/ to app_backup_YYYYMMDD/"
```

---

### ⏳ Step 4: Merge Configuration

**Target:** `ospra_os/core/settings.py`

**Actions:**
1. Add Gmail OAuth settings from `app/settings.py`
2. Add email automation labels
3. Ensure all existing settings are preserved
4. Test settings loading

**Validation:**
```python
from ospra_os.core.settings import get_settings
settings = get_settings()
assert settings.google_client_id is not None
assert settings.LABEL_AUTO_REPLIED == "Auto Replied"
```

---

### ⏳ Step 5: Migrate Email Automation Services

**Target Directory:** `ospra_os/email_automation/`

**Files to Migrate:**
1. `gmail_client.py` - Gmail API wrapper
2. `email_processor.py` - Email processing pipeline
3. `smart_reply.py` - Intelligent reply system
4. `business_hours.py` - Business hours logic
5. `refund_processor.py` - Refund automation
6. `rules.py` - Classification rules
7. `policies.py` (renamed from oubonshop_policy.py)

**Import Updates:**
```python
# Before:
from app.gmail_client import GmailClient
from app.email_processor import EmailProcessor
from app.smart_reply import SmartReplySystem

# After:
from ospra_os.email_automation.gmail_client import GmailClient
from ospra_os.email_automation.email_processor import EmailProcessor
from ospra_os.email_automation.smart_reply import SmartReplySystem
```

---

### ⏳ Step 6: Migrate AI Integration

**Target Directory:** `ospra_os/ai/`

**Files to Migrate:**
1. `multi_provider_client.py` (from ai_client.py)
2. `response_cache.py`

**Actions:**
1. Compare with existing `ospra_os/ai/` modules
2. Consolidate features (cost tracking, caching, etc.)
3. Update imports throughout codebase

---

### ⏳ Step 7: Migrate Database Models

**Target:** `ospra_os/database/multi_store_models.py`

**Actions:**
1. Add `EmailFollowup` model
2. Add helper functions: `init_followup_db()`, `get_followup_session()`
3. Update database migrations if using Alembic

---

### ⏳ Step 8: Convert Background Jobs to Celery

**Target:** `ospra_os/tasks/email_tasks.py`

**Create Celery Tasks:**
```python
from celery import shared_task
from ospra_os.email_automation.email_processor import EmailProcessor
from ospra_os.core.settings import get_settings

@shared_task(name="check_emails")
def check_emails_task():
    """Process inbox for new emails."""
    settings = get_settings()
    processor = EmailProcessor(settings)
    # ... process inbox logic

@shared_task(name="process_followups")
def process_followups_task():
    """Send AI follow-ups during business hours."""
    # ... follow-up logic
```

**Configure Celery Beat Schedule:**
```python
# In ospra_os/celery_config.py or similar
CELERY_BEAT_SCHEDULE = {
    'check-emails-every-5-minutes': {
        'task': 'check_emails',
        'schedule': 300.0,  # 5 minutes
    },
    'process-followups-every-hour': {
        'task': 'process_followups',
        'schedule': 3600.0,  # 1 hour
    },
}
```

---

### ⏳ Step 9: Migrate Analytics

**Target:** `ospra_os/analytics/email_analytics.py`

**Actions:**
1. Move `app/analytics.py` → `ospra_os/analytics/email_analytics.py`
2. Update imports
3. Integrate with existing analytics modules

---

### ⏳ Step 10: Create Email Routes

**Target:** `ospra_os/api/email_automation_routes.py`

**Create API Endpoints:**
```python
from fastapi import APIRouter, Depends
from ospra_os.core.settings import Settings, get_settings
from ospra_os.email_automation.email_processor import EmailProcessor

router = APIRouter(prefix="/api/email-automation", tags=["Email Automation"])

@router.post("/process-inbox")
async def process_inbox(settings: Settings = Depends(get_settings)):
    """Manually trigger inbox processing."""
    processor = EmailProcessor(settings)
    result = processor.process_inbox(auto_reply=True, max_messages=25)
    return result

@router.get("/gmail/auth-url")
async def get_gmail_auth_url(settings: Settings = Depends(get_settings)):
    """Get Gmail OAuth authorization URL."""
    from ospra_os.email_automation.gmail_client import GmailClient
    client = GmailClient(settings)
    return {"auth_url": client.build_auth_url()}

@router.get("/gmail/oauth-callback")
async def gmail_oauth_callback(code: str, settings: Settings = Depends(get_settings)):
    """Handle Gmail OAuth callback."""
    from ospra_os.email_automation.gmail_client import GmailClient
    client = GmailClient(settings)
    client.exchange_code_for_tokens(code)
    return {"status": "success", "message": "Gmail connected successfully"}

@router.get("/followups/pending")
async def get_pending_followups(settings: Settings = Depends(get_settings)):
    """Get emails pending AI follow-up."""
    from ospra_os.database.multi_store_models import EmailFollowup
    from ospra_os.database.db import get_db
    # ... query logic
    return {"followups": [...]}
```

---

### ⏳ Step 11: Update main.py

**Target:** `ospra_os/main.py`

**Add Email Router:**
```python
# In ospra_os/main.py

try:
    from ospra_os.api.email_automation_routes import router as email_router
    app.include_router(email_router)
    print("✅ Email Automation router loaded")
    _HAS_EMAIL_AUTOMATION = True
except ImportError as e:
    print(f"⚠️ Email Automation router not loaded: {e}")
    _HAS_EMAIL_AUTOMATION = False
```

---

### ⏳ Step 12: Remove/Archive app/

**Actions:**
1. Verify all functionality migrated
2. Run tests to ensure no breakage
3. Move app/ to archive:
   ```bash
   mkdir -p archive/
   mv app/ archive/app_archived_$(date +%Y%m%d)/
   ```

---

### ⏳ Step 13: Update References

**Search for Remaining References:**
```bash
grep -r "from app\." --include="*.py" ospra_os/
grep -r "import app\." --include="*.py" ospra_os/
```

**Update:**
- Import statements
- Documentation
- README files
- Configuration files

---

### ⏳ Step 14: Testing

**Test Checklist:**
1. ✅ Application starts without errors
2. ✅ Email automation routes accessible
3. ✅ Gmail OAuth flow works
4. ✅ Email processing works
5. ✅ AI replies generated correctly
6. ✅ Refund automation works
7. ✅ Background tasks execute
8. ✅ Analytics tracking functional
9. ✅ Settings loaded correctly
10. ✅ Database models created

**Test Commands:**
```bash
# Start application
uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001

# Test email routes
curl http://localhost:8001/api/email-automation/gmail/auth-url
curl http://localhost:8001/api/email-automation/followups/pending

# Test settings
python -c "from ospra_os.core.settings import get_settings; s = get_settings(); print(s.google_client_id)"

# Run tests
uv run pytest tests/test_email_automation.py -v
```

---

## Import Dependency Map

### Before Migration

```
app/
├── settings.py (standalone)
├── ai_client.py
│   ├── → app/oubonshop_policy.py
│   ├── → app/response_cache.py
│   └── → ospra_os/core/settings.py ✅ (already uses ospra_os)
├── email_processor.py
│   ├── → app/smart_reply.py
│   ├── → app/gmail_client.py
│   ├── → app/models.py
│   ├── → app/analytics.py
│   └── → ospra_os/core/settings.py ✅
├── smart_reply.py
│   ├── → app/business_hours.py
│   ├── → app/refund_processor.py
│   ├── → app/ai_client.py
│   ├── → ospra_os/integrations/shopify/client.py ✅
│   └── → ospra_os/core/settings.py ✅
├── gmail_client.py
│   └── → ospra_os/core/settings.py ✅
└── scheduler.py
    ├── → app/email_processor.py
    ├── → app/business_hours.py
    ├── → app/models.py
    ├── → app/gmail_client.py
    ├── → app/ai_client.py
    └── → ospra_os/core/settings.py ✅
```

**Observation:** Many files already import from `ospra_os/core/settings.py` - this makes migration easier!

---

### After Migration

```
ospra_os/
├── core/
│   └── settings.py (unified, includes Gmail settings)
├── ai/
│   ├── multi_provider_client.py (from app/ai_client.py)
│   └── response_cache.py (from app/response_cache.py)
├── email_automation/
│   ├── gmail_client.py (from app/gmail_client.py)
│   ├── email_processor.py (from app/email_processor.py)
│   ├── smart_reply.py (from app/smart_reply.py)
│   ├── business_hours.py (from app/business_hours.py)
│   ├── refund_processor.py (from app/refund_processor.py)
│   ├── rules.py (from app/rules.py)
│   └── policies.py (from app/oubonshop_policy.py)
├── database/
│   └── multi_store_models.py (+ EmailFollowup model)
├── analytics/
│   └── email_analytics.py (from app/analytics.py)
├── tasks/
│   └── email_tasks.py (from app/scheduler.py, converted to Celery)
└── api/
    └── email_automation_routes.py (new)
```

---

## Risk Assessment

### Low Risk ✅
- Configuration merge (settings already compatible)
- Service migration (files already use ospra_os.core.settings)
- Database model addition (EmailFollowup is isolated)

### Medium Risk ⚠️
- AI client consolidation (need to compare with existing ospra_os/ai/)
- Scheduler conversion (APScheduler → Celery)
- Import path updates (need comprehensive search/replace)

### High Risk 🔴
- None identified (thorough testing will mitigate risks)

---

## Rollback Plan

If migration fails:

1. **Restore backup:**
   ```bash
   rm -rf app/
   cp -r app_backup_YYYYMMDD/ app/
   ```

2. **Revert git changes:**
   ```bash
   git checkout -- ospra_os/
   git clean -fd ospra_os/
   ```

3. **Restart services:**
   ```bash
   uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001
   ```

---

## Success Criteria

✅ Migration is considered successful when:

1. All `app/` functionality is available in `ospra_os/`
2. Application starts without import errors
3. Email automation routes are accessible
4. Gmail OAuth flow works
5. Email processing works end-to-end
6. AI replies are generated correctly
7. Background tasks execute on schedule
8. Analytics tracking is functional
9. All tests pass
10. `app/` directory can be safely archived

---

## Timeline Estimate

- **Step 3 (Backup):** 1 minute
- **Step 4 (Config merge):** 15 minutes
- **Step 5 (Email services):** 30 minutes
- **Step 6 (AI migration):** 20 minutes
- **Step 7 (Models):** 10 minutes
- **Step 8 (Celery conversion):** 30 minutes
- **Step 9 (Analytics):** 10 minutes
- **Step 10 (Email routes):** 20 minutes
- **Step 11 (main.py update):** 5 minutes
- **Step 12 (Archive app/):** 2 minutes
- **Step 13 (Update references):** 15 minutes
- **Step 14 (Testing):** 30 minutes

**Total Estimated Time:** ~3 hours

---

## Next Actions

1. ✅ Review this migration plan
2. ⏳ Execute Step 3: Backup app/
3. ⏳ Execute Step 4: Merge configuration
4. ⏳ Continue with remaining steps sequentially
5. ⏳ Update project_structure.md after completion

---

## Notes

- Many files already import from `ospra_os.core.settings` - this is good architectural consistency
- The email automation service is well-architected and should integrate cleanly
- Consider adding comprehensive tests for email automation after migration
- Document the new email automation endpoints in API documentation

---

**Document Version:** 1.0
**Last Updated:** 2025-12-10
**Author:** Claude Code (Automated Migration Plan)
